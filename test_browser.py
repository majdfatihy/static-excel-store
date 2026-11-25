from playwright.sync_api import sync_playwright
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import json
for f in Path('dist').rglob('*.html'):
 s=BeautifulSoup(f.read_text(),'html.parser');assert s.title and s.find('meta',attrs={'name':'description'});json.loads(s.find('script',type='application/ld+json').string)
 for a in s.select('a[href], img[src], script[src], link[href]'):
  v=(a.get('href') or a.get('src')).split('?')[0]
  if v and not v.startswith(('https:','http:','#')):assert (f.parent/v).exists(),(f,v)
print('21 HTML pages: metadata, JSON-LD syntax and internal paths pass')
server=subprocess.Popen(['python','-m','http.server','8765','--directory','dist'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 with sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1280,'height':800});errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  go=lambda path:page.goto('http://127.0.0.1:8765/'+path)
  go('index.html');page.locator('[data-add="p01"]').first.click();assert page.locator('#count').inner_text()=='1';page.locator('[data-add="p03"]').first.click();assert page.locator('#count').inner_text()=='2'
  go('products/p01.html');assert page.locator('#count').inner_text()=='2';page.locator('[data-add]').click();assert page.locator('#count').inner_text()=='3'
  go('cart.html');assert page.locator('.cart-row').count()==2;page.locator('[data-qty="p01"]').fill('3');page.locator('[data-qty="p01"]').press('Tab');assert page.locator('#count').inner_text()=='4';page.reload();assert page.locator('#count').inner_text()=='4'
  page.locator('[name=name]').fill('اختبار');page.locator('[name=governorate]').select_option('المنيا');page.locator('[name=phone]').fill('01000000000');page.locator('[name=address]').fill('عنوان تجريبي');page.locator('button[value=wa]').click();assert 'تجريبي' in page.locator('#order-note').inner_text()
  go('products.html');page.locator('#filter-q').fill('ماوس');assert page.locator('#grid .product').count()==1;page.locator('#filter-q').fill('');page.locator('#sort').select_option('low');assert 'حامل هاتف' in page.locator('#grid .product').first.inner_text();page.locator('#max').fill('200');assert page.locator('#grid .product').count()==3
  page.locator('#theme').click();t=page.locator('html').get_attribute('data-theme');page.reload();assert page.locator('html').get_attribute('data-theme')==t
  go('index.html');page.locator('.search input').fill('سا');assert page.locator('.suggest a').count()>=1
  page.set_viewport_size({'width':390,'height':844});go('index.html');assert page.evaluate('document.documentElement.scrollWidth <= innerWidth');page.screenshot(path='/mnt/data/store-mobile-preview.png')
  assert not errs,errs
  print('PASS: cart, persistence, quantity, demo checkout, search, price filters, sorting, theme, mobile viewport; no page errors');b.close()
finally:server.terminate()
