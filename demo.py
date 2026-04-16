#!/usr/bin/env python3
"""H6006 LED demo - every trick as fast as BLE allows.

Cycles through 8 visual phases then restores bright warm white.
Always performs a fresh BLE scan for stable device references.

Usage:
    uv run python demo.py                  # 20s default
    uv run python demo.py -d 30            # 30 seconds
    uv run python demo.py -d 10 -f 0.03    # 10s, faster frames
"""

import argparse
import asyncio
import colorsys
import random
import sys
import time

from h6006ctl.ble import BulbSession, resolve_targets
from h6006ctl.protocol import (
    brightness_packet,
    color_temp_packet,
    power_packet,
    rgb_packet,
)


def hsv_rgb(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


async def demo(duration: float, delay: float):
    # Always fresh scan - demo needs real BLEDevice refs for stability
    bulbs = await resolve_targets([], use_cache=False)
    if not bulbs:
        print("No bulbs found.", file=sys.stderr)
        return 1

    n = len(bulbs)
    phases = 8
    print(f"{n} bulb(s) | {duration}s | {delay:.3f}s/frame | {phases} phases")

    dropped = 0

    async with BulbSession(bulbs) as s:
        w = s.write_all
        await w({b.address: power_packet(True) for b in bulbs})
        await asyncio.sleep(0.3)
        await w({b.address: brightness_packet(100) for b in bulbs})
        await asyncio.sleep(0.15)

        t0 = time.monotonic()
        f = 0

        while (el := time.monotonic() - t0) < duration:
            phase = int((el / duration) * phases) % phases

            try:
                if phase == 0:
                    # Rainbow sweep - all bulbs same hue
                    r, g, b = hsv_rgb(f * 0.04)
                    await w({bu.address: rgb_packet(r, g, b) for bu in bulbs})

                elif phase == 1:
                    # Per-bulb rainbow chase
                    await w({
                        bu.address: rgb_packet(*hsv_rgb(f * 0.05 + i / n))
                        for i, bu in enumerate(bulbs)
                    })

                elif phase == 2:
                    # Primary/secondary strobe
                    colors = [
                        (255, 0, 0), (0, 255, 0), (0, 0, 255),
                        (255, 255, 0), (0, 255, 255), (255, 0, 255),
                        (255, 255, 255),
                    ]
                    c = colors[f % len(colors)]
                    await w({bu.address: rgb_packet(*c) for bu in bulbs})

                elif phase == 3:
                    # Brightness pulse + hue drift
                    bri = int(abs(((f * 3) % 200) - 100))
                    await w({bu.address: brightness_packet(bri) for bu in bulbs})
                    r, g, b = hsv_rgb(f * 0.02)
                    await w({bu.address: rgb_packet(r, g, b) for bu in bulbs})

                elif phase == 4:
                    # CT sweep warm <-> cool
                    pos = ((f * 2) % 120) / 120.0
                    k = int(2700 + (6500 - 2700) * (1 - abs(2 * pos - 1)))
                    await w({bu.address: color_temp_packet(k) for bu in bulbs})

                elif phase == 5:
                    # Random per-bulb
                    await w({
                        bu.address: rgb_packet(
                            random.randint(0, 255),
                            random.randint(0, 255),
                            random.randint(0, 255),
                        )
                        for bu in bulbs
                    })

                elif phase == 6:
                    # Police: red/blue split
                    await w({
                        bu.address: rgb_packet(
                            *((255, 0, 0) if (i + f) % 2 == 0 else (0, 0, 255))
                        )
                        for i, bu in enumerate(bulbs)
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
                    await w({bu.address: rgb_packet(*c) for bu in bulbs})

            except Exception:
                dropped += 1

            f += 1
            await asyncio.sleep(delay)

        # Restore: bright warm white
        print("Restoring warm white...")
        await w({b.address: brightness_packet(100) for b in bulbs})
        await asyncio.sleep(0.15)
        await w({b.address: color_temp_packet(2700) for b in bulbs})

    suffix = f" ({dropped} dropped)" if dropped else ""
    print(f"{f} frames | {f / duration:.1f} fps{suffix}")
    return 0


def main():
    p = argparse.ArgumentParser(description="H6006 demo mode")
    p.add_argument("-d", "--duration", type=float, default=20.0,
                   help="Demo duration in seconds (default: 20)")
    p.add_argument("-f", "--delay", type=float, default=0.05,
                   help="Inter-frame delay in seconds (default: 0.05)")
    args = p.parse_args()
    raise SystemExit(asyncio.run(demo(args.duration, args.delay)))


if __name__ == "__main__":
    main()
