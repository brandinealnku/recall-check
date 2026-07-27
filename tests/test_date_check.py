import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

def node(expression):
    script = "const d=require('./date-check.js'); const value=(" + expression + "); console.log(JSON.stringify(value));"
    return json.loads(subprocess.check_output(['node','-e',script], cwd=ROOT, text=True))

class DateCheckTests(unittest.TestCase):
    def test_upc_has_no_date(self):
        result=node("d.normalizeScanResult('012345678905','UPC_A',{today:new Date(2026,6,27)})")
        self.assertEqual(result['gtin'],'012345678905'); self.assertFalse(result['containsEncodedDate'])
    def test_parenthesized_gs1(self):
        result=node("d.parseGS1('(01)09501101530003(10)LOT7(17)270730',{today:new Date(2026,6,27)})")
        self.assertEqual(result['gtin'],'09501101530003'); self.assertEqual(result['lotNumber'],'LOT7'); self.assertEqual(result['expirationDate'],'2027-07-30')
    def test_group_separator_and_all_dates(self):
        result=node("d.parseGS1('010950110153000310LOT\\u001d112607271326072715270731162607301727073021SER',{today:new Date(2026,6,27)})")
        self.assertEqual(result['productionDate'],'2026-07-27'); self.assertEqual(result['packagingDate'],'2026-07-27'); self.assertEqual(result['bestBeforeDate'],'2027-07-31'); self.assertEqual(result['sellByDate'],'2026-07-30'); self.assertEqual(result['expirationDate'],'2027-07-30'); self.assertEqual(result['serialNumber'],'SER')
    def test_digital_link(self):
        result=node("d.parseGS1('https://id.gs1.org/01/09501101530003?17=270730&10=ABC',{today:new Date(2026,6,27)})")
        self.assertEqual(result['expirationDate'],'2027-07-30'); self.assertEqual(result['lotNumber'],'ABC')
    def test_malformed_and_no_false_date(self):
        self.assertTrue(node("d.parseGS1('(17)261332',{today:new Date(2026,6,27)}).parseWarnings.length>0"))
        self.assertEqual(node("d.parseGS1('012345678905',{today:new Date(2026,6,27)}).expirationDate"),'')
    def test_day_zero_and_ambiguity(self):
        self.assertEqual(node("d.parseGS1Date('270200',{today:new Date(2026,6,27),allowDayZero:true}).iso"),'2027-02-28')
        self.assertTrue(node("d.parseGS1Date('760101',{today:new Date(2026,0,1)}).ambiguous"))
    def test_date_only_evaluation(self):
        expr="['2024-02-29','2026-12-31','2027-01-01'].map(x=>d.compareDateOnly(x,new Date(2026,11,31,23,59)))"
        self.assertEqual(node(expr),['past','today','future'])
    def test_semantics(self):
        best=node("d.evaluateDate({date:'2020-01-01',type:'best_before',source:'manual',today:new Date(2026,0,1)})")
        self.assertEqual(best['status'],'printed_date_past'); self.assertIn('quality',best['meaning'].lower()); self.assertNotIn('danger',json.dumps(best).lower())
        prod=node("d.evaluateDate({date:'2020-01-01',type:'production',source:'encoded',today:new Date(2026,0,1)})")
        self.assertEqual(prod['status'],'production_or_packaging_date')
    def test_recall_priority(self):
        text=node("d.combinedSummary('confirmed_current_recall',d.evaluateDate({date:'2099-01-01',type:'expiration'}))")
        self.assertIn('Do not use',text)
    def test_privacy_static(self):
        source=(ROOT/'app.js').read_text()
        self.assertNotIn('localStorage',source); self.assertNotIn('sessionStorage',source)
        self.assertNotRegex(source,r'api[_-]?key|tesseract|ocr.*fetch')
