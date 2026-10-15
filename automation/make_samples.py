"""固定虚构样例与独立验收答案；不覆盖既有数据。"""
from pathlib import Path
import pandas as pd
from shared import write_workbook, write_json
ROOT=Path(__file__).resolve().parent


def make(root=ROOT):
    folder=root/'ops_daily/data'
    folder.mkdir(parents=True,exist_ok=True)
    products=[dict(sku='P001',name='舒适生活礼盒',stock=8,low_stock_threshold=10),
              dict(sku='P002',name='便携收纳包',stock=40,low_stock_threshold=10),
              dict(sku='P003',name='替换配件',stock=3,low_stock_threshold=5),
              dict(sku='P004',name='旅行套装',stock=0,low_stock_threshold=5)]
    orders=[]
    for oid,sku,qty,price in [('O001','P001',1,299),('O002','P002',2,99),('O003','P003',3,49),
                               ('O004','P004',1,159),('O005','P002',1,99),('O006','P001',2,299)]:
        orders.append(dict(order_id=oid,sku=sku,qty=qty,unit_price=price,status='paid',ordered_at='2026-10-15'))
    orders += [dict(orders[2],order_id='O007',status='cancelled'), dict(orders[0],order_id='O008',ordered_at='2026-10-14')]
    extras=[dict(orders[0],order_id='O009',sku=''),dict(orders[0],order_id='O010',unit_price=-1),
            dict(orders[0],order_id='O011',qty='1.5'),dict(orders[0],order_id='O012',sku='UNKNOWN'),
            dict(orders[0],order_id='O013',unit_price='bad'),dict(orders[0],order_id='O014',ordered_at='bad'),
            dict(orders[1],order_id='O015',qty=1),dict(orders[1],order_id='O015',qty=1,unit_price=98),dict(orders[1])]
    refunds=[dict(refund_id=rid,order_id=oid,amount=price,status=status) for rid,oid,price,status in [
        ('R001','O001',99,'success'),('R002','O003',49,'success'),('R003','O003',49,'success'),
        ('R002','O003',49,'success'),('R004','UNKNOWN',10,'success'),('R005','O001',-10,'success'),
        ('R006','O002',300,'success'),('R007','O004',159,'pending'),('R008','O007',49,'success')]]
    if not (folder/'products.xlsx').exists():
        write_workbook(folder/'products.xlsx',{'商品':(list(products[0]),products)})
    if not (folder/'orders_1.csv').exists():
        pd.DataFrame(orders).to_csv(folder/'orders_1.csv',index=False,encoding='utf-8-sig')
    if not (folder/'orders_2.xlsx').exists():
        write_workbook(folder/'orders_2.xlsx',{'订单':(list(extras[0]),extras)})
    if not (folder/'refunds.csv').exists():
        pd.DataFrame(refunds).to_csv(folder/'refunds.csv',index=False,encoding='utf-8-sig')
    write_json(folder/'expected.json',dict(gross_sales=1500.0,order_count=6,refund_amount=197.0,
        net_sales=1303.0,units_sold=10,low_stock_count=3,exception_count=12,
        duplicate_orders_removed=1,duplicate_refunds_removed=1,excluded_orders=2,raw_order_rows=17))
    catalog=root/'catalog_bot/data'
    catalog.mkdir(parents=True,exist_ok=True)
    rows=[dict(name=n,sku=s,price=p,stock=q) for n,s,p,q in [
        ('舒适生活礼盒','SK001',299,8),('便携收纳包','SK002',99,40),('舒适生活礼盒','SK001',299,8),
        ('异常价格','BAD001',-1,5),('','BAD002',29,5),('异常库存','BAD003',29,'1.5'),
        ('重试演示商品','RETRY-001',49,3),('持续失败演示商品','FAIL-001',59,2),
        ('已有商品','PRE001',19,8),('超时演示商品','SLOW-001',69,2)]]
    if not (catalog/'products.xlsx').exists():
        write_workbook(catalog/'products.xlsx',{'商品':(list(rows[0]),rows)})
    write_json(catalog/'expected.json',dict(input_rows=10,created=3,duplicate_input=1,
        duplicate_existing=1,invalid=3,failed=2,attempted_browser_rows=6))


if __name__=='__main__':
    make()
    print('模拟数据已生成；已有源文件未覆盖。')
