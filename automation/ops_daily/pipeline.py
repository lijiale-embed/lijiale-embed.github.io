"""运营日报：按固定业务日期统计、严格去重、以分为单位核算金额。"""
import argparse
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import amount, integer, read_table, logger_for, write_json, write_workbook

ORDER_FIELDS = ['order_id', 'sku', 'qty', 'unit_price', 'status', 'ordered_at']
REFUND_FIELDS = ['refund_id', 'order_id', 'amount', 'status']


def unique_rows(rows, key, issues, source):
    groups = defaultdict(list)
    for index, row in enumerate(rows, 2):
        groups[row[key]].append((index, row))
    result, removed = [], 0
    for identity, group in groups.items():
        if not identity:
            for index, _ in group:
                issues.append(dict(source=source, row=index, record_id='', code='MISSING_ID', reason=f'{key} 为空'))
        elif len({tuple(sorted(row.items())) for _, row in group}) > 1:
            for index, _ in group:
                issues.append(dict(source=source, row=index, record_id=identity, code='CONFLICT_DUPLICATE', reason='同一编号内容冲突，整组转人工'))
        else:
            result.append(group[0][1])
            removed += len(group) - 1
    return result, removed


def run(input_dir, output_dir, report_date='2026-10-15'):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    log = logger_for('ops_daily', output_dir)
    started = perf_counter()
    try:
        target = date.fromisoformat(report_date)
        issues = []
        products = read_table(input_dir / 'products.xlsx', ['sku', 'name', 'stock', 'low_stock_threshold'])
        catalog = {}
        for row in products:
            sku = row['sku']
            if not sku or not row['name'] or sku in catalog:
                raise ValueError('商品主数据 SKU 为空、重复或名称为空，停止生成日报')
            catalog[sku] = dict(sku=sku, name=row['name'], stock=integer(row['stock']),
                                threshold=integer(row['low_stock_threshold']))
        paths = sorted([*input_dir.glob('orders*.csv'), *input_dir.glob('orders*.xlsx')])
        if not paths:
            raise ValueError('缺少 orders*.csv 或 orders*.xlsx')
        raw_orders = [row for path in paths for row in read_table(path, ORDER_FIELDS)]
        orders, duplicate_orders = unique_rows(raw_orders, 'order_id', issues, 'orders（按文件名拼接后的数据行）')
        valid, excluded = {}, 0
        for row in orders:
            oid = row['order_id']
            try:
                if not row['sku'] or row['sku'] not in catalog:
                    raise ValueError('SKU 缺失或不在商品主数据中')
                qty, cents = integer(row['qty'], positive=True), amount(row['unit_price'])
                ordered = date.fromisoformat(row['ordered_at'])
                if row['status'] not in {'paid', 'cancelled'}:
                    raise ValueError('未知订单状态')
                if row['status'] != 'paid' or ordered != target:
                    excluded += 1
                    continue
                valid[oid] = dict(row, qty=qty, cents=cents, total_cents=cents * qty)
            except ValueError as exc:
                issues.append(dict(source='orders', row='', record_id=oid, code='INVALID_ORDER', reason=str(exc)))
        refunds, duplicate_refunds = unique_rows(read_table(input_dir / 'refunds.csv', REFUND_FIELDS), 'refund_id', issues, 'refunds')
        by_order = defaultdict(list)
        for row in refunds:
            try:
                if row['status'] not in {'success', 'pending'}:
                    raise ValueError('未知退款状态')
                cents = amount(row['amount'])
                if row['status'] == 'pending':
                    continue
                if row['order_id'] not in valid:
                    raise ValueError('退款没有对应的当日有效已付订单')
                by_order[row['order_id']].append((row['refund_id'], cents))
            except ValueError as exc:
                issues.append(dict(source='refunds', row='', record_id=row['refund_id'], code='INVALID_REFUND', reason=str(exc)))
        refund_cents = 0
        for oid, values in by_order.items():
            total = sum(cents for _, cents in values)
            if total > valid[oid]['total_cents']:
                for rid, _ in values:
                    issues.append(dict(source='refunds', row='', record_id=rid, code='REFUND_EXCEEDS_ORDER', reason='累计退款大于订单金额，整组不计入汇总'))
            else:
                refund_cents += total
        gross_cents = sum(row['total_cents'] for row in valid.values())
        sales = []
        for sku, product in catalog.items():
            rows = [r for r in valid.values() if r['sku'] == sku]
            sales.append(dict(SKU=sku, 商品=product['name'], 销量=sum(r['qty'] for r in rows),
                              销售额元=sum(r['total_cents'] for r in rows) / 100))
        low_stock = [dict(SKU=p['sku'], 商品=p['name'], 库存=p['stock'], 预警阈值=p['threshold'])
                     for p in catalog.values() if p['stock'] <= p['threshold']]
        metrics = dict(report_date=report_date, gross_sales=gross_cents / 100, order_count=len(valid),
                       refund_amount=refund_cents / 100, net_sales=(gross_cents-refund_cents) / 100,
                       units_sold=sum(r['qty'] for r in valid.values()), low_stock_count=len(low_stock),
                       exception_count=len(issues), duplicate_orders_removed=duplicate_orders,
                       duplicate_refunds_removed=duplicate_refunds, excluded_orders=excluded,
                       raw_order_rows=len(raw_orders))
        labels = {'report_date':'统计日期', 'gross_sales':'销售额元', 'order_count':'有效订单数',
                  'refund_amount':'成功退款元', 'net_sales':'退款后销售额元', 'units_sold':'售出件数',
                  'low_stock_count':'低库存商品数', 'exception_count':'异常条数',
                  'duplicate_orders_removed':'去除完全重复订单行', 'duplicate_refunds_removed':'去除完全重复退款行',
                  'excluded_orders':'非当日或取消订单数', 'raw_order_rows':'订单输入行数'}
        overview = [dict(指标=labels[k], 数值=v) for k,v in metrics.items()]
        overview += [dict(指标='数据性质', 数值='个人模拟业务数据'),
                     dict(指标='统计口径', 数值='当日已付订单销售额，减对应成功退款；销量为退款前件数'),
                     dict(指标='更新方式', 数值='结果值报表；修改源数据后重新运行程序')]
        write_workbook(output_dir / '运营日报.xlsx', {
            '日报汇总': (['指标','数值'], overview),
            '商品销量': (['SKU','商品','销量','销售额元'], sales),
            '库存预警': (['SKU','商品','库存','预警阈值'], low_stock),
            '异常清单': (['source','row','record_id','code','reason'], issues)})
        write_json(output_dir / 'exceptions.json', issues)
        metrics.update(status='success', elapsed_seconds=round(perf_counter()-started,6), dataset='synthetic')
        write_json(output_dir / 'metrics.json', metrics)
        log.info('完成 %s', metrics)
        return metrics
    except Exception as exc:
        log.exception('运营日报生成失败')
        write_json(output_dir / 'metrics.json', dict(status='failed', error=str(exc)))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=Path(__file__).parent/'data')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent/'outputs')
    parser.add_argument('--date', default='2026-10-15')
    args=parser.parse_args()
    print(run(args.input,args.output,args.date))
