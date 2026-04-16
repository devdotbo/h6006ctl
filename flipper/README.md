# Govee Control - Flipper Zero FAP

Flipper Zero application for controlling Govee H6006 BLE LED bulbs.

## Status

- GUI: working (submenu, popup, variable item list)
- BLE scanner: simulated (real GAP central scanning requires firmware API work)
- BLE connection: GATT writes stubbed (connection manager and keepalive loop ready)
- Protocol: aligned with verified Python CLI (`src/h6006ctl/protocol.py`)

## Protocol Alignment

All packet formats match the verified Python implementation:

| Field | Value | Notes |
|-------|-------|-------|
| Write UUID | `...2b11` | Read UUID is `...2b10` |
| RGB mode byte | `0x0D` | Not `0x02` |
| Brightness scale | 0-100 | Not 0-254 |
| CT mode byte | `0x0D` | Same as RGB mode |
| CT encoding | zero RGB + big-endian kelvin bytes 6-7 | Not mapped single byte |
| CT range | 2700-6500K | Not 2000-9000K |

## Build

Requires [ufbt](https://github.com/flipperdevices/flipperzero-ufbt) with SDK v1.3.4+.

```bash
cd flipper
ufbt build
```

## Deploy

```bash
ufbt launch    # requires connected Flipper Zero
```

## Roadmap

- Real BLE central mode scanning (requires Flipper firmware GAP API access)
- GATT write implementation for actual bulb control
- Device persistence and saved device management
- Color picker UI
