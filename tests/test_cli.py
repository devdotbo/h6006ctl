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
