"""Command-line interface for local H6006 BLE control."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from .ble import (
    Bulb,
    DeviceState,
    discover_bulbs,
    funny,
    get_status,
    identify,
    resolve_targets,
    set_brightness,
    set_color_temp,
    set_multiple,
    set_power,
    set_rgb,
)
from .cache import save_bulbs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="h6006ctl",
        description="Scan and control nearby Govee H6006 bulbs over Bluetooth LE.",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip address cache, force BLE scan.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Discover nearby H6006 bulbs.")
    scan.add_argument("--timeout", type=float, default=5.0)
    scan.add_argument("--json", action="store_true", dest="as_json")
    scan.add_argument(
        "--save", action="store_true", dest="save_cache",
        help="Save discovered bulbs to address cache.",
    )

    status = subparsers.add_parser("status", help="Query bulb power, brightness, and color state.")
    status.add_argument("targets", nargs="*")
    status.add_argument("--timeout", type=float, default=5.0)
    status.add_argument("--json", action="store_true", dest="as_json")

    on = subparsers.add_parser("on", help="Turn bulbs on.")
    on.add_argument("targets", nargs="*")
    on.add_argument("--timeout", type=float, default=5.0)

    off = subparsers.add_parser("off", help="Turn bulbs off.")
    off.add_argument("targets", nargs="*")
    off.add_argument("--timeout", type=float, default=5.0)

    brightness = subparsers.add_parser("brightness", help="Set brightness 0-100.")
    brightness.add_argument("value", type=int)
    brightness.add_argument("targets", nargs="*")
    brightness.add_argument("--timeout", type=float, default=5.0)

    rgb = subparsers.add_parser("rgb", help="Set RGB color.")
    rgb.add_argument("red", type=int)
    rgb.add_argument("green", type=int)
    rgb.add_argument("blue", type=int)
    rgb.add_argument("targets", nargs="*")
    rgb.add_argument("--timeout", type=float, default=5.0)

    ct = subparsers.add_parser("ct", help="Set color temperature in Kelvin.")
    ct.add_argument("kelvin", type=int)
    ct.add_argument("targets", nargs="*")
    ct.add_argument("--timeout", type=float, default=5.0)

    identify_parser = subparsers.add_parser("identify", help="Blink one bulb so you can label it.")
    identify_parser.add_argument("target")
    identify_parser.add_argument("--timeout", type=float, default=5.0)
    identify_parser.add_argument("--cycles", type=int, default=3)

    funny_parser = subparsers.add_parser("funny", help="Run a short three-color light show.")
    funny_parser.add_argument("targets", nargs="*")
    funny_parser.add_argument("--timeout", type=float, default=5.0)
    funny_parser.add_argument("--loops", type=int, default=3)

    set_cmd = subparsers.add_parser("set", help="Set multiple properties in a single BLE session.")
    set_cmd.add_argument("targets", nargs="*")
    set_cmd.add_argument("--timeout", type=float, default=5.0)
    power_group = set_cmd.add_mutually_exclusive_group()
    power_group.add_argument("--on", action="store_true", default=None, dest="power_on")
    power_group.add_argument("--off", action="store_true", default=None, dest="power_off")
    set_cmd.add_argument("--brightness", type=int, default=None)
    set_cmd.add_argument("--rgb", type=int, nargs=3, metavar=("R", "G", "B"), default=None)
    set_cmd.add_argument("--ct", type=int, metavar="KELVIN", default=None)

    return parser


async def async_main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            bulbs = await discover_bulbs(timeout=args.timeout)
            if args.save_cache:
                save_bulbs([{"address": b.address, "name": b.name} for b in bulbs])
            return _print_scan(bulbs, as_json=args.as_json)

        if args.command == "status":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            states = await get_status(bulbs)
            return _print_status(bulbs, states, as_json=args.as_json)

        if args.command == "on":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            await set_power(bulbs, on=True)
            print(_describe_targets("Turned on", bulbs))
            return 0

        if args.command == "off":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            await set_power(bulbs, on=False)
            print(_describe_targets("Turned off", bulbs))
            return 0

        if args.command == "brightness":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            _require_range("brightness", args.value, 0, 100)
            await set_brightness(bulbs, args.value)
            print(_describe_targets(f"Brightness set to {args.value}", bulbs))
            return 0

        if args.command == "rgb":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            for name, value in (("red", args.red), ("green", args.green), ("blue", args.blue)):
                _require_range(name, value, 0, 255)
            await set_rgb(bulbs, args.red, args.green, args.blue)
            print(
                _describe_targets(
                    f"RGB set to ({args.red}, {args.green}, {args.blue})",
                    bulbs,
                )
            )
            return 0

        if args.command == "ct":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            _require_range("kelvin", args.kelvin, 2700, 6500)
            await set_color_temp(bulbs, args.kelvin)
            print(_describe_targets(f"Color temperature set to {args.kelvin}K", bulbs))
            return 0

        if args.command == "identify":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                [args.target], timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            await identify(bulbs[0], cycles=args.cycles)
            print(f"Identified {bulbs[0].name} ({bulbs[0].address})")
            return 0

        if args.command == "funny":
            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            await funny(bulbs, loops=args.loops)
            print(_describe_targets("Ran the funny light show on", bulbs))
            return 0

        if args.command == "set":
            if args.rgb is not None and args.ct is not None:
                raise ValueError("Cannot use --rgb and --ct together.")
            power = None
            if args.power_on:
                power = True
            elif args.power_off:
                power = False
            brightness = args.brightness
            rgb = tuple(args.rgb) if args.rgb is not None else None
            kelvin = args.ct

            if power is None and brightness is None and rgb is None and kelvin is None:
                raise ValueError(
                    "set requires at least one property"
                    " (--on/--off, --brightness, --rgb, --ct)."
                )

            if brightness is not None:
                _require_range("brightness", brightness, 0, 100)
            if rgb is not None:
                for name, val in zip(("red", "green", "blue"), rgb, strict=True):
                    _require_range(name, val, 0, 255)
            if kelvin is not None:
                _require_range("kelvin", kelvin, 2700, 6500)

            use_cache = not args.no_cache
            bulbs = await resolve_targets(
                args.targets, timeout=args.timeout, use_cache=use_cache,
            )
            _require_bulbs(bulbs)
            await set_multiple(bulbs, power=power, brightness=brightness, rgb=rgb, kelvin=kelvin)
            parts = []
            if power is not None:
                parts.append("on" if power else "off")
            if brightness is not None:
                parts.append(f"brightness={brightness}")
            if rgb is not None:
                parts.append(f"rgb={rgb}")
            if kelvin is not None:
                parts.append(f"ct={kelvin}")
            print(_describe_targets(f"Set {', '.join(parts)} on", bulbs))
            return 0
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unknown command")
    return 2


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


def _require_bulbs(bulbs: Sequence[Bulb]) -> None:
    if not bulbs:
        raise ValueError("No H6006 bulbs were discovered. Move them closer and try scan again.")


def _describe_targets(prefix: str, bulbs: Sequence[Bulb]) -> str:
    names = ", ".join(f"{bulb.name} ({bulb.address})" for bulb in bulbs)
    return f"{prefix}: {names}"


def _require_range(name: str, value: int, minimum: int, maximum: int) -> None:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")


def _print_scan(bulbs: Sequence[Bulb], *, as_json: bool) -> int:
    if as_json:
        print(
            json.dumps(
                [
                    {
                        "name": bulb.name,
                        "address": bulb.address,
                        "suffix": bulb.suffix,
                        "rssi": bulb.rssi,
                        "manufacturer_data": {
                            hex(key): value.hex() for key, value in bulb.manufacturer_data.items()
                        },
                    }
                    for bulb in bulbs
                ],
                indent=2,
            )
        )
    elif bulbs:
        for bulb in bulbs:
            print(f"{bulb.name:20} {bulb.address}  RSSI={bulb.rssi}")
    else:
        print("No H6006 bulbs discovered.")
    return 0


def _print_status(
    bulbs: Sequence[Bulb], states: dict[str, DeviceState], *, as_json: bool
) -> int:
    payload = []
    for bulb in bulbs:
        state = states[bulb.address]
        payload.append(
            {
                "name": bulb.name,
                "address": bulb.address,
                "power": state.power,
                "brightness": state.brightness,
                "mode": state.mode,
                "rgb": state.rgb,
                "kelvin": state.kelvin,
            }
        )

    if as_json:
        print(json.dumps(payload, indent=2))
        return 0

    for item in payload:
        color = f"rgb={item['rgb']}" if item["rgb"] else f"ct={item['kelvin']}"
        print(
            f"{item['name']:20} {item['address']}  "
            f"power={item['power']} brightness={item['brightness']} {color}"
        )
    return 0
