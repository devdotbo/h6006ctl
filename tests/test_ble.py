import unittest
from unittest.mock import AsyncMock, patch

from h6006ctl.ble import Bulb, _find_matches, funny, identify, resolve_targets


class ResolveTargetsTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_targets_matches_unique_suffix(self) -> None:
        bulbs = [
            Bulb(address="addr-1", name="ihoment_H6006_ABCD"),
            Bulb(address="addr-2", name="ihoment_H6006_EFGH"),
        ]

        with patch("h6006ctl.ble.discover_bulbs", AsyncMock(return_value=bulbs)):
            resolved = await resolve_targets(["ABCD"])

        self.assertEqual([bulb.name for bulb in resolved], ["ihoment_H6006_ABCD"])

    async def test_resolve_targets_rejects_ambiguous_target(self) -> None:
        bulbs = [
            Bulb(address="addr-1", name="ihoment_H6006_ABCD"),
            Bulb(address="addr-2", name="ihoment_H6006_XABCD"),
        ]

        with patch("h6006ctl.ble.discover_bulbs", AsyncMock(return_value=bulbs)):
            with self.assertRaises(ValueError):
                await resolve_targets(["ABCD"])


class MatchTests(unittest.TestCase):
    def test_find_matches_supports_name_address_and_suffix(self) -> None:
        bulb = Bulb(address="addr-1", name="ihoment_H6006_ABCD")

        self.assertEqual(_find_matches("abcd", [bulb]), [bulb])
        self.assertEqual(_find_matches("addr-1", [bulb]), [bulb])
        self.assertEqual(_find_matches("ihoment_h6006_abcd", [bulb]), [bulb])


class DemoRestoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_identify_restores_default_state(self) -> None:
        bulb = Bulb(address="addr-1", name="ihoment_H6006_ABCD")
        fake_session = AsyncMock()
        fake_session.__aenter__.return_value = fake_session
        fake_session.__aexit__.return_value = None

        with (
            patch("h6006ctl.ble.BulbSession", return_value=fake_session),
            patch("h6006ctl.ble.restore_default_state", AsyncMock()) as restore_default_state,
        ):
            await identify(bulb, cycles=1)

        restore_default_state.assert_awaited_once_with([bulb])

    async def test_funny_restores_default_state(self) -> None:
        bulbs = [Bulb(address="addr-1", name="ihoment_H6006_ABCD")]
        fake_session = AsyncMock()
        fake_session.__aenter__.return_value = fake_session
        fake_session.__aexit__.return_value = None

        with (
            patch("h6006ctl.ble.BulbSession", return_value=fake_session),
            patch("h6006ctl.ble.restore_default_state", AsyncMock()) as restore_default_state,
        ):
            await funny(bulbs, loops=1)

        restore_default_state.assert_awaited_once_with(bulbs)
