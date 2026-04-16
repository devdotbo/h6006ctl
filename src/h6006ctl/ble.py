"""BLE discovery, state queries, and control helpers for H6006 bulbs."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .cache import load_bulbs
from .protocol import (
    BRIGHTNESS_CMD,
    COLOR_CMD,
    DEFAULT_BRIGHTNESS,
    DEFAULT_KELVIN,
    MAX_KELVIN,
    MIN_KELVIN,
    MODEL_PREFIX,
    POWER_CMD,
    READ_UUID,
    REQUEST_HEAD,
    WRITE_UUID,
    brightness_packet,
    build_query,
    color_temp_packet,
    power_packet,
    rgb_packet,
)


@dataclass(slots=True)
class Bulb:
    address: str
    name: str
    ble_device: BLEDevice | None = None
    rssi: int | None = None
    manufacturer_data: dict[int, bytes] = field(default_factory=dict)

    @property
    def suffix(self) -> str:
        return self.name.rsplit("_", maxsplit=1)[-1]


@dataclass(slots=True)
class DeviceState:
    power: bool | None = None
    brightness: int | None = None
    rgb: tuple[int, int, int] | None = None
    kelvin: int | None = None

    @property
    def mode(self) -> str:
        if self.kelvin is not None:
            return "ct"
        if self.rgb is not None:
            return "rgb"
        return "unknown"


@dataclass(slots=True)
class BulbSession:
    bulbs: Sequence[Bulb]
    timeout: float = 20.0
    _stack: AsyncExitStack = field(init=False, repr=False)
    _clients: dict[str, BleakClient] = field(init=False, default_factory=dict, repr=False)

    async def __aenter__(self) -> BulbSession:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        try:
            if len(self.bulbs) <= 1:
                for bulb in self.bulbs:
                    client = BleakClient(bulb.ble_device or bulb.address, timeout=self.timeout)
                    await self._stack.enter_async_context(client)
                    self._clients[bulb.address] = client
            else:
                clients = [
                    BleakClient(bulb.ble_device or bulb.address, timeout=self.timeout)
                    for bulb in self.bulbs
                ]
                results = await asyncio.gather(
                    *(c.connect() for c in clients), return_exceptions=True
                )
                for client in clients:
                    self._stack.push_async_callback(client.disconnect)
                errors = [r for r in results if isinstance(r, BaseException)]
                if errors:
                    raise errors[0]
                for bulb, client in zip(self.bulbs, clients, strict=True):
                    self._clients[bulb.address] = client
        except Exception as exc:
            await self._stack.__aexit__(type(exc), exc, exc.__traceback__)
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._stack.__aexit__(exc_type, exc, tb)

    async def write_all(self, packet_by_address: dict[str, bytes]) -> None:
        for address, packet in packet_by_address.items():
            await self._clients[address].write_gatt_char(WRITE_UUID, packet, response=False)

    async def query_status(self, per_device_timeout: float = 5.0) -> dict[str, DeviceState]:
        results: dict[str, DeviceState] = {bulb.address: DeviceState() for bulb in self.bulbs}

        async def query_one(bulb: Bulb) -> None:
            state = results[bulb.address]
            event = asyncio.Event()

            def on_notify(_, data: bytearray) -> None:
                parsed = parse_notification(data)
                if parsed is None:
                    return

                kind, value = parsed
                if kind == "power":
                    state.power = value
                elif kind == "brightness":
                    state.brightness = value
                elif kind == "rgb":
                    state.rgb = value
                    state.kelvin = None
                elif kind == "ct":
                    state.kelvin = value
                    state.rgb = None

                if state.power is not None and state.brightness is not None and (
                    state.rgb is not None or state.kelvin is not None
                ):
                    event.set()

            client = self._clients[bulb.address]
            await client.start_notify(READ_UUID, on_notify)
            try:
                for command in (POWER_CMD, BRIGHTNESS_CMD, COLOR_CMD):
                    await client.write_gatt_char(WRITE_UUID, build_query(command), response=False)
                await asyncio.wait_for(event.wait(), timeout=per_device_timeout)
            except TimeoutError as err:
                raise TimeoutError(
                    f"Timed out querying status for {bulb.name} ({bulb.address})"
                ) from err
            finally:
                await client.stop_notify(READ_UUID)

        await asyncio.gather(*(query_one(bulb) for bulb in self.bulbs))
        return results


def parse_notification(frame: bytes | bytearray) -> tuple[str, object] | None:
    if len(frame) < 20 or frame[0] != REQUEST_HEAD:
        return None

    checksum = 0
    for byte in frame[:19]:
        checksum ^= byte
    if (checksum & 0xFF) != frame[19]:
        return None

    command = frame[1]
    if command == POWER_CMD:
        return ("power", frame[2] == 0x01)
    if command == BRIGHTNESS_CMD:
        return ("brightness", frame[2])
    if command == COLOR_CMD:
        red, green, blue = frame[3], frame[4], frame[5]
        kelvin = (frame[6] << 8) | frame[7]
        if (red, green, blue) == (0, 0, 0) and MIN_KELVIN <= kelvin <= MAX_KELVIN:
            return ("ct", kelvin)
        return ("rgb", (red, green, blue))
    return None


async def discover_bulbs(timeout: float = 5.0) -> list[Bulb]:
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    bulbs: list[Bulb] = []

    for address, (device, adv) in devices.items():
        name = device.name or adv.local_name or ""
        if not name.startswith(MODEL_PREFIX):
            continue
        bulbs.append(
            Bulb(
                address=address,
                name=name,
                ble_device=device,
                rssi=adv.rssi,
                manufacturer_data=dict(adv.manufacturer_data or {}),
            )
        )

    bulbs.sort(key=lambda bulb: (bulb.name, bulb.address))
    return bulbs


async def resolve_targets(
    targets: Sequence[str], timeout: float = 5.0, *, use_cache: bool = True
) -> list[Bulb]:
    if use_cache:
        cached = bulbs_from_cache()
        if cached is not None:
            if not targets:
                return cached
            resolved: list[Bulb] = []
            lowered_targets = [t.lower() for t in targets]
            for target in lowered_targets:
                matches = _find_matches(target, cached)
                if not matches:
                    pass  # fall through to scan
                elif len(matches) > 1:
                    options = ", ".join(f"{b.name} ({b.address})" for b in matches)
                    raise ValueError(f"Target '{target}' is ambiguous: {options}")
                else:
                    bulb = matches[0]
                    if bulb.address not in {item.address for item in resolved}:
                        resolved.append(bulb)
            if len(resolved) == len(lowered_targets):
                return resolved
            # Fall through to scan if any target didn't match cache

    discovered = await discover_bulbs(timeout=timeout)
    if not targets:
        return discovered

    resolved = []
    lowered_targets = [target.lower() for target in targets]
    for target in lowered_targets:
        matches = _find_matches(target, discovered)
        if not matches:
            raise ValueError(f"No discovered H6006 matched target '{target}'.")
        if len(matches) > 1:
            options = ", ".join(f"{bulb.name} ({bulb.address})" for bulb in matches)
            raise ValueError(f"Target '{target}' is ambiguous: {options}")
        bulb = matches[0]
        if bulb.address not in {item.address for item in resolved}:
            resolved.append(bulb)

    return resolved


def _find_matches(target: str, bulbs: Iterable[Bulb]) -> list[Bulb]:
    matches: list[Bulb] = []
    for bulb in bulbs:
        haystacks = {
            bulb.address.lower(),
            bulb.name.lower(),
            bulb.suffix.lower(),
        }
        if target in haystacks or target in bulb.address.lower() or target in bulb.name.lower():
            matches.append(bulb)
    return matches


def bulbs_from_cache() -> list[Bulb] | None:
    """Convert cached dicts to Bulb objects. Returns None if cache is unusable."""
    entries = load_bulbs()
    if entries is None:
        return None
    return [
        Bulb(address=entry["address"], name=entry["name"])
        for entry in entries
    ]


async def set_power(bulbs: Sequence[Bulb], on: bool) -> None:
    async with BulbSession(bulbs) as session:
        await session.write_all({bulb.address: power_packet(on) for bulb in bulbs})
    if not on:
        # H6006 bulbs need a short settle window after power-off before
        # a new BLE session can reliably query the updated state.
        await asyncio.sleep(1.0)


async def set_brightness(bulbs: Sequence[Bulb], value: int) -> None:
    async with BulbSession(bulbs) as session:
        await session.write_all({bulb.address: brightness_packet(value) for bulb in bulbs})


async def set_rgb(bulbs: Sequence[Bulb], red: int, green: int, blue: int) -> None:
    async with BulbSession(bulbs) as session:
        await session.write_all(
            {bulb.address: rgb_packet(red, green, blue) for bulb in bulbs}
        )


async def set_color_temp(bulbs: Sequence[Bulb], kelvin: int) -> None:
    async with BulbSession(bulbs) as session:
        await session.write_all({bulb.address: color_temp_packet(kelvin) for bulb in bulbs})


async def set_multiple(
    bulbs: Sequence[Bulb],
    *,
    power: bool | None = None,
    brightness: int | None = None,
    rgb: tuple[int, int, int] | None = None,
    kelvin: int | None = None,
) -> None:
    """Apply multiple properties in a single BLE session.

    Packet order: power -> brightness -> color (matches restore_default_state).
    """
    if not bulbs:
        return

    async with BulbSession(bulbs) as session:
        if power is not None:
            await session.write_all({b.address: power_packet(power) for b in bulbs})
            if not power:
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.2)
        if brightness is not None:
            await session.write_all(
                {b.address: brightness_packet(brightness) for b in bulbs}
            )
            await asyncio.sleep(0.2)
        if rgb is not None:
            await session.write_all(
                {b.address: rgb_packet(*rgb) for b in bulbs}
            )
        elif kelvin is not None:
            await session.write_all(
                {b.address: color_temp_packet(kelvin) for b in bulbs}
            )


async def restore_default_state(bulbs: Sequence[Bulb]) -> None:
    """Return bulbs to the public default resting state."""

    if not bulbs:
        return

    await set_power(bulbs, on=True)
    await asyncio.sleep(0.2)
    await set_brightness(bulbs, DEFAULT_BRIGHTNESS)
    await asyncio.sleep(0.2)
    await set_color_temp(bulbs, DEFAULT_KELVIN)


async def get_status(bulbs: Sequence[Bulb]) -> dict[str, DeviceState]:
    if not bulbs:
        raise ValueError("No H6006 bulbs were discovered.")
    async with BulbSession(bulbs) as session:
        return await session.query_status()


async def identify(bulb: Bulb, cycles: int = 3) -> None:
    try:
        async with BulbSession([bulb]) as session:
            await session.write_all({bulb.address: power_packet(True)})
            await asyncio.sleep(0.2)
            for _ in range(cycles):
                for packet in (
                    brightness_packet(DEFAULT_BRIGHTNESS),
                    rgb_packet(255, 30, 30),
                    rgb_packet(30, 255, 30),
                    rgb_packet(30, 30, 255),
                ):
                    await session.write_all({bulb.address: packet})
                    await asyncio.sleep(0.35)
    finally:
        await restore_default_state([bulb])


async def funny(bulbs: Sequence[Bulb], loops: int = 3) -> None:
    if not bulbs:
        return

    try:
        async with BulbSession(bulbs) as session:
            await session.write_all({bulb.address: power_packet(True) for bulb in bulbs})
            await asyncio.sleep(0.2)
            await session.write_all(
                {bulb.address: brightness_packet(DEFAULT_BRIGHTNESS) for bulb in bulbs}
            )
            await asyncio.sleep(0.2)

            cycle_colors = [
                (255, 40, 40),
                (40, 255, 80),
                (60, 120, 255),
            ]
            for _ in range(loops):
                for shift in range(len(cycle_colors)):
                    await session.write_all(
                        {
                            bulb.address: rgb_packet(
                                *cycle_colors[(index + shift) % len(cycle_colors)]
                            )
                            for index, bulb in enumerate(bulbs)
                        }
                    )
                    await asyncio.sleep(0.45)

            for color in ((255, 0, 255), (0, 255, 255), (255, 220, 0)):
                await session.write_all({bulb.address: rgb_packet(*color) for bulb in bulbs})
                await asyncio.sleep(0.35)
    finally:
        await restore_default_state(bulbs)
