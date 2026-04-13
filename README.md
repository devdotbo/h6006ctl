# h6006ctl

Local Bluetooth Low Energy control for Govee `H6006` bulbs.

`h6006ctl` is a small Python CLI for discovering nearby H6006 bulbs and controlling them without the Govee cloud. The implementation is based on live hardware verification against multiple H6006 bulbs and uses only sanitized, model-level examples in the public source tree.

## Features

- Discover nearby `ihoment_H6006_*` bulbs over BLE
- Control power, brightness, RGB color, and color temperature
- Target one bulb or all discovered bulbs
- Query current state from the bulbs
- Run demo commands that restore a safe default baseline afterward

## Default Resting State

Demo-style commands restore this default resting state when they finish:

- `power=True`
- `brightness=100`
- `ct=2700`

Regular commands such as `rgb`, `ct`, `brightness`, `on`, and `off` are persistent.

## Quickstart

Requirements:

- Python `3.12+`
- Bluetooth enabled on the machine running the CLI
- Nearby Govee `H6006` bulbs

Install and run local checks:

```bash
uv sync --group dev
uv run ruff check .
uv run python -m unittest discover -s tests
```

Discover bulbs:

```bash
uv run h6006ctl scan
uv run h6006ctl scan --json
```

Inspect state:

```bash
uv run h6006ctl status
uv run h6006ctl status ABCD
uv run h6006ctl status ihoment_H6006_ABCD
```

Control bulbs:

```bash
uv run h6006ctl on
uv run h6006ctl off ABCD
uv run h6006ctl brightness 100
uv run h6006ctl rgb 0 0 255
uv run h6006ctl ct 2700
```

Run demos:

```bash
uv run h6006ctl identify ABCD
uv run h6006ctl funny
```

Targets can be omitted to act on all discovered H6006 bulbs, or passed as a full advertising name, address, or unique suffix placeholder such as `ABCD`.

## Verified Hardware Behavior

The current repo has been verified against real H6006 bulbs for:

- `scan`
- `status`
- `on` / `off`
- `brightness`
- `rgb`
- `ct`
- one-bulb targeting
- all-bulb targeting
- `identify`
- `funny`

The public brightness scale is `0-100`.

## Development

Local checks:

```bash
uv run ruff check .
uv run python -m unittest discover -s tests
uv build
```

Additional project docs:

- [Protocol Notes](docs/PROTOCOL.md)
- [Hardware Testing](docs/HARDWARE_TESTING.md)
- [Privacy and Sanitization](docs/PRIVACY.md)
- [Contributing](CONTRIBUTING.md)

## Attribution

This project is informed by reverse-engineering and open-source research from the Home Assistant and Govee communities. See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the sanitized protocol summary and upstream references.
