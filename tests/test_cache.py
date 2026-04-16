import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from h6006ctl.cache import cache_path, load_bulbs, save_bulbs


class CachePathTests(unittest.TestCase):
    def test_respects_xdg_config_home(self) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/xdg-test"}):
            result = cache_path()
        self.assertEqual(result, Path("/tmp/xdg-test/h6006ctl/bulbs.json"))

    def test_defaults_to_dot_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = cache_path()
        self.assertEqual(result, Path.home() / ".config" / "h6006ctl" / "bulbs.json")


class SaveLoadRoundTripTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "h6006ctl" / "bulbs.json"
            bulbs = [{"address": "AA:BB:CC:DD:EE:FF", "name": "ihoment_H6006_ABCD"}]
            with patch("h6006ctl.cache.cache_path", return_value=fake_path):
                save_bulbs(bulbs)
                loaded = load_bulbs()
            self.assertEqual(loaded, bulbs)

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "deep" / "nested" / "bulbs.json"
            with patch("h6006ctl.cache.cache_path", return_value=fake_path):
                save_bulbs([{"address": "AA:BB", "name": "test"}])
            self.assertTrue(fake_path.exists())


class LoadBulbsEdgeCases(unittest.TestCase):
    def test_returns_none_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "nonexistent" / "bulbs.json"
            with patch("h6006ctl.cache.cache_path", return_value=fake_path):
                self.assertIsNone(load_bulbs())

    def test_returns_none_for_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "bulbs.json"
            fake_path.write_text("{bad json")
            with patch("h6006ctl.cache.cache_path", return_value=fake_path):
                self.assertIsNone(load_bulbs())

    def test_returns_none_for_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "bulbs.json"
            fake_path.write_text("[]")
            with patch("h6006ctl.cache.cache_path", return_value=fake_path):
                self.assertIsNone(load_bulbs())

    def test_returns_none_for_missing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "bulbs.json"
            fake_path.write_text('[{"address": "AA:BB"}]')
            with patch("h6006ctl.cache.cache_path", return_value=fake_path):
                self.assertIsNone(load_bulbs())
