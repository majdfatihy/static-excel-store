"""Integration checks; run python -m unittest test_catalog from the repo."""
import json, tempfile, unittest, shutil, subprocess, sys
from pathlib import Path
from openpyxl import load_workbook
from catalog_validation import validate_catalog

ROOT=Path(__file__).resolve().parent

def set_setting(w,key,value):
    for row in w['Settings'].iter_rows(min_row=2):
        if row[0].value==key:
            row[1].value=value
            return
    w['Settings'].append([key,value])

class CatalogTests(unittest.TestCase):
    def test_actual_workbook(self):
        w=load_workbook(ROOT/'catalog.xlsx', data_only=True)
        result=validate_catalog(w)
        self.assertGreaterEqual(result['products'],0)
        self.assertGreaterEqual(result['categories'],0)
        for name in ['Products','Categories','Settings','Guide','Shipping']:
            self.assertIn(name,w.sheetnames)
        w.close()

    def test_invalid_price_and_duplicate(self):
        w=load_workbook(ROOT/'catalog.xlsx')
        p=w['Products']; headers={cell.value:cell.column for cell in p[1]}
        if p.max_row<2 or not p.cell(2,headers['id']).value:
            self.skipTest('No products to mutate')
        p.cell(2,headers['sale_price'],float(p.cell(2,headers['price']).value)+1)
        p.cell(3,headers['id'],p.cell(2,headers['id']).value)
        with self.assertRaisesRegex(ValueError,'invalid sale_price'):
            validate_catalog(w)
        w.close()

    def test_invalid_theme(self):
        w=load_workbook(ROOT/'catalog.xlsx')
        set_setting(w,'accent_light','red;unsafe')
        with self.assertRaisesRegex(ValueError,'accent_light'):
            validate_catalog(w)
        w.close()

    def test_full_build_and_safe_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            t=Path(folder)
            for f in ['build.py','catalog_validation.py','catalog.xlsx']:
                shutil.copy2(ROOT/f,t/f)
            shutil.copytree(ROOT/'src',t/'src')
            def run(*args):return subprocess.run([sys.executable,'build.py',*args],cwd=t,capture_output=True,text=True)
            result=run('--publish-root')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            original=(t/'dist/index.html').read_bytes()
            self.assertEqual(original,(t/'index.html').read_bytes())
            data=json.loads((t/'data.js').read_text(encoding='utf8').removeprefix('window.STORE=').removesuffix(';'))
            self.assertIn('products',data)
            w=load_workbook(t/'catalog.xlsx')
            ship=w['Shipping']; cairo=next((i for i in range(2,ship.max_row+1) if ship.cell(i,1).value=='القاهرة'),None)
            if cairo is None:ship.append(['القاهرة','Cairo',47])
            else:ship.cell(cairo,3,47)
            set_setting(w,'accent_light','#123456')
            set_setting(w,'policy_privacy_body','Test <privacy>')
            set_setting(w,'policy_privacy_body_en','Privacy test')
            w.save(t/'catalog.xlsx'); w.close()
            result=run()
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads((t/'dist/data.js').read_text(encoding='utf8').removeprefix('window.STORE=').removesuffix(';'))
            self.assertEqual(data['settings']['shipping_by_governorate']['القاهرة'],47)
            self.assertIn('--accent:#123456',(t/'dist/style.css').read_text(encoding='utf8'))
            self.assertIn('Test &lt;privacy&gt;',(t/'dist/privacy.html').read_text(encoding='utf8'))
            self.assertEqual(data['settings']['policy_translations']['Test <privacy>'],'Privacy test')
            safe=(t/'dist/index.html').read_bytes()
            w=load_workbook(t/'catalog.xlsx'); set_setting(w,'accent_dark','invalid'); w.save(t/'catalog.xlsx');w.close()
            self.assertNotEqual(run().returncode,0)
            self.assertEqual((t/'dist/index.html').read_bytes(),safe)

if __name__=='__main__':unittest.main()
