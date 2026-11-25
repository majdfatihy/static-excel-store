from pathlib import Path
import json, re, html, shutil, sys, math, hashlib
from urllib.parse import urlparse
from openpyxl import load_workbook
from datetime import date
ROOT=Path(__file__).resolve().parent
E=lambda x:html.escape(str(x),quote=True)
def rows(w,s):
    data=list(w[s].values); return [dict(zip(data[0],r)) for r in data[1:] if any(v is not None for v in r)]
def text(v): return str(v or '').strip()
def slug(v):
    v=text(v)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',v): raise ValueError(f'Invalid ID: {v}')
    return v
def num(v):
    n=float(v or 0)
    if not math.isfinite(n) or n<0: raise ValueError(f'Invalid number {v}')
    return n
def integer(v):
    n=num(v)
    if int(n)!=n: raise ValueError(f'Invalid integer {v}')
    return int(n)
def flag(v):
    n=integer(v)
    if n not in (0,1): raise ValueError(f'Invalid flag {v}')
    return bool(n)
def safe_url(v):
    v=text(v); p=urlparse(v)
    if re.fullmatch(r'assets/[a-zA-Z0-9_./-]+',v) and '..' not in v and (ROOT/'src'/v).is_file(): return v
    if p.scheme=='https' and p.netloc and not p.username and not p.password: return v
    raise ValueError(f'Invalid image URL {v}')
