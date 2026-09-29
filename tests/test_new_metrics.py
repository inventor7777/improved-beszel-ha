"""Checks for Beszel 0.19 and 0.20 metric conversion."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


SPEC = importlib.util.spec_from_file_location(
    "metrics", Path(__file__).parents[1] / "custom_components/improved_beszel_api/metrics.py"
)
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


class NewMetricsTest(unittest.TestCase):
    def test_disk_totals_and_pool_usage(self):
        stats = {"diot": [1024**3, 2 * 1024**3], "z": {"tank": {"d": 200, "du": 50, "rb": 2500000, "wb": 0}}}
        self.assertEqual(metrics.disk_total_gib(stats, "read"), 1)
        self.assertEqual(metrics.disk_total_gib(stats, "write"), 2)
        self.assertEqual(metrics.pool_usage_percent(stats, "tank"), 25)
        self.assertIsNone(metrics.pool_usage_percent(stats, "missing"))
        self.assertIsNone(metrics.pool_usage_percent({"z": None}, "tank"))
        self.assertEqual(metrics.pool_io_mbps(stats, "tank", "read"), 2.5)
        self.assertEqual(metrics.pool_io_mbps(stats, "tank", "write"), 0)
        self.assertIsNone(metrics.pool_io_mbps(stats, "missing", "read"))
        self.assertIsNone(metrics.pool_io_mbps({"z": {"tank": {"d": 200}}}, "tank", "read"))

    def test_container_update_counts_include_zero(self):
        records = [
            SimpleNamespace(system="a", name="old", updatable=True),
            SimpleNamespace(system="a", name="current", updatable=False),
            SimpleNamespace(system="b", name="current", updatable=False),
            SimpleNamespace(system="c", name="old"),
        ]
        self.assertEqual(metrics.container_updates_by_system(records), {"a": ["old"], "b": []})

    def test_network_monitor_results(self):
        self.assertEqual(metrics.monitor_response_ms(28718), 28.718)
        self.assertIsNone(metrics.monitor_response_ms(0))
        self.assertEqual(metrics.monitor_loss_percent({"res": 28718, "loss1h": 0}), 0)
        self.assertEqual(metrics.monitor_loss_percent({"res": 0, "loss1h": 100}), 100)
        self.assertIsNone(metrics.monitor_loss_percent({"res": 0, "loss1h": 0}))
