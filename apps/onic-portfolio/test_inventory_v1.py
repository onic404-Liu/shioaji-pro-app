"""Inventory-only boundaries tested with a broker fixture, never real credentials."""
from pathlib import Path
import os
import unittest
from test_web import WorkspaceTests, MemoryVault
from trading_service import Workspace, InputError


class InventoryTests(WorkspaceTests):
    def test_inventory_mode_rejects_simulation_before_login(self):
        self.workspace.disconnect()
        self.workspace.inventory_only = True
        self.api.login.reset_mock()
        with self.assertRaises(InputError):
            self.login('simulation')
        self.api.login.assert_not_called()

    def test_inventory_mode_rejects_all_order_routes(self):
        self.workspace.inventory_only = True
        self.login('readonly')
        for route in ('orders/preview', 'orders/submit', 'orders/refresh', 'orders/cancel'):
            with self.assertRaises(InputError):
                self.workspace.dispatch(route, {})
        self.api.place_order.assert_not_called()
        self.api.cancel_order.assert_not_called()
        self.api.login.assert_called_with(api_key='dummy-key', secret_key='dummy-secret', subscribe_trade=False)

    def test_failed_positions_keep_last_success_then_empty_success_clears(self):
        old = list(self.workspace.positions)
        old_time = self.workspace.positions_at
        self.api.list_positions.side_effect = RuntimeError('fixture unavailable')
        self.workspace.dispatch('positions', {})
        self.assertEqual(old, self.workspace.positions)
        self.assertEqual(old_time, self.workspace.positions_at)
        self.assertIsNotNone(self.workspace.positions_error)
        self.api.list_positions.side_effect = None
        self.api.list_positions.return_value = []
        self.workspace.dispatch('positions', {})
        self.assertEqual([], self.workspace.positions)
        self.assertIsNone(self.workspace.positions_error)

    def test_default_settings_are_outside_project(self):
        workspace = Workspace(vault=MemoryVault())
        expected = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Onic' / 'SinoPac' / 'web-settings.json'
        self.assertEqual(expected, workspace.path)


if __name__ == '__main__':
    unittest.main()
