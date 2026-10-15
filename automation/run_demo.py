"""运行实测、保留真实浏览器截图与可复现测试数据。"""
import json
import sqlite3
import threading
from pathlib import Path
from make_samples import make
from shared import write_json
from ops_daily.pipeline import run as daily
from catalog_bot.server import make_server
from catalog_bot.robot import run as robot

ROOT=Path(__file__).resolve().parent


def run():
    make()
    ops=daily(ROOT/'ops_daily/data',ROOT/'ops_daily/outputs')
    # 演示运行保留旧数据库，以编号创建新文件，避免覆盖任何已有执行状态。
    state=ROOT/'catalog_bot/state'
    state.mkdir(exist_ok=True)
    number=1
    while (state/f'demo-{number}.sqlite').exists():number+=1
    db=state/f'demo-{number}.sqlite'
    server=make_server(db,0,True)
    with sqlite3.connect(db) as connection:
        connection.execute('INSERT INTO products VALUES(?,?,?,?)',('PRE001','已有商品',1900,8))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        catalog=robot(ROOT/'catalog_bot/data/products.xlsx',ROOT/'catalog_bot/outputs',url)
        repeat=robot(ROOT/'catalog_bot/data/products.xlsx',ROOT/'catalog_bot/outputs_repeat',url)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    expected=json.loads((ROOT/'ops_daily/data/expected.json').read_text())
    agreement=sum(ops[k]==v for k,v in expected.items())
    report=dict(ops=ops,catalog=catalog,repeat=repeat,
        ops_fixture_metric_agreement=f'{agreement}/{len(expected)}',
        note='固定模拟样例的指标对照结果，不代表真实业务准确率或人工效率提升；商品写入均通过真实浏览器表单。')
    write_json(ROOT/'evidence/demo_metrics.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':run()
