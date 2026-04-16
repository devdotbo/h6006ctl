#!/usr/bin/env python3
"""H6006 LED demo - every trick as fast as BLE allows.

Cycles through 8 visual phases then restores bright warm white.
Uses parallel writes, per-bulb health tracking, and session cycling
to work around the H6006's ~15s firmware connection timeout.

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

from h6006ctl.ble import BulbSession, resolve_targets
from h6006ctl.protocol import (
    WRITE_UUID,
    brightness_packet,
    color_temp_packet,
    power_packet,
    rgb_packet,
)

# Reconnect before the H6006 firmware kills the connection (~15s limit).
SESSION_SECONDS = 12.0


def hsv_rgb(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


async def run_session(bulbs, duration, delay, state):
    """Run one BLE session worth of demo frames. Mutates state dict."""
    f = state["frame"]
    phases = 8
    total_dur = state["total_duration"]
    t_global = state["t_global"]

    async with BulbSession(bulbs) as session:
        alive = dict(session._clients)
        n = len(alive)

        async def w(packets):
            to_send = {a: p for a, p in packets.items() if a in alive}
            if not to_send:
                return
            results = await asyncio.gather(
                *(alive[a].write_gatt_char(WRITE_UUID, p, response=False)
                  for a, p in to_send.items()),
                return_exceptions=True,
            )
            for addr, result in zip(to_send, results):
                if isinstance(result, BaseException):
                    del alive[addr]
                    state["lost"] += 1
                else:
                    state["sent"] += 1

        t0 = time.monotonic()

        while True:
            el_global = time.monotonic() - t_global
            el_session = time.monotonic() - t0

            if el_global >= total_dur:
                break
            if el_session >= duration:
                break
            if not alive:
                break

            phase = int((el_global / total_dur) * phases) % phases

            if phase == 0:
                r, g, b = hsv_rgb(f * 0.04)
                await w({a: rgb_packet(r, g, b) for a in alive})

            elif phase == 1:
                addrs = list(alive)
                await w({
                    a: rgb_packet(*hsv_rgb(f * 0.05 + i / max(len(addrs), 1)))
                    for i, a in enumerate(addrs)
                })

            elif phase == 2:
                colors = [
                    (255, 0, 0), (0, 255, 0), (0, 0, 255),
                    (255, 255, 0), (0, 255, 255), (255, 0, 255),
                    (255, 255, 255),
                ]
                c = colors[f % len(colors)]
                await w({a: rgb_packet(*c) for a in alive})

            elif phase == 3:
                bri = int(abs(((f * 3) % 200) - 100))
                await w({a: brightness_packet(bri) for a in alive})
                r, g, b = hsv_rgb(f * 0.02)
                await w({a: rgb_packet(r, g, b) for a in alive})

            elif phase == 4:
                pos = ((f * 2) % 120) / 120.0
                k = int(2700 + 3800 * (1 - abs(2 * pos - 1)))
                await w({a: color_temp_packet(k) for a in alive})

            elif phase == 5:
                await w({
                    a: rgb_packet(
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255),
                    )
                    for a in alive
                })

            elif phase == 6:
                addrs = list(alive)
                await w({
                    a: rgb_packet(
                        *((255, 0, 0) if (i + f) % 2 == 0 else (0, 0, 255))
                    )
                    for i, a in enumerate(addrs)
                })

            elif phase == 7:
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

        state["frame"] = f
        return len(alive) > 0


async def demo(duration: float, delay: float):
    bulbs = await resolve_targets([], use_cache=False)
    if not bulbs:
        print("No bulbs found.", file=sys.stderr)
        return 1

    n = len(bulbs)
    phases = 8
    session_count = max(1, int(duration / SESSION_SECONDS) + 1)
    print(f"{n} bulb(s) | {duration}s | {delay:.3f}s/frame | {phases} phases | reconnect every {SESSION_SECONDS:.0f}s")

    state = {
        "frame": 0,
        "sent": 0,
        "lost": 0,
        "total_duration": duration,
        "t_global": time.monotonic(),
    }

    cycle = 0
    while time.monotonic() - state["t_global"] < duration:
        cycle += 1
        remaining = duration - (time.monotonic() - state["t_global"])
        if remaining <= 0:
            break
        session_dur = min(SESSION_SECONDS, remaining)
        ok = await run_session(bulbs, session_dur, delay, state)
        if time.monotonic() - state["t_global"] < duration:
            # Brief pause between session cycles for clean reconnect
            await asyncio.sleep(0.1)

    # Restore
    elapsed = time.monotonic() - state["t_global"]
    f = state["frame"]
    print(f"\n{f} frames in {elapsed:.1f}s ({f / max(elapsed, 0.01):.1f} fps)")
    print(f"  {state['sent']} writes delivered, {state['lost']} lost, {cycle} session(s)")

    print("Restoring warm white...")
    try:
        async with BulbSession(bulbs) as session:
            clients = session._clients
            for addr, client in clients.items():
                await client.write_gatt_char(WRITE_UUID, brightness_packet(100), response=False)
            await asyncio.sleep(0.1)
            for addr, client in clients.items():
                await client.write_gatt_char(WRITE_UUID, color_temp_packet(2700), response=False)
    except Exception:
        print("  restore failed (reconnect failed)")

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
