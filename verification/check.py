"""Real Edge acceptance, isolated databases and ephemeral ports. Requires playwright."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote, quote
from urllib.request import urlopen, Request
from concurrent.futures import ThreadPoolExecutor
import json, os, socket, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification'

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]

def ready(url):
    for _ in range(80):
        try:
            with urlopen(url,timeout=1) as r:
                if r.status==200:return
        except OSError:time.sleep(.1)
    raise RuntimeError(f'Server did not start: {url}')

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):self.ids.add(a['id'])
        if tag in ['a','img','link','script']:
            value=a.get('href') or a.get('src')
            if value:self.links.append(value)

def main():
    pages=[ROOT/'index.html',*sorted((ROOT/'projects').glob('*.html'))]
    resources=set();external=set();link_count=0
    for path in pages:
        source=path.read_text(encoding='utf-8');parser=Links();parser.feed(source)
        assert '简历' not in source and 'resume' not in source.lower() and '.docx' not in source,path
        for link in parser.links:
            url=urlparse(link)
            if url.scheme in ['https','http']:external.add(link);continue
            if url.scheme:continue
            assert link!='#'
            target=(path.parent/unquote(url.path)).resolve() if url.path else path
            assert target.is_relative_to(ROOT) and (target.is_file() or target==ROOT/'assets/device-desk.png'),(path,link)
            resources.add(target);link_count+=1
            if url.fragment:
                parser2=Links();parser2.feed(target.read_text(encoding='utf-8'))
                assert unquote(url.fragment) in parser2.ids,(path,link)
    assert not list((ROOT/'downloads').glob('*.pdf')) and not list((ROOT/'downloads').glob('*.docx'))
    def external_check(url):
        try:
            with urlopen(Request(url,headers={'User-Agent':'Portfolio-Link-Check'}),timeout=20) as r:return dict(url=url,status=r.status)
        except Exception as e:return dict(url=url,error=str(e))
    with ThreadPoolExecutor(max_workers=4) as pool:external_results=list(pool.map(external_check,sorted(external)))
    assert all(r.get('status')==200 for r in external_results), external_results
    errors=[];http_errors=[];checks=[];responsive=[];processes=[]
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    with tempfile.TemporaryDirectory(prefix='portfolio-qa-') as temp:
        log=open(Path(temp)/'services.log','w',encoding='utf-8')
        def launch(args,cwd,env=None):
            process=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=log,**flags);processes.append(process);return process
        try:
            site_port,app_port=free_port(),free_port()
            site=f'http://127.0.0.1:{site_port}/';url=f'http://127.0.0.1:{app_port}/'
            launch([sys.executable,'-m','http.server',str(site_port),'--bind','127.0.0.1'],ROOT)
            env={**os.environ,'PORT':str(app_port),'DB_PATH':str(Path(temp)/'state.sqlite')}
            server=launch(['node','server.js','--seed'],ROOT/'fullstack/device-desk',env)
            ready(site);ready(url+'api/health')
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='msedge',headless=True)
                app=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                app.on('pageerror',lambda e:errors.append(str(e)))
                def wait(message='数据已更新'):app.get_by_text(message,exact=True).wait_for()
                app.goto(url);wait();app.screenshot(path=str(ROOT/'assets/device-desk.png'),full_page=True)
                app.locator('#device-filter input').fill('不存在的设备');app.locator('#device-filter button').click()
                app.get_by_text('暂无匹配设备。可清除筛选或新增设备。').wait_for()
                app.locator('#device-filter input').fill('');app.locator('#device-filter button').click();app.get_by_text('筛选结果：3 台设备').wait_for()
                f=app.locator('#device-form')
                f.locator('[name=name]').fill('浏览器验收设备');f.locator('[name=code]').fill('SIM-BROWSER-04')
                f.locator('[name=temperature]').fill('28.5');f.locator('[name=humidity]').fill('55')
                f.get_by_role('button',name='保存设备',exact=True).click();wait('设备已保存')
                row=app.locator('#device-rows tr').filter(has_text='SIM-BROWSER-04')
                row.get_by_role('button',name='查看',exact=True).click();app.locator('dialog[open]').wait_for();app.keyboard.press('Escape')
                row.get_by_role('button',name='编辑',exact=True).click();f.locator('[name=name]').fill('浏览器验收设备（已修改）');f.locator('[name=status]').select_option('warning')
                f.get_by_role('button',name='保存设备',exact=True).click();wait('设备已保存');assert '已修改' in row.inner_text()
                app.once('dialog',lambda d:d.accept());row.get_by_role('button',name='删除',exact=True).click();wait();assert row.count()==0
                f.locator('[name=code]').fill('SIM-INVALID');f.get_by_role('button',name='保存设备',exact=True).click()
                assert f.locator('[name=name]').evaluate('(e)=>!e.validity.valid');app.locator('#cancel-edit').click()
                checks.extend(['设备表单增查改删','搜索空结果','前端必填校验','Escape 关闭设备详情'])
                ticket=app.locator('#ticket-form');ticket.locator('[name=device_id]').select_option(label='SIM-ESP32-01 · 环境采集节点（模拟）')
                ticket.locator('[name=title]').fill('浏览器验收异常');ticket.locator('[name=description]').fill('<script>window.bad=1</script>')
                ticket.get_by_role('button',name='创建工单',exact=True).click();wait('工单已创建')
                issue=app.locator('.ticket').filter(has_text='浏览器验收异常');assert app.evaluate('window.bad') is None
                issue.get_by_role('button',name='查看详情').click();app.locator('dialog[open]').wait_for();app.locator('#close-detail').click()
                issue.get_by_role('button',name='开始处理').click();wait();issue.get_by_role('button',name='关闭工单',exact=True).click();wait();assert '已关闭' in issue.inner_text()
                app.locator('#ticket-filter select').select_option('closed');app.locator('#ticket-filter button').click();app.get_by_text('筛选结果：1 条工单').wait_for()
                protected=app.locator('#device-rows tr').filter(has_text='SIM-ESP32-01');app.once('dialog',lambda d:d.accept())
                protected.get_by_role('button',name='删除',exact=True).click();app.locator('#error:not([hidden])').wait_for();assert '关联工单' in app.locator('#error').inner_text()
                checks.extend(['工单创建与详情','完整状态流转与筛选','关联设备删除保护','输入作为文本呈现'])
                server.terminate();server.wait(timeout=10)
                launch(['node','server.js'],ROOT/'fullstack/device-desk',env);ready(url+'api/health')
                app.reload();wait();assert '已关闭' in app.locator('.ticket').filter(has_text='浏览器验收异常').inner_text();checks.append('服务进程重启后工单保留')
                for width in [1440,768,390]:
                    app.set_viewport_size({'width':width,'height':1000});app.reload();wait()
                    assert app.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'app overflow {width}'
                    app.screenshot(path=str(OUT/f'app-{width}.png'),full_page=True)
                app.route('**/api/**',lambda r:r.abort());app.locator('#refresh').click();app.locator('#error:not([hidden])').wait_for();assert app.locator('#device-count').inner_text()=='—'
                app.unroute('**/api/**');app.locator('#refresh').click();wait();checks.append('服务异常提示与恢复刷新')
                empty_port=free_port();empty=f'http://127.0.0.1:{empty_port}/'
                launch(['node','server.js'],ROOT/'fullstack/device-desk',{**os.environ,'PORT':str(empty_port),'DB_PATH':str(Path(temp)/'empty.sqlite')})
                ready(empty+'api/health');app.goto(empty);wait();assert app.locator('#device-count').inner_text()=='0';assert '暂无匹配工单' in app.locator('#ticket-list').inner_text();checks.append('真实空库首次启动')
                for width in [1440,768,390]:
                    page=browser.new_page(viewport={'width':width,'height':1000},device_scale_factor=1)
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('response',lambda r:http_errors.append(dict(url=r.url,status=r.status)) if r.status>=400 else None)
                    for path in pages:
                        relative=path.relative_to(ROOT).as_posix();response=page.goto(site+relative,wait_until='networkidle');assert response.status==200
                        assert page.locator('h1').count()==1
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'{width}: {relative}'
                        for picture in page.locator('img').all():picture.scroll_into_view_if_needed()
                        page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
                        if relative=='index.html':
                            page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/f'home-{width}.png'),full_page=True)
                            for anchor in ['fullstack','automation','embedded','experience','skills','contact']:
                                page.locator(f'nav a[href="index.html#{anchor}"]').click();assert page.url.endswith('#'+anchor)
                            page.locator('#contact a[href="#about"]').click();assert page.url.endswith('#about')
                        responsive.append(dict(page=relative,width=width,status='passed'))
                    page.close()
                page=browser.new_page();page.goto(site+'projects/device-desk.html')
                with page.expect_download() as download:page.get_by_role('link',name='下载完整源码 ↓',exact=True).click()
                assert download.value.suggested_filename=='device-desk-source.zip'
                page.goto(site+'projects/ops-daily.html')
                with page.expect_download() as download:page.get_by_role('link',name='下载实际 Excel 结果',exact=True).click()
                assert download.value.suggested_filename.endswith('.xlsx')
                page.goto(site);page.keyboard.press('Tab');assert page.locator('.skip').evaluate('(e)=>e===document.activeElement')
                page.keyboard.press('Enter');assert page.url.endswith('#main');checks.extend(['源码 ZIP 与 Excel 实际下载','键盘跳至正文','导航与返回顶部'])
                browser.close()
            for resource in resources:
                with urlopen(site+quote(resource.relative_to(ROOT).as_posix())) as response:assert response.status==200
            assert not errors,errors
            assert not http_errors,http_errors
            result=dict(checked_at='2026-10-18',responsive_checks=responsive,app_widths=[1440,768,390],business_checks=checks,local_link_occurrences=link_count,local_resources=len(resources),external_links=external_results,javascript_errors=errors,http_errors=http_errors,resume_entry_check='passed')
            (OUT/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
        finally:
            for process in reversed(processes):
                if process.poll() is None:process.terminate();process.wait(timeout=10)
            log.close()

if __name__=='__main__':main()
