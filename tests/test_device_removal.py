"""Check device removal without importing Home Assistant."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).parents[1] / "custom_components/improved_beszel_api/__init__.py"
function = next(
    node for node in ast.parse(SOURCE.read_text()).body
    if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_remove_config_entry_device"
)
namespace = {"DOMAIN": "improved_beszel_api"}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)


class DeviceRemovalTest(unittest.IsolatedAsyncioTestCase):
    async def test_only_removed_system_can_be_deleted(self):
        coordinator = SimpleNamespace(
            data={"systems": [SimpleNamespace(id="current")]},
            last_update_success=True,
        )
        calls = []

        async def refresh():
            calls.append(True)

        coordinator.async_request_refresh = refresh
        entry = SimpleNamespace(entry_id="hub")
        hass = SimpleNamespace(data={"improved_beszel_api": {"hub": {"coordinator": coordinator}}})
        remove = namespace["async_remove_config_entry_device"]

        for identifier, expected in (("removed", True), ("current", False), ("hub", False)):
            device = SimpleNamespace(identifiers={("improved_beszel_api", identifier)})
            self.assertEqual(await remove(hass, entry, device), expected)
        self.assertEqual(len(calls), 2)

        coordinator.last_update_success = False
        device = SimpleNamespace(identifiers={("improved_beszel_api", "removed")})
        self.assertFalse(await remove(hass, entry, device))


if __name__ == "__main__":
    unittest.main()
