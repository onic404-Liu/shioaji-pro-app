"""Read-only Cathay position snapshots. No copies, exchange rates or broker login."""
import csv
from decimal import Decimal, InvalidOperation
import io
import os
from pathlib import Path
import time

FORMATS = (
    ('tw', '國泰台股', '國泰未實現損益.csv', '庫存股數', '持有成本', '股票現值', '未實現損益', '預估報酬率'),
    ('overseas', '國泰複委託', '國泰 複委託 未實現損益.csv', '目前庫存', '庫存成本', '庫存現值', '投資損益', '報酬率%(不含息)'),
)
CURRENCIES = {'台幣':'TWD','新台幣':'TWD','美金':'USD','美元':'USD','港幣':'HKD','日圓':'JPY','日幣':'JPY','人民幣':'CNY','歐元':'EUR','英鎊':'GBP'}
FOOTER_LABELS = {'未實現損益','投資損益','持有成本','融資金額','庫存股數','股票名稱'}


def numeric(value):
    text = str(value).strip().replace(',', '').replace('%', '').replace('−', '-')
    if text in ('', '-', '--', '—', 'N/A'):
        return None
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        number = Decimal(text)
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def default_folder():
    configured = os.environ.get('ONIC_CATHAY_DIR')
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / '投資對帳單' / '國泰證券' / '未實現損益'
        if candidate.is_dir():
            return candidate
    return Path.home() / '投資對帳單' / '國泰證券' / '未實現損益'


def read_snapshot(path, spec):
    kind, label, filename, qty, cost, value, pnl, rate = spec
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'cp950'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('不支援的檔案編碼')
    records = list(csv.reader(io.StringIO(text)))
    required = {'股票名稱','幣別',qty,cost,value,pnl,rate,'現價','成交均價'}
    start = next((i for i, row in enumerate(records[:10]) if required <= {c.strip() for c in row}), None)
    if start is None:
        raise ValueError('檔案欄位不符合國泰格式')
    header = [c.strip() for c in records[start]]
    rows, totals, ignored = [], {}, 0
    for cells in records[start+1:]:
        cells = [c.strip() for c in cells]
        if not cells or not any(cells):
            continue
        if any(c in FOOTER_LABELS for c in cells) or any(c.startswith(('合計','總計','小計')) for c in cells[:2]):
            ignored += 1
            continue
        if len(cells) != len(header):
            raise ValueError('持倉列欄位數不符')
        data = dict(zip(header, cells))
        quantity = numeric(data[qty])
        if not data['股票名稱'] or quantity is None or quantity < 0:
            raise ValueError('持倉名稱或股數不完整')
        currency = CURRENCIES.get(data['幣別'], data['幣別'].upper()) or '未標示'
        amount = numeric(data[pnl])
        row = {'name':data['股票名稱'], 'kind':kind, 'market':data.get('市場別', data.get('類別','')),
               'currency':currency, 'quantity':float(quantity), 'pnl':float(amount) if amount is not None else None}
        for key, field in (('cost',cost),('market_value',value),('price','現價'),('average','成交均價'),('return_pct',rate)):
            parsed = numeric(data[field])
            row[key] = float(parsed) if parsed is not None else None
        rows.append(row)
        bucket = totals.setdefault(currency, {'pnl':Decimal(0), 'count':0, 'complete':True})
        bucket['count'] += 1
        if amount is None or currency == '未標示':
            bucket['complete'] = False
        else:
            bucket['pnl'] += amount
    summaries = [{'currency':currency, 'count':b['count'], 'pnl':float(b['pnl']) if b['complete'] else None}
                 for currency,b in sorted(totals.items())]
    return {'kind':kind, 'label':label, 'file':filename, 'encoding':encoding,
            'snapshot_date':None, 'modified_at':path.stat().st_mtime, 'loaded_at':time.time(),
            'rows':rows, 'totals':summaries, 'ignored_summary_rows':ignored, 'error':None, 'stale':False}


class CathayReader:
    def __init__(self, folder=None, enabled=True):
        self.folder = Path(folder) if folder is not None else default_folder()
        self.enabled = enabled
        self.cache = {}
        self.signatures = {}

    def state(self):
        if not self.enabled:
            return {'sources':[], 'fixture':True}
        result = []
        for spec in FORMATS:
            kind,label,filename,*_ = spec
            path = self.folder / filename
            try:
                stat = path.stat()
                signature = (stat.st_mtime_ns, stat.st_size)
                if signature != self.signatures.get(kind):
                    self.cache[kind] = read_snapshot(path,spec)
                    self.signatures[kind] = signature
                item = dict(self.cache[kind])
            except (OSError, ValueError, csv.Error):
                item = dict(self.cache.get(kind, {'kind':kind,'label':label,'file':filename,'rows':[],'totals':[],
                            'snapshot_date':None,'modified_at':None,'loaded_at':None}))
                item.update(error='檔案不存在、無法讀取或格式不符；請核對國泰匯出檔。', stale=kind in self.cache)
            result.append(item)
        return {'sources':result, 'fixture':False}
