#!/usr/bin/env python3
"""H6006 LED demo - perceptually optimized color at max BLE throughput.

8 visual phases using OKLCH color space for perceptually uniform
transitions, gamma-corrected brightness, and per-bulb spatial effects.
Session cycling works around the H6006 ~15s firmware timeout.

Usage:
    uv run python demo.py                  # 20s, 0.02s/frame
    uv run python demo.py -d 30            # 30 seconds
    uv run python demo.py -d 10 -f 0.01    # 10s, fastest
"""

import argparse
import asyncio
import math
import random
import sys
import time

from h6006ctl.ble import BulbSession, resolve_targets
from h6006ctl.protocol import (
    WRITE_UUID,
    brightness_packet,
    color_temp_packet,
    rgb_packet,
)

SESSION_SECONDS = 12.0

# ---------------------------------------------------------------------------
# OKLAB / OKLCH color math -- perceptually uniform color space
# ---------------------------------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

def _linear_to_srgb(c: float) -> float:
    return 1.055 * c ** (1 / 2.4) - 0.055 if c > 0.0031308 else 12.92 * c

def _oklab_to_linear_rgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l_cubed = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3
    return (
        +4.0767416621 * l_cubed - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l_cubed + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l_cubed - 0.7034186147 * m + 1.7076147010 * s,
    )

def oklch(L: float, C: float, h_deg: float) -> tuple[int, int, int]:
    """OKLCH -> clamped sRGB bytes. L in [0,1], C in [0,~0.4], h in degrees."""
    h = math.radians(h_deg % 360)
    a, b = C * math.cos(h), C * math.sin(h)
    r, g, b = _oklab_to_linear_rgb(L, a, b)
    return (
        max(0, min(255, int(_linear_to_srgb(max(0, r)) * 255 + 0.5))),
        max(0, min(255, int(_linear_to_srgb(max(0, g)) * 255 + 0.5))),
        max(0, min(255, int(_linear_to_srgb(max(0, b)) * 255 + 0.5))),
    )

def gamma_bri(t: float) -> int:
    """Perceptual brightness: t in [0,1] -> H6006 value 0-100 with gamma 2.2."""
    return max(0, min(100, int(100 * t ** 2.2)))

# ---------------------------------------------------------------------------
# Demo session
# ---------------------------------------------------------------------------

