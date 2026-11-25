"""Browser regression tests for the generated storefront; no external messages are sent."""
from pathlib import Path
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(root/'dist')))
Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}/'
data=json.loads((root/'dist/data.js').read_text(encoding='utf8').removeprefix('window.STORE=').removesuffix(';'))
products=data['products']
item=next((p for p in products if p['stock']>0),None)
try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        for width in (390,1280):
            ctx=browser.new_context(viewport={'width':width,'height':844},locale='ar-EG',color_scheme='dark')
            page=ctx.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base)
            page.locator('#language-toggle').wait_for()
            assert page.locator('#language-toggle').inner_text()=='AR'
            assert page.locator('html').get_attribute('data-theme')=='dark'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
            if item:
                page.locator('.search-toggle').click()
                page.locator('.search input').fill(item['name'])
                page.locator('.suggest a').first.wait_for()
                page.locator('.search-toggle').click()
                page.goto(base+'products/'+item['id']+'.html')
                page.locator('.detail [data-add]').click()
                drawer=page.locator('.cart-drawer')
                assert drawer.is_visible()
                assert page.locator('#count').inner_text()=='1'
                assert drawer.locator('.order-fold').get_attribute('open') is None
                assert drawer.locator('button[value=wa]').is_enabled()==bool(data['settings']['whatsapp'])
                drawer.locator('.order-fold summary').click()
                combo=drawer.locator('[role=combobox]')
                combo.fill('المنيا')
                drawer.locator('[role=option]').filter(has_text='المنيا').click()
                assert drawer.locator('select[name=governorate]').input_value()=='المنيا'
                drawer.locator('[data-close-drawer]').click()
                assert page.locator('.recommendations [data-add="'+item['id']+'"]').count()==0
            page.locator('#language-toggle').click()
            assert page.locator('html').get_attribute('dir')=='ltr'
            page.reload()
            page.locator('#language-toggle').wait_for()
            assert page.locator('#language-toggle').inner_text()=='EN'
            assert page.locator('#count').inner_text()==('1' if item else '0')
            assert not errors,errors
            print(f'PASS {width}px: search, cart, optional order, governorate, language, theme, recommendations')
            ctx.close()
        browser.close()
finally:
    server.shutdown()
