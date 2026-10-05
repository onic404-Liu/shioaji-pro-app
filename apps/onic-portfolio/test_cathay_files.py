import csv
import io
from pathlib import Path
import tempfile
import unittest
from cathay_files import CathayReader, FORMATS, read_snapshot

TW_HEADER = ['股票名稱','類別','庫存股數','持有成本','成交均價','現價','股票現值','未實現損益','預估報酬率','手續費','交易稅','幣別']
US_HEADER = ['市場別','股票名稱','現價','成交均價','今委賣','今買成','今賣成','可用庫存','目前庫存','庫存現值','幣別','庫存成本','投資損益','報酬率%(不含息)','參考含息報酬率']


def write_csv(path, rows, encoding='cp950'):
    stream=io.StringIO(newline='')
    csv.writer(stream).writerows(rows)
    path.write_bytes(stream.getvalue().encode(encoding))


class CathayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.tw=self.folder/FORMATS[0][2]
        self.us=self.folder/FORMATS[1][2]

    def test_cp950_footer_not_double_counted_and_source_is_unchanged(self):
        write_csv(self.tw,[TW_HEADER,['測試 A','現股','1000','10000','10','11','11000','1,000','10%','0','0','台幣'],[],['總計','0','1000','10000','10','11','11000','1000','10','0','0','台幣'],['未實現損益','1000']])
        before=self.tw.read_bytes()
        result=read_snapshot(self.tw,FORMATS[0])
        self.assertEqual(1,len(result['rows']))
        self.assertEqual(1000,result['totals'][0]['pnl'])
        self.assertEqual('TWD',result['totals'][0]['currency'])
        self.assertIsNone(result['snapshot_date'])
        self.assertEqual(before,self.tw.read_bytes())

    def test_currencies_and_decimal_totals_are_separate(self):
        write_csv(self.us,[US_HEADER,['美國','TEST A','10','9','0','0','0','1','1','10','美金','9','0.1','1','1'],['美國','TEST B','10','9','0','0','0','1','1','10','美金','9','0.2','2','2'],['香港','TEST C','10','9','0','0','0','1','1','10','港幣','9','-2','-2','-2']],encoding='utf-8-sig')
        result=read_snapshot(self.us,FORMATS[1])
        totals={t['currency']:t['pnl'] for t in result['totals']}
        self.assertEqual({'USD':0.3,'HKD':-2},totals)

    def test_missing_pnl_never_becomes_zero_total(self):
        write_csv(self.tw,[TW_HEADER,['測試 A','現股','1','10','10','10','10','--','--','0','0','台幣']])
        result=read_snapshot(self.tw,FORMATS[0])
        self.assertIsNone(result['totals'][0]['pnl'])

    def test_bad_update_retains_last_good_data_and_recovers(self):
        write_csv(self.tw,[TW_HEADER,['測試 A','現股','1','10','10','11','11','1','10','0','0','台幣']])
        reader=CathayReader(self.folder)
        good=reader.state()['sources'][0]
        self.tw.write_text('bad format',encoding='utf-8')
        failed=reader.state()['sources'][0]
        self.assertTrue(failed['stale'])
        self.assertEqual(good['rows'],failed['rows'])
        self.assertIsNotNone(failed['error'])
        self.tw.unlink()
        self.assertTrue(reader.state()['sources'][0]['stale'])
        write_csv(self.tw,[TW_HEADER])
        recovered=reader.state()['sources'][0]
        self.assertEqual([],recovered['rows'])
        self.assertFalse(recovered['stale'])
        self.assertIsNone(recovered['error'])

    def test_invalid_position_row_fails_entire_snapshot(self):
        write_csv(self.tw,[TW_HEADER,['測試 A','現股','not a quantity','10','10','10','10','0','0','0','0','台幣']])
        with self.assertRaises(ValueError):
            read_snapshot(self.tw,FORMATS[0])


if __name__=='__main__':
    unittest.main()