async def run_session(bulbs, duration, delay, state):
    f = state["frame"]
    total_dur = state["total_duration"]
    t_global = state["t_global"]
    async with BulbSession(bulbs) as session:
        alive = dict(session._clients)

        async def w(packets):
            to_send = {a: p for a, p in packets.items() if a in alive}
            if not to_send:
                return
            results = await asyncio.gather(
                *(alive[a].write_gatt_char(WRITE_UUID, p, response=False)
                  for a, p in to_send.items()),
                return_exceptions=True,
            )
            for addr, result in zip(to_send, results, strict=True):
                if isinstance(result, BaseException):
                    del alive[addr]
                    state["lost"] += 1
                else:
                    state["sent"] += 1

        t0 = time.monotonic()

        while True:
            el_global = time.monotonic() - t_global
            el_session = time.monotonic() - t0
            if el_global >= total_dur or el_session >= duration or not alive:
                break

            phase = int((el_global / total_dur) * 8) % 8
            addrs = list(alive)
            na = len(addrs)

            if phase == 0:
                # OKLCH rainbow sweep - perceptually uniform hue rotation
                hue = (f * 4.0) % 360
                r, g, b = oklch(0.75, 0.15, hue)
                await w({a: rgb_packet(r, g, b) for a in addrs})

            elif phase == 1:
                # Spatial rainbow - each bulb at equidistant hue offset
                base_hue = (f * 5.0) % 360
                await w({
                    a: rgb_packet(*oklch(0.75, 0.15, base_hue + i * (360 / max(na, 1))))
                    for i, a in enumerate(addrs)
                })

            elif phase == 2:
                # Saturated strobe - OKLCH primaries (more vivid than sRGB primaries)
                # warm red, green, violet, yellow, cyan, magenta, white
                hues = [29, 142, 264, 70, 195, 330, 0]
                chroma = [0.2, 0.2, 0.2, 0.18, 0.15, 0.18, 0.0]
                light = [0.65, 0.75, 0.55, 0.85, 0.8, 0.7, 1.0]
                idx = f % len(hues)
                r, g, b = oklch(light[idx], chroma[idx], hues[idx])
                await w({a: rgb_packet(r, g, b) for a in addrs})

            elif phase == 3:
                # Gamma-corrected brightness pulse with OKLCH hue drift
                t = abs(((f * 3) % 200) - 100) / 100.0  # 0->1->0 triangle
                bri = gamma_bri(t)
                await w({a: brightness_packet(bri) for a in addrs})
                hue = (f * 2.0) % 360
                r, g, b = oklch(0.75, 0.15, hue)
                await w({a: rgb_packet(r, g, b) for a in addrs})

            elif phase == 4:
                # CT sweep warm <-> cool with per-bulb gradient
                pos = ((f * 2) % 120) / 120.0
                base_k = int(2700 + 3800 * (1 - abs(2 * pos - 1)))
                for i, a in enumerate(addrs):
                    offset = int((i / max(na - 1, 1)) * 800 - 400) if na > 1 else 0
                    k = max(2700, min(6500, base_k + offset))
                    await w({a: color_temp_packet(k)})

            elif phase == 5:
                # Aesthetic random - OKLCH constrained for vibrant colors
                await w({
                    a: rgb_packet(*oklch(
                        random.uniform(0.55, 0.85),
                        random.uniform(0.10, 0.20),
                        random.uniform(0, 360),
                    ))
                    for a in addrs
                })

            elif phase == 6:
                # Police with brightness flash
                await w({
                    a: rgb_packet(
                        *oklch(
                            0.85 if (i + f) % 2 == 0 else 0.55,
                            0.20,
                            29 if (i + f) % 2 == 0 else 264,
                        )
                    )
                    for i, a in enumerate(addrs)
                })

            elif phase == 7:
                # OKLCH complementary wave - opposite hues, spatial sweep
                base_hue = (f * 6.0) % 360
                await w({
                    a: rgb_packet(*oklch(
                        0.75,
                        0.17,
                        base_hue + 180 * (i % 2) + i * 30,
                    ))
                    for i, a in enumerate(addrs)
                })

            f += 1
            await asyncio.sleep(delay)

        state["frame"] = f
        return len(alive) > 0


async def demo(duration: float, delay: float):
    bulbs = await resolve_targets([], use_cache=False)
    if not bulbs:
        print("No bulbs found.", file=sys.stderr)
        return 1

    print(
        f"{len(bulbs)} bulb(s) | {duration}s | {delay:.3f}s/frame"
        f" | 8 phases | OKLCH | reconnect {SESSION_SECONDS:.0f}s"
    )

    state = {
        "frame": 0, "sent": 0, "lost": 0,
        "total_duration": duration,
        "t_global": time.monotonic(),
    }

    cycle = 0
    while time.monotonic() - state["t_global"] < duration:
        cycle += 1
        remaining = duration - (time.monotonic() - state["t_global"])
        if remaining <= 0:
            break
        await run_session(bulbs, min(SESSION_SECONDS, remaining), delay, state)
        if time.monotonic() - state["t_global"] < duration:
            await asyncio.sleep(0.1)

    elapsed = time.monotonic() - state["t_global"]
    f = state["frame"]
    print(f"\n{f} frames in {elapsed:.1f}s ({f / max(elapsed, 0.01):.1f} fps)")
    print(f"  {state['sent']} writes, {state['lost']} lost, {cycle} session(s)")

    print("Restoring warm white...")
    try:
        async with BulbSession(bulbs) as session:
            for client in session._clients.values():
                await client.write_gatt_char(WRITE_UUID, brightness_packet(100), response=False)
            await asyncio.sleep(0.1)
            for client in session._clients.values():
                await client.write_gatt_char(WRITE_UUID, color_temp_packet(2700), response=False)
    except Exception:
        print("  restore failed")

    return 0


def main():
    p = argparse.ArgumentParser(description="H6006 demo - OKLCH perceptual color")
    p.add_argument("-d", "--duration", type=float, default=20.0)
    p.add_argument("-f", "--delay", type=float, default=0.02)
    args = p.parse_args()
    raise SystemExit(asyncio.run(demo(args.duration, args.delay)))


if __name__ == "__main__":
    main()
