# h6006ctl

Local Bluetooth Low Energy control for Govee H6006 bulbs - no cloud, no app, just BLE.

A small Python CLI for discovering nearby H6006 bulbs and controlling them directly. Based on live hardware verification against multiple H6006 bulbs. All examples in the public source tree use sanitized, model-level placeholders.

## Features

- **BLE discovery** of nearby `ihoment_H6006_*` bulbs
- **Address cache** - scan once with `--save`, skip BLE discovery on subsequent commands
- **Compound `set` command** - power + brightness + color in a single BLE session
- **Parallel BLE connections** - connect to multiple bulbs concurrently via `asyncio.gather`
- **Full control** - power, brightness (0-100), RGB color, color temperature (2700-6500K)
- **State readback** - query power, brightness, and color mode from the bulbs
- **Demo modes** - `identify`, `funny`, and a standalone `demo.py` light show
- **Flipper Zero FAP** - companion app in `flipper/` with protocol-aligned packet builders

## Quickstart

```
Python 3.12+  |  Bluetooth enabled  |  Nearby H6006 bulbs
```

```bash
uv sync --group dev
uv run h6006ctl scan                        # discover bulbs
```

## Usage

### Discover and cache

```bash
uv run h6006ctl scan                        # discover nearby bulbs
uv run h6006ctl scan --json                 # JSON output
uv run h6006ctl scan --save                 # save to address cache
```

Cached addresses let subsequent commands skip the 5-second BLE scan:

```bash
uv run h6006ctl on                          # instant (cached)
uv run h6006ctl --no-cache on               # force fresh BLE scan
```

Cache location: `$XDG_CONFIG_HOME/h6006ctl/bulbs.json` (default `~/.config/h6006ctl/bulbs.json`)

### Control

```bash
uv run h6006ctl on                          # power on all bulbs
uv run h6006ctl off ABCD                    # power off one bulb by suffix
uv run h6006ctl brightness 80
uv run h6006ctl rgb 0 0 255                 # blue
uv run h6006ctl ct 2700                     # warm white
```

### Compound set (single BLE session)

Apply multiple properties without reconnecting:

```bash
uv run h6006ctl set --on --brightness 100 --ct 2700
uv run h6006ctl set --on --brightness 80 --rgb 255 0 128
uv run h6006ctl set --off
```

`--on`/`--off` are mutually exclusive. `--rgb` and `--ct` are mutually exclusive.

### Status

```bash
uv run h6006ctl status                      # text output
uv run h6006ctl status --json               # JSON output
uv run h6006ctl status ABCD                 # one bulb
```

### Demos

```bash
uv run h6006ctl identify ABCD               # blink one bulb for labeling
uv run h6006ctl funny                       # three-color light show
uv run python demo.py                       # 20s full demo (all phases)
uv run python demo.py -d 30 -f 0.03         # 30s, faster frames
```

### Targeting

Targets can be omitted to act on all discovered bulbs, or specified as:
- Full advertising name: `ihoment_H6006_ABCD`
- BLE address (platform-dependent format)
- Unique suffix: `ABCD`

Default scan timeout is 5 seconds. Override with `--timeout`.

## Default Resting State

Demo commands restore this baseline when they finish:

| Property | Value |
|----------|-------|
| power | on |
| brightness | 100 |
| color temp | 2700K |

Regular commands (`on`, `off`, `rgb`, `ct`, `brightness`, `set`) are persistent.

## Flipper Zero

A companion Flipper Zero application lives in `flipper/`. It has protocol-aligned packet builders verified against the Python CLI. See [`flipper/README.md`](flipper/README.md) for build instructions and current status.

## Verified Hardware Behavior

All commands verified against real H6006 bulbs:

`scan` `status` `on` `off` `brightness` `rgb` `ct` `set` `identify` `funny`

One-bulb and all-bulb targeting both verified. Brightness scale is `0-100`.

## Development

```bash
uv run ruff check .
uv run python -m unittest discover -s tests
uv build
```

### Project docs

- [Protocol Notes](docs/PROTOCOL.md) - frame format, GATT UUIDs, verified command behavior
- [Hardware Testing](docs/HARDWARE_TESTING.md) - test procedures and results
- [Privacy and Sanitization](docs/PRIVACY.md) - how the public tree avoids leaking device data
- [Contributing](CONTRIBUTING.md)

## Attribution

This project is informed by reverse-engineering and open-source research from the Home Assistant and Govee communities. See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the sanitized protocol summary and upstream references.
