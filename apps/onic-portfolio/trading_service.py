"""Local web workspace. Production is read-only; mutations are simulation-only."""
from datetime import datetime
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid
from credential_store import Vault
from service import plain

os.environ['SJ_LOG_PATH'] = os.devnull


class InputError(ValueError):
    """Safe validation messages authored by this application."""


def number(value, positive=False):
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise InputError('請輸入大於零的有效數字。')
    return value


def code(value):
    value = str(value).strip()
    if not re.fullmatch(r'[0-9]{4,6}', value):
        raise InputError('請輸入 4–6 位台股證券代號。')
    return value


class Workspace:
    def __init__(self, path=None, vault=None, sdk=None, inventory_only=False):
        self.inventory_only = inventory_only
        self.path = Path(path or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Onic' / 'SinoPac' / 'web-settings.json')
        self.vault = vault or Vault()
        self.sdk = sdk
        self.lock = threading.RLock()
        self.quote_lock = threading.RLock()
        self.api = None
        self.profile = None
        self.accounts = []
        self.account_index = 0
        self.positions = []
        self.positions_at = None
        self.positions_error = None
        self.quotes = {}
        self.quote_error = None
        self.subscriptions = set()
        self.trades = []
        self.previews = {}
        self.last_submit = 0
        self.report_at = None
        self.events = []
        self.alert_memory = {}
        self.config = {'watch': [], 'alerts': []}
        if self.path.exists():
            stored = json.loads(self.path.read_text(encoding='utf-8'))
            self.config = {k: stored.get(k, []) for k in self.config}

    def persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.config, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)

    def require(self, trading=False):
        if self.api is None:
            raise InputError('請先連線到永豐 API。')
        if trading and self.profile != 'simulation':
            raise InputError('正式環境只有查詢權限；此工具只允許模擬交易。')
        return self.accounts[self.account_index]

    def disconnect(self):
        old, self.api = self.api, None
        self.profile = None
        self.accounts = []
        self.positions = []
        self.positions_at = None
        self.positions_error = None
        with self.quote_lock:
            self.quotes = {}
        self.quote_error = None
        self.subscriptions = set()
        self.trades = []
        self.previews = {}
        self.report_at = None
        self.events = []
        self.alert_memory = {}
        if old:
            try:
                old.logout()
            except Exception:
                pass

    def connect(self, data):
        profile = data.get('profile')
        if self.inventory_only and profile != 'readonly':
            raise InputError('庫存工作台只接受正式查詢環境，請使用正式查詢金鑰。')
        self.vault.target(profile)
        pair = self.vault.read(profile) if data.get('use_saved') else None
        key, secret = pair or (str(data.get('key', '')).strip(), str(data.get('secret', '')).strip())
        if not key or not secret:
            raise InputError('請填寫金鑰，或選擇已保存的金鑰。')
        if profile == 'simulation' and not data.get('signed'):
            raise InputError('請先確認已完成證券 API 使用同意書簽署。')
        self.disconnect()
        if self.sdk is None:
            import shioaji
            self.sdk = shioaji
        api = self.sdk.Shioaji(simulation=profile == 'simulation')
        try:
            result = api.login(api_key=key, secret_key=secret, subscribe_trade=profile == 'simulation')
            accounts = [a for a in result if getattr(a.account_type, 'value', a.account_type) == 'S']
            if not accounts:
                raise InputError('金鑰沒有可用的證券帳戶，請檢查帳戶授權。')
            if profile == 'simulation':
                api.set_order_callback(lambda *_: setattr(self, 'report_at', time.time()) if self.api is api else None)
            api.set_on_tick_stk_v1_callback(lambda *args: self.on_tick(*args) if self.api is api else None)
            if data.get('save') and not data.get('use_saved'):
                self.vault.write(profile, key, secret)
        except Exception:
            try:
                api.logout()
            except Exception:
                pass
            raise
        finally:
            key = secret = ''
        self.api, self.profile, self.accounts = api, profile, accounts
        self.account_index = 0
        self.refresh_positions()

    def on_tick(self, *args):
        tick = args[-1]
        if getattr(tick, 'simtrade', False):
            return
        try:
            symbol = str(tick.code)
            with self.quote_lock:
                old = self.quotes.get(symbol, {})
                self.quotes[symbol] = {**old, 'price': number(tick.close),
                                      'change': number(getattr(tick, 'pct_chg', 0)),
                                      'at': time.time(), 'source': '即時成交',
                                      'source_at': str(getattr(tick, 'datetime', ''))}
                self.evaluate_alerts(symbol, number(tick.close))
        except (ValueError, TypeError, AttributeError):
            pass

    def contract(self, symbol):
        self.require()
        value = self.api.Contracts.Stocks[code(symbol)]
        if value is None:
            raise InputError('找不到這個證券代號。')
        return value

    def refresh_positions(self):
        account = self.require()
        try:
            rows = plain(self.api.list_positions(account=account, unit=self.sdk.Unit.Share))
            self.positions = [{k: row.get(k) for k in
                               ('id', 'code', 'quantity', 'price', 'last_price', 'pnl', 'direction', 'cond')}
                              for row in rows]
            self.positions_at = time.time()
            self.positions_error = None
        except Exception:
            self.positions_error = '庫存查詢失敗；保留上次資料，請重新查詢並檢查帳務權限。'
        self.refresh_quotes()

    def refresh_quotes(self):
        self.require()
        symbols = set(str(p['code']) for p in self.positions)
        symbols.update(w['code'] for w in self.config['watch'])
        symbols.update(a['code'] for a in self.config['alerts'])
        if len(symbols) > 100:
            raise InputError('目前最多追蹤 100 個不同標的。')
        try:
            contracts = [self.contract(s) for s in sorted(symbols)]
            snapshots = self.api.snapshots(contracts) if contracts else []
            with self.quote_lock:
                contracts_by_code = {str(c.code): c for c in contracts}
                for snapshot in snapshots:
                    symbol = str(snapshot.code)
                    contract = contracts_by_code[symbol]
                    self.quotes[symbol] = {'name': str(contract.name), 'price': number(snapshot.close),
                                          'change': number(snapshot.change_rate), 'at': time.time(),
                                          'source': '行情快照', 'source_at': str(snapshot.ts)}
                    self.evaluate_alerts(symbol, number(snapshot.close))
            for symbol in self.subscriptions - symbols:
                self.api.unsubscribe(self.contract(symbol), quote_type=self.sdk.QuoteType.Tick,
                                     version=self.sdk.QuoteVersion.v1)
            self.subscriptions &= symbols
            for contract in contracts:
                if str(contract.code) not in self.subscriptions:
                    self.api.subscribe(contract, quote_type=self.sdk.QuoteType.Tick,
                                       version=self.sdk.QuoteVersion.v1)
                    self.subscriptions.add(str(contract.code))
            self.quote_error = None
        except Exception:
            self.quote_error = '行情更新或訂閱失敗；請檢查行情權限與連線。畫面會保留上次報價及時間。'

    def evaluate_alerts(self, symbol, price):
        for rule in self.config['alerts']:
            if not rule['enabled'] or rule['code'] != symbol:
                continue
            pct = (price / rule['base'] - 1) * 100
            zone = 'upper' if pct >= rule['pct'] else 'lower' if pct <= -rule['pct'] else 'inside'
            old_zone, last = self.alert_memory.get(rule['id'], ('inside', 0))
            now = time.time()
            if zone != 'inside' and (zone != old_zone or now - last >= rule['cooldown']):
                if now - last >= rule['cooldown']:
                    event = {'id': str(uuid.uuid4()), 'at': now, 'code': symbol,
                             'text': f'{symbol} 已達預設{"上限" if zone == "upper" else "下限"}，請檢視追蹤計畫。',
                             'price': price, 'pct': round(pct, 2)}
                    self.events = (self.events + [event])[-30:]
                    last = now
            self.alert_memory[rule['id']] = zone, last

    def save_watch(self, data):
        symbol = code(data['code'])
        if len(self.config['watch']) >= 100:
            raise InputError('關注清單最多 100 檔。')
        if any(w['code'] == symbol for w in self.config['watch']):
            raise InputError('這個代號已在關注清單。')
        name = str(self.contract(symbol).name) if self.api else ''
        self.config['watch'].append({'code': symbol, 'name': name, 'note': str(data.get('note', ''))[:100]})
        self.persist()
        if self.api:
            self.refresh_quotes()

    def save_alert(self, data):
        symbol, base, pct = code(data['code']), number(data['base'], True), number(data['pct'], True)
        if pct >= 100:
            raise InputError('上下限百分比必須小於 100%。')
        cooldown = int(data.get('cooldown', 600))
        if not 60 <= cooldown <= 86400:
            raise InputError('通知冷卻時間須介於 60 秒與一天。')
        rule = {'id': str(uuid.uuid4()), 'code': symbol, 'base': base, 'pct': pct,
                'cooldown': cooldown, 'enabled': True}
        with self.quote_lock:
            self.config['alerts'] = [a for a in self.config['alerts'] if a['code'] != symbol] + [rule]
        self.persist()
        if self.api:
            self.refresh_quotes()

    def preview(self, data):
        account = self.require(trading=True)
        symbol = code(data['code'])
        action = data.get('action')
        if action not in ('Buy', 'Sell'):
            raise InputError('請選擇買進或賣出。')
        quantity = int(data['quantity'])
        if str(quantity) != str(data['quantity']) or not 1 <= quantity <= 999:
            raise InputError('張數必須是 1–999 的整數。')
        price = number(data['price'], True)
        contract = self.contract(symbol)
        if str(getattr(getattr(contract, 'exchange', ''), 'value', getattr(contract, 'exchange', ''))) not in ('TSE', 'OTC'):
            raise InputError('此入口僅支援上市／上櫃證券整股模擬委託。')
        for field, comparison in [('limit_up', lambda p, bound: p > bound),
                                  ('limit_down', lambda p, bound: p < bound)]:
            bound = getattr(contract, field, None)
            if bound and comparison(price, float(bound)):
                raise InputError('價格超出商品檔漲跌停範圍，請更新價格。')
        ticket = {'id': str(uuid.uuid4()), 'code': symbol, 'name': str(contract.name),
                  'action': action, 'quantity': quantity, 'price': price,
                  'amount': price * quantity * 1000, 'expires': time.time() + 90,
                  'account': self.account_index}
        self.previews = {ticket['id']: ticket}
        return ticket

    def submit(self, data):
        account = self.require(trading=True)
        ticket = self.previews.get(data.get('id'))
        if not ticket or ticket['expires'] < time.time() or ticket['account'] != self.account_index:
            raise InputError('確認內容已過期或已使用，請重新預覽。')
        if time.monotonic() - self.last_submit < 1.1:
            raise InputError('請間隔至少一秒，再確認下一筆模擬委託。')
        self.previews.pop(ticket['id'])
        order = self.sdk.StockOrder(action=getattr(self.sdk.Action, ticket['action']), price=ticket['price'],
                                   quantity=ticket['quantity'], price_type=self.sdk.StockPriceType.LMT,
                                   order_type=self.sdk.OrderType.ROD, order_lot=self.sdk.StockOrderLot.Common,
                                   order_cond=self.sdk.StockOrderCond.Cash, account=account)
        self.last_submit = time.monotonic()
        try:
            trade = self.api.place_order(self.contract(ticket['code']), order)
            self.trades.append({'ticket': ticket, 'trade': trade})
        except Exception:
            self.trades.append({'ticket': ticket, 'trade': None})
            raise InputError('下單呼叫未取得確認，結果未知。請查詢委託並核對，勿直接重送。')
        return {'accepted_call': True}

    def order_rows(self):
        rows = []
        for record in self.trades:
            ticket, trade = record['ticket'], record['trade']
            status = getattr(trade.status.status, 'value', str(trade.status.status)) if trade else 'Unknown'
            rows.append({**{k: ticket[k] for k in ('id', 'code', 'name', 'action', 'quantity', 'price')},
                         'status': status, 'filled': int(getattr(trade.status, 'deal_quantity', 0)) if trade else 0})
        return rows

    def refresh_orders(self):
        account = self.require(trading=True)
        self.api.update_status(account=account)
        known = {getattr(r['trade'].order, 'id', None) for r in self.trades if r['trade']}
        for trade in self.api.list_trades():
            if trade.order.account.account_id != account.account_id or trade.order.id in known:
                continue
            self.trades.append({'ticket': {'id': str(uuid.uuid4()), 'code': str(trade.contract.code),
                                'name': str(trade.contract.name),
                                'action': getattr(trade.order.action, 'value', str(trade.order.action)),
                                'quantity': int(trade.order.quantity), 'price': float(trade.order.price)}, 'trade': trade})
        self.report_at = time.time()

    def cancel(self, data):
        self.require(trading=True)
        record = next((r for r in self.trades if r['ticket']['id'] == data.get('id')), None)
        if not record or not record['trade']:
            raise InputError('沒有可撤銷的已知委託；請先查詢委託。')
        if getattr(record['trade'].order.account, 'account_id', None) != self.require().account_id:
            raise InputError('這筆委託不屬於目前選取的帳戶。')
        status = getattr(record['trade'].status.status, 'value', str(record['trade'].status.status))
        if status not in ('Submitted', 'PartFilled', 'PreSubmitted'):
            raise InputError('此狀態不能撤單，請更新委託回報。')
        self.api.cancel_order(record['trade'])
        return {'cancel_requested': True}

    def state(self):
        with self.quote_lock:
            quotes = json.loads(json.dumps(self.quotes))
            events = list(self.events)
        return {'connected': self.api is not None, 'profile': self.profile,
                'inventory_only': self.inventory_only,
                'accounts': [f'{a.broker_id} / ****{str(a.account_id)[-4:]}' for a in self.accounts],
                'account_index': self.account_index, 'saved': self.vault.saved(),
                'positions': self.positions, 'positions_at': self.positions_at,
                'positions_error': self.positions_error, 'quotes': quotes, 'quote_error': self.quote_error,
                'watch': self.config['watch'], 'alerts': self.config['alerts'],
                'orders': self.order_rows(), 'events': events, 'report_at': self.report_at}

    def dispatch(self, route, data):
        with self.lock:
            if self.inventory_only and route.startswith('orders/'):
                raise InputError('庫存工作台未開放下單、改單或刪單功能。')
            if route == 'connect':
                self.connect(data)
            elif route == 'disconnect':
                self.disconnect()
            elif route == 'credentials/delete':
                self.vault.delete(data['profile'])
            elif route == 'account':
                self.require()
                index = int(data['index'])
                if not 0 <= index < len(self.accounts):
                    raise InputError('帳戶選擇無效。')
                self.account_index = index
                self.previews = {}
                self.trades = []
                self.positions = []
                self.positions_at = None
                self.refresh_positions()
            elif route == 'positions':
                self.refresh_positions()
            elif route == 'quotes':
                self.refresh_quotes()
            elif route == 'watch/add':
                self.save_watch(data)
            elif route == 'watch/remove':
                self.config['watch'] = [w for w in self.config['watch'] if w['code'] != code(data['code'])]
                self.persist()
                if self.api:
                    self.refresh_quotes()
            elif route == 'alerts/save':
                self.save_alert(data)
            elif route == 'alerts/remove':
                with self.quote_lock:
                    self.config['alerts'] = [a for a in self.config['alerts'] if a['id'] != data['id']]
                self.persist()
            elif route == 'orders/preview':
                return self.preview(data)
            elif route == 'orders/submit':
                return self.submit(data)
            elif route == 'orders/refresh':
                self.refresh_orders()
            elif route == 'orders/cancel':
                return self.cancel(data)
            else:
                raise InputError('未知操作。')
            return self.state()