def safe_json(x): return json.dumps(x,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
def build(publish_root=False):
    w=load_workbook(ROOT/'catalog.xlsx',read_only=True,data_only=True)
    s={text(r['key']):text(r['value']) for r in rows(w,'Settings')}; base=s.get('base_url','').rstrip('/')
    if base and (urlparse(base).scheme!='https' or not urlparse(base).netloc or urlparse(base).query or urlparse(base).fragment): raise ValueError('base_url must be an HTTPS website URL')
    demo=flag(s.get('demo',1)); name=s.get('name') or 'المتجر'; currency=s.get('currency','EGP')
    if not re.fullmatch('[A-Z]{3}',currency): raise ValueError('Currency must be 3 uppercase letters')
    wa=s.get('whatsapp',''); tg=s.get('telegram','').lstrip('@')
    if wa and not re.fullmatch(r'[1-9][0-9]{7,14}',wa): raise ValueError('Invalid WhatsApp number')
    if tg and not re.fullmatch(r'[A-Za-z0-9_]{5,32}',tg): raise ValueError('Invalid Telegram username')
    if not demo and (not base or not(wa or tg)): raise ValueError('Live mode needs base URL and order destination')
    if not s.get('description'): s['description']='تصفح المنتجات والعروض حسب التصنيف والسعر، واختر ما يناسبك.'
    cats=[]; ids=set()
    for r in rows(w,'Categories'):
        k=slug(r['id'])
        if k in ids or not text(r['name']): raise ValueError('Duplicate or blank category')
        ids.add(k); cats.append(dict(id=k,name=text(r['name']),order=integer(r['order']),home=flag(r['home']),limit=max(1,integer(r['limit']))))
    cats.sort(key=lambda x:x['order']); products=[]; seen=set()
    for r in rows(w,'Products'):
        k=slug(r['id']); c=slug(r['category']); price=num(r['price']); sale=num(r['sale_price']); n=text(r['name'])
        if k in seen or c not in ids or not n or not price or (sale and sale>=price): raise ValueError(f'Invalid product {k}')
        seen.add(k); images=[safe_url(x) for x in text(r['images']).split('|') if x.strip()]
        if not images: images=['assets/placeholder.svg']
        day=r['date']; day=day.date().isoformat() if hasattr(day,'date') else text(day); date.fromisoformat(day)
        if flag(r['active']): products.append(dict(id=k,name=n,category=c,description=text(r['description']).replace(' - منتج تجريبي لعرض خصائص المتجر.',''),price=price,sale_price=sale,stock=integer(r['stock']),images=images,order=integer(r['order']),date=day,keywords=text(r['keywords']),seo_title=text(r['seo_title']) or f'{n} | {name}',seo_description=text(r['seo_description']) or text(r['description']) or f'{n} | {name}'))
    products.sort(key=lambda p:p['order']); out=ROOT/'dist'
    # validation before replacing output
    if out.exists(): shutil.rmtree(out)
    out.mkdir(); shutil.copytree(ROOT/'src'/'assets',out/'assets'); shutil.copy(ROOT/'src'/'app.js',out/'app.js'); shutil.copy(ROOT/'src'/'style.css',out/'style.css')
    payment=[x.strip() for x in s.get('payment_methods','الدفع عند الاستلام').split('|') if x.strip()]
    shipping_by_governorate={}
    for pair in s.get('shipping_by_governorate','').split('|'):
        if pair.strip():
            g,v=pair.split('=',1); shipping_by_governorate[g.strip()]=num(v)
    config=dict(name=name,currency=currency,whatsapp=wa,telegram=tg,shipping=num(s.get('shipping')),shipping_by_governorate=shipping_by_governorate,demo=demo,payment_methods=payment)
    (out/'data.js').write_text('window.STORE='+safe_json(dict(settings=config,categories=cats,products=products))+';',encoding='utf8')
    rev=hashlib.sha256(b''.join((out/f).read_bytes() for f in ('style.css','data.js','app.js'))).hexdigest()[:12]
    paths=[]
    def page(path,title,desc,body,kind='WebPage',product=None):
        prefix='../'*(path.count('/')); canonical=base+('/' if path=='index.html' else '/'+path) if base else ''; url=lambda v: (base+'/'+v if base and not v.startswith('https://') else v)
        logo=s.get('logo',''); brand=f'<img class="logo" src="{E(prefix+logo if logo.startswith("assets/") else logo)}" alt="{E(name)}">' if logo else E(name)
        nav=''.join(f'<a href="{prefix}categories/{c["id"]}.html">{E(c["name"])}</a>' for c in cats)
        policies={'privacy':'الخصوصية','terms':'الشروط','shipping':'الشحن','returns':'الاسترجاع','contact':'اتصل بنا'}
        foot=''.join(f'<a href="{prefix}{k}.html">{v}</a>' for k,v in policies.items())
        schema={'@context':'https://schema.org','@type':kind,'name':title,'description':desc}
        if canonical:schema['url']=canonical
        if product:
            schema.update(name=product['name'],image=[url(i) for i in product['images']],sku=product['id'],offers={'@type':'Offer','priceCurrency':currency,'price':product['sale_price'] or product['price'],'availability':'https://schema.org/'+('InStock' if product['stock'] else 'OutOfStock')})
        if product and canonical:schema['offers']['url']=canonical
        meta=f'<meta name="description" content="{E(desc[:160])}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc[:160])}"><meta property="og:type" content="{"product" if product else "website"}"><meta name="twitter:card" content="summary_large_image">'
        if canonical: meta+=f'<link rel="canonical" href="{E(canonical)}"><meta property="og:url" content="{E(canonical)}">'
        if product:meta+=f'<meta property="og:image" content="{E(url(product["images"][0]))}"><meta name="twitter:image" content="{E(url(product["images"][0]))}">'
        if demo or path=='cart.html':meta+='<meta name="robots" content="noindex,follow">'
        banner=''
        output=f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)}</title>{meta}<script type="application/ld+json">{safe_json(schema)}</script><link rel="stylesheet" href="{prefix}style.css?v={rev}"><script defer src="{prefix}data.js?v={rev}"></script><script defer src="{prefix}app.js?v={rev}"></script></head><body data-root="{prefix}">{banner}<header><div class="top"><a class="brand" href="{prefix}index.html">{brand}</a><form class="search" action="{prefix}products.html"><input name="q" aria-label="بحث المنتجات" placeholder="ابحث عن منتج…" autocomplete="off"><button>بحث</button><div class="suggest" hidden></div></form><button id="theme" aria-label="تغيير المظهر">المظهر</button><a class="cart" href="{prefix}cart.html">السلة <span id="count">0</span></a></div><nav><a href="{prefix}index.html">الرئيسية</a><a href="{prefix}products.html">كل المنتجات</a>{nav}</nav></header><main>{body}</main><footer><b>{E(name)}</b><div>{foot}</div></footer><div id="toast" role="status"></div></body></html>'
        f=out/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(output,encoding='utf8');paths.append(path)
    def card(p,prefix=''):
        price=p['sale_price'] or p['price']; img=p['images'][0]; img=prefix+img if img.startswith('assets/') else img
        old=f'<del>{p["price"]:g} {currency}</del>' if p['sale_price'] else ''; disabled='disabled' if not p['stock'] else ''
        return f'<article class="product"><a href="{prefix}products/{p["id"]}.html"><img loading="lazy" src="{E(img)}" alt="{E(p["name"])}" width="400" height="400"><h3>{E(p["name"])}</h3></a><div class="price">{price:g} {currency} {old}</div><div class="buy"><input aria-label="الكمية" type="number" min="1" max="{p["stock"]}" value="1" {disabled}><button data-add="{p["id"]}" {disabled}>{"أضف للسلة" if p["stock"] else "غير متوفر"}</button></div></article>'
    def section(title,items,link):return f'<section><div class="section-head"><h2>{E(title)}</h2><a href="{link}">عرض الكل ←</a></div><div class="rail">'+''.join(card(p) for p in items)+'</div></section>'
    home=f'<div class="hero"><div><p class="eyebrow">تجربة تسوق بسيطة</p><h1>{E(s.get("headline","تسوق بسهولة"))}</h1><p>{E(s.get("description",""))}</p><a class="cta" href="products.html">تصفح المنتجات</a></div><div class="hero-mark" aria-hidden="true">◈</div></div>'
    sale=[p for p in products if p['sale_price']]
    if sale:home+=section('العروض والخصومات',sale[:6],'products.html?sale=1')
    for c in cats:
        if c['home']:home+=section(c['name'],[p for p in products if p['category']==c['id']][:c['limit']],f'categories/{c["id"]}.html')
    page('index.html',name,s.get('description',''),home,'WebSite')
    filters='<div class="filters"><label>البحث<input id="filter-q" placeholder="اسم المنتج"></label><label>من<input id="min" type="number" min="0"></label><label>إلى<input id="max" type="number" min="0"></label><label>الترتيب<select id="sort"><option value="order">الافتراضي</option><option value="low">الأقل سعراً</option><option value="high">الأعلى سعراً</option><option value="new">الأحدث</option><option value="old">الأقدم</option></select></label><label>التصنيف<select id="category"><option value="">الكل</option>'+''.join(f'<option value="{c["id"]}">{E(c["name"])}</option>' for c in cats)+'</select></label></div>'
    def listing(title,items,prefix='',category=''):return f'<h1>{E(title)}</h1><div id="listing" data-category="{category}">{filters}<p id="results"></p><div id="grid" class="grid">'+''.join(card(p,prefix) for p in items[:12])+'</div><button id="more" hidden>عرض المزيد</button></div>'
    page('products.html','كل المنتجات | '+name,'تصفح وابحث في جميع المنتجات',listing('كل المنتجات',products),'CollectionPage')
    for c in cats:page(f'categories/{c["id"]}.html',c['name']+' | '+name,'تصفح منتجات '+c['name'],listing(c['name'],[p for p in products if p['category']==c['id']],'../',c['id']),'CollectionPage')
    for p in products:
        prefix='../'; imgs=''.join(f'<img loading="lazy" alt="{E(p["name"])}" src="{E(prefix+i if i.startswith("assets/") else i)}" width="400" height="400">' for i in p['images'])
        page(f'products/{p["id"]}.html',p['seo_title'],p['seo_description'],f'<a href="../categories/{p["category"]}.html">العودة للتصنيف</a><div class="detail"><div class="gallery">{imgs}</div><div><h1>{E(p["name"])}</h1><p>{E(p["description"])}</p><p class="price">{p["sale_price"] or p["price"]:g} {currency}</p><p>{"متوفر" if p["stock"] else "غير متوفر"}</p><div class="buy"><input type="number" min="1" max="{p["stock"]}" value="1" aria-label="الكمية"><button data-add="{p["id"]}" {"disabled" if not p["stock"] else ""}>أضف للسلة</button></div><button data-share>مشاركة الرابط</button></div></div>','Product',p)
    gov='القاهرة|الجيزة|الإسكندرية|الدقهلية|البحيرة|الشرقية|الغربية|المنوفية|كفر الشيخ|القليوبية|دمياط|بورسعيد|الإسماعيلية|السويس|شمال سيناء|جنوب سيناء|مطروح|الفيوم|بني سويف|المنيا|أسيوط|سوهاج|قنا|الأقصر|أسوان|البحر الأحمر|الوادي الجديد'.split('|')
    page('cart.html','السلة | '+name,'مراجعة المنتجات والطلب','<h1>سلة التسوق</h1><div class="checkout"><div id="cart-items"></div><form id="order"><h2>بيانات الطلب</h2><label>الاسم<input name="name" required maxlength="100"></label><label>المحافظة<select name="governorate" required><option value="">اختر المحافظة</option>'+''.join(f'<option>{g}</option>' for g in gov)+'</select></label><label>الهاتف<input name="phone" type="tel" required pattern="[+0-9\\s\\(\\)\\-]{8,20}"></label><label>العنوان<textarea name="address" required maxlength="300"></textarea></label><label>طريقة الدفع<select name="payment">'+''.join(f'<option>{E(x)}</option>' for x in config['payment_methods'])+'</select></label><p id="total"></p><button value="wa">إرسال عبر واتساب</button><button value="tg">إرسال عبر تيليجرام</button><p id="order-note" role="status"></p></form></div>')
    for k,v in {'privacy':('سياسة الخصوصية','تُحفظ السلة في بيانات الموقع بالمتصفح. عند إرسال الاستفسار أو الطلب، تنتقل البيانات إلى خدمة التواصل المختارة وفق سياسة الخصوصية الخاصة بها.'),'terms':('الشروط والأحكام','تخضع الطلبات للتأكيد من صاحب المتجر؛ الأسعار والتوفر قابلان للمراجعة.'),'shipping':('الشحن والتوصيل','يؤكد صاحب المتجر مدة الشحن وتكلفته النهائية قبل إتمام الطلب.'),'returns':('الاسترجاع والاستبدال','استفسر عن شروط الاسترجاع والاستبدال قبل تأكيد الطلب، مع مراعاة حقوق المستهلك المقررة قانوناً.'),'contact':('اتصل بنا','للاستفسار تواصل مع صاحب المتجر عبر قنوات الطلب المتاحة.')}.items():page(k+'.html',v[0]+' | '+name,v[1],f'<h1>{v[0]}</h1><p>{v[1]}</p>')
    (out/'robots.txt').write_text('User-agent: *\nAllow: /\n'+('Sitemap: '+base+'/sitemap.xml\n' if base and not demo else ''))
    (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+(''.join(f'<url><loc>{E(base+("/" if p=="index.html" else "/"+p))}</loc></url>' for p in paths if p!='cart.html') if base else '')+'</urlset>',encoding='utf8')
    if publish_root:
        for folder in ('assets','products','categories'):
            target=ROOT/folder
            if target.exists(): shutil.rmtree(target)
            if (out/folder).exists(): shutil.copytree(out/folder,target)
        for file in out.iterdir():
            if file.is_file(): shutil.copy2(file,ROOT/file.name)
        (ROOT/'.nojekyll').touch()
    print(f'Generated {len(paths)} pages, {len(products)} products, {len(cats)} categories.')
if __name__=='__main__':
    try:build('--publish-root' in sys.argv)
    except Exception as e: print('Build failed:',e);sys.exit(1)
