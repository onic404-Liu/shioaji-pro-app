import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
import uuid
from credential_store import Vault
from trading_service import Workspace
from web_app import Server


class MemoryVault:
    target = staticmethod(Vault.target)
    def __init__(self):
        self.values = {}
    def read(self, profile):
        self.target(profile)
        return self.values.get(profile)
    def write(self, profile, key, secret):
        self.target(profile)
        self.values[profile] = key, secret
    def delete(self, profile):
        self.target(profile)
        self.values.pop(profile, None)
    def saved(self):
        return {p: p in self.values for p in ('simulation', 'readonly')}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = MemoryVault()
        self.account = NS(account_type='S', broker_id='9A95', account_id='1234567')
        self.contract = NS(code='2890', name='測試證券', exchange='TSE', limit_up=40, limit_down=20)
        self.api = Mock()
        self.api.login.return_value = [self.account]
        self.api.list_positions.return_value = [{'code':'2890', 'quantity':1000, 'price':28,
                                                'last_price':29, 'pnl':1000}]
        self.api.snapshots.return_value = [NS(code='2890', close=29, change_rate=1.2, ts=1)]
        self.api.Contracts = NS(Stocks={'2890': self.contract})
        self.api.list_trades.return_value = []
        self.sdk = NS(Shioaji=Mock(return_value=self.api), Unit=NS(Share='Share'),
                      QuoteType=NS(Tick='Tick'), QuoteVersion=NS(v1='v1'),
                      Action=NS(Buy='Buy',Sell='Sell'),StockPriceType=NS(LMT='LMT'),
                      OrderType=NS(ROD='ROD'),StockOrderLot=NS(Common='Common'),
                      StockOrderCond=NS(Cash='Cash'), StockOrder=Mock(side_effect=lambda **kw:NS(**kw)))
        self.workspace = Workspace(Path(self.temp.name)/'settings.json', self.vault, self.sdk)
        self.login()

    def login(self, profile='simulation', save=False):
        self.workspace.dispatch('connect', {'profile':profile, 'key':'dummy-key',
                                'secret':'dummy-secret','signed':True,'save':save})

    def preview(self):
        return self.workspace.dispatch('orders/preview', {'code':'2890','action':'Buy','quantity':'1','price':'28'})

    def test_login_before_callback_and_fixed_environment(self):
        self.sdk.Shioaji.assert_called_once_with(simulation=True)
        names = [c[0] for c in self.api.method_calls]
        self.assertLess(names.index('login'), names.index('set_order_callback'))
        self.api.activate_ca.assert_not_called()

    def test_save_and_read_never_expose_secrets_or_write_them_in_settings(self):
        self.login(save=True)
        self.workspace.dispatch('watch/add', {'code':'2890','note':'測試'})
        state = json.dumps(self.workspace.state())
        content = self.workspace.path.read_text(encoding='utf-8')
        for value in ('dummy-key','dummy-secret'):
            self.assertNotIn(value, state)
            self.assertNotIn(value, content)
        self.assertTrue(self.workspace.state()['saved']['simulation'])
        self.workspace.dispatch('disconnect', {})
        self.workspace.dispatch('connect', {'profile':'simulation','use_saved':True,'signed':True})
        self.assertTrue(self.workspace.state()['connected'])
        self.workspace.dispatch('credentials/delete', {'profile':'simulation'})
        self.assertFalse(self.workspace.state()['saved']['simulation'])

    def test_formal_mode_rejects_every_trading_route_before_sdk_call(self):
        self.login('readonly')
        for route, data in [('orders/preview',{}),('orders/submit',{'id':'anything'}),
                            ('orders/cancel',{'id':'anything'}),('orders/refresh',{})]:
            with self.assertRaises(ValueError):
                self.workspace.dispatch(route,data)
        self.api.place_order.assert_not_called()
        self.api.cancel_order.assert_not_called()
        self.assertEqual(self.sdk.Shioaji.call_args.kwargs['simulation'],False)

    def test_single_use_confirmation_and_pending_not_success(self):
        ticket=self.preview()
        trade=NS(status=NS(status='PendingSubmit',deal_quantity=0),order=NS(id='test',account=self.account))
        self.api.place_order.return_value=trade
        self.workspace.dispatch('orders/submit',{'id':ticket['id']})
        self.assertEqual(self.workspace.state()['orders'][0]['status'],'PendingSubmit')
        with self.assertRaises(ValueError):
            self.workspace.dispatch('orders/submit',{'id':ticket['id']})
        self.api.place_order.assert_called_once()
        order=self.api.place_order.call_args.args[1]
        self.assertEqual((order.quantity,order.order_lot,order.order_cond),(1,'Common','Cash'))

    def test_invalid_prices_quantities_expired_ticket_and_account_change(self):
        for price,qty in [('nan','1'),('0','1'),('100','1'),('28','1.5'),('28','0')]:
            with self.assertRaises((ValueError,TypeError)):
                self.workspace.preview({'code':'2890','action':'Buy','price':price,'quantity':qty})
        ticket=self.preview();ticket['expires']=0
        with self.assertRaises(ValueError):
            self.workspace.submit({'id':ticket['id']})
        ticket=self.preview()
        self.workspace.dispatch('account',{'index':0})
        with self.assertRaises(ValueError):
            self.workspace.submit({'id':ticket['id']})
        self.api.place_order.assert_not_called()

    def test_unknown_result_is_not_retried(self):
        ticket=self.preview()
        self.api.place_order.side_effect=TimeoutError()
        with self.assertRaises(ValueError):
            self.workspace.submit({'id':ticket['id']})
        self.assertEqual(self.workspace.state()['orders'][0]['status'],'Unknown')
        with self.assertRaises(ValueError):
            self.workspace.submit({'id':ticket['id']})
        self.api.place_order.assert_called_once()

    def test_cooldown_and_tick_stream(self):
        self.workspace.save_alert({'code':'2890','base':28,'pct':10,'cooldown':600})
        self.workspace.on_tick(NS(code='2890',close=31,pct_chg=2,simtrade=False,datetime='test'))
        self.workspace.on_tick(NS(code='2890',close=32,pct_chg=3,simtrade=False,datetime='test'))
        self.assertEqual(len(self.workspace.events),1)
        self.assertEqual(self.workspace.quotes['2890']['price'],32)
        self.workspace.on_tick(NS(code='2890',close=500,pct_chg=3,simtrade=True,datetime='test'))
        self.assertEqual(self.workspace.quotes['2890']['price'],32)

    def test_failure_preserves_last_positions_and_timestamp(self):
        old_time=self.workspace.positions_at
        self.api.list_positions.side_effect=TimeoutError()
        self.workspace.refresh_positions()
        self.assertEqual(self.workspace.positions[0]['quantity'],1000)
        self.assertEqual(self.workspace.positions_at,old_time)
        self.assertTrue(self.workspace.positions_error)

    def test_cancel_requires_right_account_and_valid_state(self):
        trade=NS(status=NS(status='Submitted',deal_quantity=0),order=NS(id='t',account=self.account))
        self.api.place_order.return_value=trade
        ticket=self.preview();self.workspace.submit({'id':ticket['id']})
        self.workspace.cancel({'id':ticket['id']})
        self.api.cancel_order.assert_called_once_with(trade)
        trade.status.status='Filled'
        with self.assertRaises(ValueError):
            self.workspace.cancel({'id':ticket['id']})


class HttpSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Workspace(Path(self.temp.name)/'config.json',MemoryVault())
        self.server=Server(('127.0.0.1',0),self.workspace,'offline-test-token')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self,method,path,headers=None,data=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        c.request(method,path,body=json.dumps(data) if data is not None else None,headers=headers or {})
        r=c.getresponse();body=r.read();status=r.status;c.close();return status,body

    def test_no_unauthorized_state_or_private_files(self):
        self.assertEqual(self.request('GET','/api/state')[0],401)
        self.assertEqual(self.request('GET','/../credential_store.py')[0],404)
        self.assertEqual(self.request('GET','/data/web-settings.json')[0],404)
        h={'Authorization':'Bearer offline-test-token'}
        status,body=self.request('GET','/api/state',h)
        self.assertEqual(status,200);self.assertNotIn(b'secret',body)

    def test_origin_and_host_are_checked_before_mutation(self):
        h={'Authorization':'Bearer offline-test-token','Content-Type':'application/json',
           'Origin':'https://example.com'}
        self.assertEqual(self.request('POST','/api/watch/add',h,{'code':'2890'})[0],403)
        h['Origin']=self.server.origin;h['Host']='evil.example'
        self.assertEqual(self.request('POST','/api/watch/add',h,{'code':'2890'})[0],403)
        h.pop('Host');self.assertEqual(self.request('POST','/api/watch/add',h,{'code':'2890'})[0],200)
        self.assertEqual(len(self.workspace.config['watch']),1)


class WindowsVaultTests(unittest.TestCase):
    def test_real_credential_roundtrip_in_disposable_target(self):
        unique='Onic/SinoPac/QA-'+str(uuid.uuid4())
        class TestVault(Vault):
            @staticmethod
            def target(profile):
                return unique
        vault=TestVault()
        try:
            vault.write('simulation','offline-dummy-key','offline-dummy-secret')
            self.assertEqual(vault.read('simulation'),('offline-dummy-key','offline-dummy-secret'))
        finally:
            vault.delete('simulation')
        self.assertIsNone(vault.read('simulation'))


if __name__=='__main__':
    unittest.main()
