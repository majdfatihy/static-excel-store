"""Browser regression tests for the generated storefront; no external messages are sent."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(root/'dist')))
Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}/'
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
            page.locator('.search-toggle').click()
            page.locator('.search input').fill('سماعة')
            page.locator('.suggest a').first.wait_for()
            page.locator('.search-toggle').click()
            page.locator('[data-add="p01"]').first.click()
            drawer=page.locator('.cart-drawer')
            assert drawer.is_visible()
            assert page.locator('#count').inner_text()=='1'
            assert not drawer.locator('.order-fold').get_attribute('open')
            assert drawer.locator('button[value=wa]').is_enabled()
            drawer.locator('.order-fold summary').click()
            combo=drawer.locator('[role=combobox]')
            combo.fill('المنيا')
            drawer.locator('[role=option]').filter(has_text='المنيا').click()
            assert drawer.locator('select[name=governorate]').input_value()=='المنيا'
            drawer.locator('[data-close-drawer]').click()
            page.locator('#language-toggle').click()
            assert page.locator('html').get_attribute('dir')=='ltr'
            page.reload()
            assert page.locator('#language-toggle').inner_text()=='EN'
            assert page.locator('#count').inner_text()=='1'
            page.goto(base+'products/p01.html')
            assert page.locator('.recommendations section').count()==3
            assert page.locator('.recommendations [data-add=p01]').count()==0
            assert not errors,errors
            print(f'PASS {width}px: search, cart, optional order, governorate, language, theme, recommendations')
            ctx.close()
        browser.close()
finally:
    server.shutdown()
