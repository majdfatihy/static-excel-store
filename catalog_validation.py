"""Validate spreadsheet inputs before generating any storefront files."""
import math, re
from datetime import date, datetime
from urllib.parse import urlparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent

REQUIRED = {
    'Products': 'id name category description price sale_price stock images order date active keywords seo_title seo_description'.split(),
    'Categories': 'id name order home limit'.split(),
    'Settings': ['key','value'],
}
GOVERNORATES=set('القاهرة|الجيزة|الإسكندرية|الدقهلية|البحيرة|الشرقية|الغربية|المنوفية|كفر الشيخ|القليوبية|دمياط|بورسعيد|الإسماعيلية|السويس|شمال سيناء|جنوب سيناء|مطروح|الفيوم|بني سويف|المنيا|أسيوط|سوهاج|قنا|الأقصر|أسوان|البحر الأحمر|الوادي الجديد'.split('|'))
def val(v):return '' if v is None else str(v).strip()
def number(v,minimum=0,maximum=float('inf'),whole=False):
    if v is None or val(v)=='':return False
    try:
        n=float(v)
        return math.isfinite(n) and minimum<=n<=maximum and (not whole or n.is_integer())
    except (ValueError,TypeError):return False

def validate_catalog(w):
    errors=[]
    def read(sheet,required):
        if sheet not in w.sheetnames:
            errors.append(f'{sheet}: missing worksheet')
            return []
        rows=list(w[sheet].values)
        if not rows:
            errors.append(f'{sheet}: missing header')
            return []
        h=[val(x) for x in rows[0]]
        if len(set(x for x in h if x))!=len([x for x in h if x]):errors.append(f'{sheet}: duplicate column headers')
        missing=[x for x in required if x not in h]
        if missing:errors.append(f'{sheet}: missing columns {", ".join(missing)}')
        return [(i,dict(zip(h,row))) for i,row in enumerate(rows[1:],2) if any(val(x) for x in row)]
    p=read('Products',REQUIRED['Products']);c=read('Categories',REQUIRED['Categories']);s=read('Settings',REQUIRED['Settings'])
    seen=set();settings={}
    for i,r in s:
        key=val(r.get('key'))
        if not key or key in seen:errors.append(f'Settings!A{i}: blank or duplicate key {key}')
        seen.add(key);settings[key]=val(r.get('value'))
    for key in ['demo','show_offers','show_recommendations']:
        if key in settings and not number(settings[key],0,1,True):errors.append(f'Settings: {key} must be 0 or 1')
    for key,maximum in [('recommendation_limit',10),('offers_limit',100)]:
        if settings.get(key) and not number(settings[key],1,maximum,True):errors.append(f'Settings: {key} must be 1–{maximum}')
    if not number(settings.get('shipping','0')):errors.append('Settings: shipping must be nonnegative')
    if settings.get('payment_methods_en') and len(settings['payment_methods_en'].split('|'))!=len(settings.get('payment_methods','الدفع عند الاستلام').split('|')):errors.append('Settings: payment translations must match the original options')
    base=settings.get('base_url','')
    if base:
        u=urlparse(base)
        if u.scheme!='https' or not u.netloc or u.username or u.password or u.query or u.fragment:errors.append('Settings: invalid base_url')
    if settings.get('whatsapp') and not re.fullmatch(r'[1-9][0-9]{7,14}',settings['whatsapp']):errors.append('Settings: invalid whatsapp international number')
    if settings.get('telegram') and not re.fullmatch(r'@?[A-Za-z0-9_]{5,32}',settings['telegram']):errors.append('Settings: invalid telegram username')
    if not re.fullmatch('[A-Z]{3}',settings.get('currency','EGP')):errors.append('Settings: invalid currency code')
    if settings.get('demo')=='0' and (not base or not(settings.get('whatsapp') or settings.get('telegram'))):errors.append('Settings: live mode requires URL and contact')
    logo=settings.get('logo','')
    if logo:
        u=urlparse(logo)
        if not (re.fullmatch(r'assets/[a-zA-Z0-9_./-]+',logo) and '..' not in logo and (ROOT/'src'/logo).is_file() or u.scheme=='https' and u.netloc and not u.username and not u.password):errors.append('Settings: invalid logo URL or missing asset')
    cat_ids=set()
    for i,r in c:
        tag=f'Categories row {i}';k=val(r.get('id'))
        if not re.fullmatch('[a-z0-9][a-z0-9-]*',k) or k in cat_ids:errors.append(f'{tag}: invalid or duplicate id {k}')
        cat_ids.add(k)
        if not val(r.get('name')):errors.append(f'{tag}: name required')
        for key,lo,hi in [('order',0,float('inf')),('home',0,1),('limit',1,1000)]:
            if not number(r.get(key),lo,hi,True):errors.append(f'{tag}: invalid {key}')
        if val(r.get('recommendation_limit')) and not number(r['recommendation_limit'],1,10,True):errors.append(f'{tag}: recommendation_limit must be 1–10')
    product_ids=set()
    for i,r in p:
        tag=f'Products row {i}';k=val(r.get('id'))
        if not re.fullmatch('[a-z0-9][a-z0-9-]*',k) or k in product_ids:errors.append(f'{tag}: invalid or duplicate id {k}')
        product_ids.add(k)
        if val(r.get('category')) not in cat_ids:errors.append(f'{tag}: unknown category')
        if not val(r.get('name')):errors.append(f'{tag}: name required')
        if not number(r.get('price'),0.01):errors.append(f'{tag}: price must be positive')
        sale=r.get('sale_price')
        if val(sale) and (not number(sale) or (number(r.get('price'),0.01) and number(sale) and float(sale)>=float(r['price']))):errors.append(f'{tag}: invalid sale_price')
        for key,hi in [('stock',float('inf')),('order',float('inf')),('active',1)]:
            if not number(r.get(key),0,hi,True):errors.append(f'{tag}: invalid {key}')
        try:
            d=r.get('date')
            if not isinstance(d,(datetime,date)):date.fromisoformat(val(d))
        except (ValueError,TypeError):errors.append(f'{tag}: date must be YYYY-MM-DD')
        for image in val(r.get('images')).split('|'):
            image=image.strip()
            if not image:continue
            u=urlparse(image)
            if not (re.fullmatch(r'assets/[a-zA-Z0-9_./-]+',image) and '..' not in image and (ROOT/'src'/image).is_file() or u.scheme=='https' and u.netloc and not u.username and not u.password):errors.append(f'{tag}: invalid image URL {image}')
    for i,r in p:
        ids=[x.strip() for x in val(r.get('related_products')).split('|') if x.strip()]
        if len(ids)!=len(set(ids)) or any(k not in product_ids or k==val(r.get('id')) for k in ids):errors.append(f'Products row {i}: invalid related_products (unknown, duplicate, or self-reference)')
    shipping_seen=set()
    if 'Shipping' in w.sheetnames:
        for i,r in read('Shipping',['governorate','governorate_en','cost']):
            g=val(r.get('governorate'))
            if g not in GOVERNORATES or g in shipping_seen:errors.append(f'Shipping row {i}: invalid or duplicate governorate {g}')
            shipping_seen.add(g)
            if val(r.get('cost')) and not number(r.get('cost')):errors.append(f'Shipping row {i}: invalid cost')
    for pair in settings.get('shipping_by_governorate','').split('|'):
        if not pair.strip():continue
        g,sep,cost=pair.partition('=')
        if not sep or g.strip() not in GOVERNORATES or not number(cost):errors.append(f'Settings: invalid shipping entry {pair}')
    if errors:raise ValueError('Catalog validation failed:\n'+'\n'.join(errors))
    return {'products':len(p),'categories':len(c)}
