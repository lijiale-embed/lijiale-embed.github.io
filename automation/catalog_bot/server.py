"""商品后台：SQLite 唯一 SKU；演示故障只能用 --test-mode 显式开启。"""
import argparse
import json
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shared import amount, integer

PAGE=Path(__file__).with_name('index.html')


def validate(row):
    name,sku=str(row.get('name','')).strip(),str(row.get('sku','')).strip()
    if not name or not sku:
        raise ValueError('商品名称、SKU 必填')
    if len(name)>120 or len(sku)>64:
        raise ValueError('名称或 SKU 过长')
    cents=amount(row.get('price',''))
    if cents<=0:
        raise ValueError('售价必须大于 0')
    stock=integer(row.get('stock',''))
    return dict(name=name,sku=sku,price=cents/100,stock=stock)


def make_server(db, port=8877, test_mode=False):
    db=Path(db)
    db.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY,name TEXT NOT NULL,price_cents INTEGER NOT NULL,stock INTEGER NOT NULL)')
    attempts={}
    lock=threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):
            pass

        def send(self,value,status=200,html=False):
            body=value.encode('utf-8') if html else json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
                pass

        def do_GET(self):
            if self.path=='/':
                return self.send(PAGE.read_text(encoding='utf-8'),html=True)
            if self.path=='/health':
                return self.send(dict(status='ok',test_mode=test_mode))
            if self.path=='/api/products':
                with sqlite3.connect(db) as connection:
                    rows=connection.execute('SELECT sku,name,price_cents,stock FROM products ORDER BY sku').fetchall()
                return self.send([dict(sku=s,name=n,price=p/100,stock=q) for s,n,p,q in rows])
            self.send(dict(error='未找到页面'),404)

        def do_POST(self):
            if self.path!='/api/products':
                return self.send(dict(error='未找到接口'),404)
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://{self.headers.get("Host")}':
                return self.send(dict(error='不允许跨站写入'),403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length>8192:
                    return self.send(dict(error='请求过大'),413)
                payload=json.loads(self.rfile.read(length))
                if not isinstance(payload,dict):
                    raise ValueError('商品数据必须为对象')
                product=validate(payload)
                sku=product['sku']
                if test_mode:
                    with lock:
                        attempts[sku]=attempts.get(sku,0)+1
                        count=attempts[sku]
                    if sku=='FAIL-001' or (sku=='RETRY-001' and count==1):
                        return self.send(dict(error='演示模式：暂时无法保存，请重试'),503)
                    if sku=='SLOW-001':
                        time.sleep(2)
                        return self.send(dict(error='演示模式：处理超时，未写入'),503)
                with sqlite3.connect(db,timeout=5) as connection:
                    try:
                        connection.execute('INSERT INTO products VALUES(?,?,?,?)',
                            (sku,product['name'],amount(product['price']),product['stock']))
                    except sqlite3.IntegrityError:
                        existing=connection.execute('SELECT name,price_cents,stock FROM products WHERE sku=?',(sku,)).fetchone()
                        same=existing==(product['name'],amount(product['price']),product['stock'])
                        return self.send(dict(error='SKU 已存在，未重复写入',same_payload=same),409)
                return self.send(dict(status='created',product=product),201)
            except (ValueError,TypeError) as exc:
                return self.send(dict(error=str(exc)),400)
            except sqlite3.Error:
                return self.send(dict(error='存储暂不可用'),503)

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=Path(__file__).parent/'state/catalog.sqlite')
    parser.add_argument('--port',type=int,default=8877)
    parser.add_argument('--test-mode',action='store_true')
    args=parser.parse_args()
    httpd=make_server(args.db,args.port,args.test_mode)
    print(f'商品后台 http://127.0.0.1:{httpd.server_port} test_mode={args.test_mode}',flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
