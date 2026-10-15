"""Check container pagination without importing Home Assistant or PocketBase."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).parents[1] / "custom_components/improved_beszel_api/api.py"
client_class = next(node for node in ast.parse(SOURCE.read_text()).body if isinstance(node, ast.ClassDef) and node.name == "BeszelApiClient")
method = next(node for node in client_class.body if isinstance(node, ast.FunctionDef) and node.name == "get_containers")
namespace = {"SimpleNamespace": SimpleNamespace, "LOGGER": SimpleNamespace(warning=lambda *args: None)}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), "exec"), namespace)


class ContainerApiTest(unittest.TestCase):
    def test_integer_updated_field_and_pagination(self):
        pages = [
            {"items": [{"system": "a", "name": "old", "updatable": True, "updated": 1792106380647}], "totalPages": 2},
            {"items": [{"system": "b", "name": "new", "updatable": False, "updated": 1792106380648}], "totalPages": 2},
        ]
        paths = []

        def send(path, options):
            paths.append(path)
            self.assertEqual(options, {"method": "GET"})
            return pages[len(paths) - 1]

        client = SimpleNamespace(_ensure_client=lambda: None, _client=SimpleNamespace(send=send))
        records = namespace["get_containers"](client)
        self.assertEqual([record.name for record in records], ["old", "new"])
        self.assertEqual(records[0].updated, 1792106380647)
        self.assertEqual(paths, [
            "/api/collections/containers/records?page=1&perPage=500",
            "/api/collections/containers/records?page=2&perPage=500",
        ])
