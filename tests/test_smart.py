"""Checks for S.M.A.R.T. device ID fallback."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "smart", Path(__file__).parents[1] / "custom_components/improved_beszel_api/smart.py"
)
smart = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smart)


class SmartDeviceKeyTest(unittest.TestCase):
    def test_uses_name_only_when_safe_and_short(self):
        self.assertEqual(smart.smart_device_key("/dev/nvme0n1", "record1"), "nvme0n1")
        self.assertEqual(smart.smart_device_key("IOService:/disk", "record1"), "record1")
        self.assertEqual(smart.smart_device_key("a" * 101, "record1"), "record1")
