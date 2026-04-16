import asyncio
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import AsyncMock, patch

from h6006ctl import cli
from h6006ctl.ble import Bulb, DeviceState


class CliTests(unittest.TestCase):
    def test_status_prints_text_output(self) -> None:
        bulb = Bulb(address="addr-1", name="ihoment_H6006_ABCD")
        state = DeviceState(power=True, brightness=100, rgb=(0, 0, 255))
        stdout = io.StringIO()

        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=[bulb])),
            patch("h6006ctl.cli.get_status", AsyncMock(return_value={bulb.address: state})),
            redirect_stdout(stdout),
        ):
            code = asyncio.run(cli.async_main(["status"]))

        self.assertEqual(code, 0)
        self.assertIn("brightness=100", stdout.getvalue())
        self.assertIn("rgb=(0, 0, 255)", stdout.getvalue())

    def test_status_json_output(self) -> None:
        bulb = Bulb(address="addr-1", name="ihoment_H6006_ABCD")
        state = DeviceState(power=True, brightness=100, kelvin=2700)
        stdout = io.StringIO()

        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=[bulb])),
            patch("h6006ctl.cli.get_status", AsyncMock(return_value={bulb.address: state})),
            redirect_stdout(stdout),
        ):
            code = asyncio.run(cli.async_main(["status", "--json"]))

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload[0]["brightness"], 100)
        self.assertEqual(payload[0]["kelvin"], 2700)

    def test_invalid_brightness_returns_error(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = asyncio.run(cli.async_main(["brightness", "101"]))

        self.assertEqual(code, 1)
        self.assertIn("brightness must be between 0 and 100", stderr.getvalue())

    def test_no_bulbs_status_returns_error(self) -> None:
        stderr = io.StringIO()

        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=[])),
            redirect_stderr(stderr),
        ):
            code = asyncio.run(cli.async_main(["status"]))

        self.assertEqual(code, 1)
        self.assertIn("No H6006 bulbs were discovered", stderr.getvalue())


class SetCommandTests(unittest.TestCase):
    def test_set_command_applies_multiple_properties(self) -> None:
        stdout = io.StringIO()
        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=[
                Bulb(address="addr-1", name="ihoment_H6006_ABCD"),
            ])),
            patch("h6006ctl.cli.set_multiple", AsyncMock()) as mock_set,
            redirect_stdout(stdout),
        ):
            code = asyncio.run(cli.async_main(["set", "--on", "--brightness", "80"]))
        self.assertEqual(code, 0)
        mock_set.assert_awaited_once()
        kwargs = mock_set.call_args[1]
        self.assertTrue(kwargs["power"])
        self.assertEqual(kwargs["brightness"], 80)

    def test_set_command_rejects_rgb_and_ct(self) -> None:
        stderr = io.StringIO()
        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=[
                Bulb(address="addr-1", name="ihoment_H6006_ABCD"),
            ])),
            redirect_stderr(stderr),
        ):
            code = asyncio.run(cli.async_main(["set", "--rgb", "255", "0", "0", "--ct", "2700"]))
        self.assertEqual(code, 1)
        self.assertIn("Cannot use --rgb and --ct together", stderr.getvalue())

    def test_set_command_requires_property(self) -> None:
        stderr = io.StringIO()
        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=[
                Bulb(address="addr-1", name="ihoment_H6006_ABCD"),
            ])),
            redirect_stderr(stderr),
        ):
            code = asyncio.run(cli.async_main(["set"]))
        self.assertEqual(code, 1)
        self.assertIn("at least one property", stderr.getvalue())


class ScanSaveTests(unittest.TestCase):
    def test_scan_save_writes_cache(self) -> None:
        bulbs = [Bulb(address="addr-1", name="ihoment_H6006_ABCD")]
        stdout = io.StringIO()
        with (
            patch("h6006ctl.cli.discover_bulbs", AsyncMock(return_value=bulbs)),
            patch("h6006ctl.cli.save_bulbs") as mock_save,
            redirect_stdout(stdout),
        ):
            code = asyncio.run(cli.async_main(["scan", "--save"]))
        self.assertEqual(code, 0)
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        self.assertEqual(saved[0]["address"], "addr-1")


class NoCacheFlagTests(unittest.TestCase):
    def test_no_cache_flag_passes_through(self) -> None:
        bulbs = [Bulb(address="addr-1", name="ihoment_H6006_ABCD")]
        stdout = io.StringIO()
        with (
            patch("h6006ctl.cli.resolve_targets", AsyncMock(return_value=bulbs)) as mock_resolve,
            patch("h6006ctl.cli.set_power", AsyncMock()),
            redirect_stdout(stdout),
        ):
            code = asyncio.run(cli.async_main(["--no-cache", "on"]))
        self.assertEqual(code, 0)
        _, kwargs = mock_resolve.call_args
        self.assertFalse(kwargs.get("use_cache", True))
