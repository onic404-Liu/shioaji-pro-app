"""Read-only Shioaji adapter. No order placement or certificate activation."""
from datetime import date
from enum import Enum


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'model_dump'):
        return plain(value.model_dump())
    if hasattr(value, 'dict'):
        return plain(value.dict())
    return value


def validate_dates(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if a > b:
        raise ValueError('開始日期不可晚於結束日期。')
    if b > date.today():
        raise ValueError('結束日期不可晚於今天。')
    return start, end


class Broker:
    def __init__(self, module=None):
        self.module = module
        self.api = None
        self.accounts = []

    def login(self, key, secret, simulation):
        if self.module is None:
            import shioaji
            self.module = shioaji
        self.logout()
        api = self.module.Shioaji(simulation=simulation)
        try:
            accounts = api.login(api_key=key, secret_key=secret,
                                 subscribe_trade=False)
            stocks = [a for a in accounts
                      if str(getattr(a.account_type, 'value', a.account_type)) == 'S']
            if not stocks:
                raise ValueError('登入成功，但沒有可用的證券帳戶。請確認金鑰的帳戶授權。')
        except Exception:
            try:
                api.logout()
            except Exception:
                pass
            raise
        self.api, self.accounts = api, stocks
        return [f'{a.broker_id} / ****{str(a.account_id)[-4:]}' for a in stocks]

    def logout(self):
        api, self.api = self.api, None
        self.accounts = []
        if api:
            api.logout()

    def account(self, index):
        if self.api is None:
            raise ValueError('請先登入。')
        return self.accounts[index]

    def positions(self, index):
        return plain(self.api.list_positions(account=self.account(index),
                                            unit=self.module.Unit.Share))

    def history(self, index, start, end, code=''):
        validate_dates(start, end)
        rows = plain(self.api.list_profit_loss(account=self.account(index),
                     begin_date=start, end_date=end, unit=self.module.Unit.Share))
        return [r for r in rows if not code or str(r.get('code')) == code]

    def position_detail(self, index, detail_id):
        return plain(self.api.list_position_detail(account=self.account(index), detail_id=detail_id))

    def profit_detail(self, index, detail_id):
        return plain(self.api.list_profit_loss_detail(account=self.account(index),
                     detail_id=detail_id, unit=self.module.Unit.Share))

    def names(self, codes):
        if self.api is None:
            raise ValueError('請先登入，才能核對股票代號。')
        rows = []
        for code, note in codes:
            contract = self.api.Contracts.Stocks[code]
            rows.append({'code': code, 'name': getattr(contract, 'name', '') if contract else '',
                         'note': note, 'state': '已找到商品' if contract else '查無商品'})
        return rows
