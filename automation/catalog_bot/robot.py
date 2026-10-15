"""真实浏览器操作：逐行填写表单、等待响应、核对列表、截图与有限重试。"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shared import read_table,write_json,write_workbook,logger_for
from catalog_bot.server import validate
from playwright.sync_api import sync_playwright,TimeoutError as BrowserTimeout,expect


def run(source,output,url='http://127.0.0.1:8877',retries=2,timeout_ms=1500,headless=True):
    output=Path(output)
    shots=output/'screenshots'
    shots.mkdir(parents=True,exist_ok=True)
    log=logger_for('catalog_bot',output)
    started=time.perf_counter()
    results=[]
    seen={}
    try:
        rows=read_table(source,['name','sku','price','stock'])
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=headless)
            context=browser.new_context(viewport={'width':1366,'height':900},locale='zh-CN')
            page=context.new_page()
            page.set_default_timeout(timeout_ms)
            for index,row in enumerate(rows,2):
                record=dict(row=index,sku=row['sku'],name=row['name'],status='',attempts=0,reason='',screenshot='')
                try:
                    product=validate(row)
                except ValueError as exc:
                    record.update(status='invalid',reason=str(exc))
                    results.append(record)
                    log.warning('输入校验失败 %s',record)
                    continue
                if product['sku'] in seen:
                    same=seen[product['sku']]==product
                    record.update(status='duplicate_input' if same else 'invalid',reason='输入中完全重复 SKU' if same else '输入中 SKU 内容冲突')
                    results.append(record)
                    continue
                seen[product['sku']]=product
                for attempt in range(1,retries+2):
                    record['attempts']=attempt
                    try:
                        page.goto(url,wait_until='networkidle',timeout=10000)
                        page.get_by_label('商品名称',exact=True).fill(product['name'])
                        page.get_by_label('SKU',exact=True).fill(product['sku'])
                        page.get_by_label('售价（元）',exact=True).fill(str(product['price']))
                        page.get_by_label('库存',exact=True).fill(str(product['stock']))
                        with page.expect_response(lambda response:response.url.endswith('/api/products') and response.request.method=='POST',timeout=timeout_ms) as saved:
                            page.get_by_role('button',name='保存商品').click()
                        response=saved.value
                        body=response.json()
                        if response.status==201:
                            expect(page.get_by_test_id('catalog-table').get_by_role('cell',name=product['sku'],exact=True)).to_be_visible()
                            expect(page.get_by_test_id('message')).to_have_text('保存成功')
                            record.update(status='created',reason='页面提交成功，列表核对通过')
                            break
                        if response.status==409 and body.get('same_payload'):
                            expect(page.get_by_test_id('message')).to_have_text('SKU 已存在，未重复写入')
                            record.update(status='duplicate_existing',reason='后台已有相同 SKU 与内容，跳过')
                            break
                        if response.status==409:
                            raise ValueError('已有 SKU 内容冲突，禁止覆盖')
                        if response.status<500:
                            raise ValueError(body.get('error','请求失败'))
                        raise RuntimeError(body.get('error','服务暂不可用'))
                    except ValueError as exc:
                        record.update(status='failed',reason=str(exc))
                        break
                    except (BrowserTimeout,RuntimeError,AssertionError) as exc:
                        record.update(status='failed',reason=f'{type(exc).__name__}: {str(exc)[:250]}')
                        log.warning('尝试 %s SKU=%s 失败: %s',attempt,product['sku'],record['reason'])
                        if attempt<=retries:
                            time.sleep(.2*attempt)
                if record['status']=='failed':
                    shot=shots/f'row-{index}-failed.png'
                    page.screenshot(path=str(shot),full_page=True)
                    record['screenshot']=str(shot.relative_to(output)).replace('\\','/')
                results.append(record)
                log.info('执行结果 %s',record)
            page.goto(url,wait_until='networkidle',timeout=10000)
            page.screenshot(path=str(shots/'catalog-final.png'),full_page=True)
            context.close()
            browser.close()
        fields=['row','sku','name','status','attempts','reason','screenshot']
        write_workbook(output/'批量执行结果.xlsx',{'执行结果':(fields,results)})
        write_json(output/'results.json',results)
        summary=dict(status='completed',input_rows=len(rows),counts=dict(Counter(r['status'] for r in results)),
                     elapsed_seconds=round(time.perf_counter()-started,6),dataset='synthetic',
                     browser='Microsoft Edge / Playwright',retries=retries)
        write_json(output/'metrics.json',summary)
        return summary
    except Exception as exc:
        log.exception('批次中断')
        write_json(output/'results.json',results)
        write_json(output/'metrics.json',dict(status='failed',error=str(exc)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=Path(__file__).parent/'data/products.xlsx')
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'outputs')
    parser.add_argument('--url',default='http://127.0.0.1:8877')
    parser.add_argument('--headed',action='store_true')
    args=parser.parse_args()
    print(run(args.input,args.output,args.url,headless=not args.headed))
