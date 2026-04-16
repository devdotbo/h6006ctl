#!/usr/bin/env python3
"""H6006 LED demo - every trick as fast as BLE allows.

Cycles through 8 visual phases then restores bright warm white.
Uses parallel writes, per-bulb health tracking, and periodic
write-with-response to keep BLE connections alive.

Usage:
    uv run python demo.py                  # 20s, 0.02s/frame
    uv run python demo.py -d 30            # 30 seconds
    uv run python demo.py -d 10 -f 0.01    # 10s, fastest
"""

import argparse
import asyncio
import colorsys
import random
import sys
import time

from bleak import BleakClient

from h6006ctl.ble import BulbSession, resolve_targets
from h6006ctl.protocol import (
    WRITE_UUID,
    brightness_packet,
    color_temp_packet,
    power_packet,
    rgb_packet,
)

# Every Nth frame, use write-with-response to flush the BLE queue
# and refresh the link layer supervision timer.
KEEPALIVE_INTERVAL = 50


def hsv_rgb(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


async def demo(duration: float, delay: float):
    bulbs = await resolve_targets([], use_cache=False)
    if not bulbs:
        print("No bulbs found.", file=sys.stderr)
        return 1

    n = len(bulbs)
    phases = 8
    print(f"{n} bulb(s) | {duration}s | {delay:.3f}s/frame | {phases} phases")

    async with BulbSession(bulbs) as session:
        alive: dict[str, BleakClient] = dict(session._clients)
        stats = {b.address: {"name": b.name, "sent": 0, "lost_at": None} for b in bulbs}

        async def w(packets: dict[str, bytes]) -> None:
            """Parallel write with per-bulb isolation."""
            to_send = {a: p for a, p in packets.items() if a in alive}
            if not to_send:
                return
            use_response = (f % KEEPALIVE_INTERVAL == 0)
            results = await asyncio.gather(
                *(alive[a].write_gatt_char(WRITE_UUID, p, response=use_response)
                  for a, p in to_send.items()),
                return_exceptions=True,
            )
            for addr, result in zip(to_send, results):
                if isinstance(result, BaseException):
                    del alive[addr]
                    stats[addr]["lost_at"] = f
                else:
                    stats[addr]["sent"] += 1

        # Init: power on, max brightness
        await w({b.address: power_packet(True) for b in bulbs})
        await asyncio.sleep(0.3)
        await w({b.address: brightness_packet(100) for b in bulbs})
        await asyncio.sleep(0.15)

        t0 = time.monotonic()
        f = 0

        while (el := time.monotonic() - t0) < duration:
            if not alive:
                print("All bulbs lost.", file=sys.stderr)
                break

            phase = int((el / duration) * phases) % phases

            if phase == 0:
                # Rainbow sweep
                r, g, b = hsv_rgb(f * 0.04)
                await w({a: rgb_packet(r, g, b) for a in alive})

            elif phase == 1:
                # Per-bulb rainbow chase
                addrs = list(alive)
                await w({
                    a: rgb_packet(*hsv_rgb(f * 0.05 + i / max(len(addrs), 1)))
                    for i, a in enumerate(addrs)
                })

            elif phase == 2:
                # Primary/secondary strobe
                colors = [
                    (255, 0, 0), (0, 255, 0), (0, 0, 255),
                    (255, 255, 0), (0, 255, 255), (255, 0, 255),
                    (255, 255, 255),
                ]
                c = colors[f % len(colors)]
                await w({a: rgb_packet(*c) for a in alive})

            elif phase == 3:
                # Brightness pulse + hue drift
                bri = int(abs(((f * 3) % 200) - 100))
                await w({a: brightness_packet(bri) for a in alive})
                r, g, b = hsv_rgb(f * 0.02)
                await w({a: rgb_packet(r, g, b) for a in alive})

            elif phase == 4:
                # CT sweep warm <-> cool
                pos = ((f * 2) % 120) / 120.0
                k = int(2700 + 3800 * (1 - abs(2 * pos - 1)))
                await w({a: color_temp_packet(k) for a in alive})

            elif phase == 5:
                # Random per-bulb
                await w({
                    a: rgb_packet(
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    )
                    for a in alive
                })

            elif phase == 6:
                # Police: red/blue split
                addrs = list(alive)
                await w({
                    a: rgb_packet(
                        *((255, 0, 0) if (i + f) % 2 == 0 else (0, 0, 255))
                    )
                    for i, a in enumerate(addrs)
                })

            elif phase == 7:
                # Complementary pairs fast swap
                pairs = [
                    ((255, 0, 0), (0, 255, 255)),
                    ((0, 255, 0), (255, 0, 255)),
                    ((0, 0, 255), (255, 255, 0)),
                    ((255, 128, 0), (0, 128, 255)),
                ]
                c = pairs[f % len(pairs)][f % 2]
                await w({a: rgb_packet(*c) for a in alive})

            f += 1
            await asyncio.sleep(delay)

        # Report
        elapsed = time.monotonic() - t0
        print(f"\n{f} frames in {elapsed:.1f}s ({f / max(elapsed, 0.01):.1f} fps)")
        for addr, s in stats.items():
            status = "alive" if addr in alive else f"lost at frame {s['lost_at']}"
            print(f"  {s['name']}: {s['sent']} writes delivered, {status}")

        # Restore - only alive bulbs
        if alive:
            print("\nRestoring warm white...")
            await w({a: brightness_packet(100) for a in alive})
            await asyncio.sleep(0.1)
            await w({a: color_temp_packet(2700) for a in alive})

    return 0


def main():
    p = argparse.ArgumentParser(description="H6006 demo mode")
    p.add_argument("-d", "--duration", type=float, default=20.0,
                   help="Demo duration in seconds (default: 20)")
    p.add_argument("-f", "--delay", type=float, default=0.02,
                   help="Inter-frame delay in seconds (default: 0.02)")
    args = p.parse_args()
    raise SystemExit(asyncio.run(demo(args.duration, args.delay)))


if __name__ == "__main__":
    main()
