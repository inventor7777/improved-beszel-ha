"""Check URL normalization without importing Home Assistant."""

import ast
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import unittest


SOURCE = Path(__file__).parents[1] / "custom_components/improved_beszel_api/config_flow.py"
function = next(node for node in ast.parse(SOURCE.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == "_normalize_url")
namespace = {"urlsplit": urlsplit, "urlunsplit": urlunsplit}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)


class NormalizeUrlTest(unittest.TestCase):
    def test_preserves_path_and_credentials(self):
        self.assertEqual(
            namespace["_normalize_url"]("  HTTPS://User:Secret@Example.COM:1800/BeSzEl/  "),
            "https://User:Secret@example.com:1800/BeSzEl",
        )
        self.assertEqual(
            namespace["_normalize_url"]("HTTP://[2001:DB8::1]:1800/Api/"),
            "http://[2001:db8::1]:1800/Api",
        )
