# H6006 Protocol Notes

This repo documents only the parts of the H6006 BLE protocol that were verified for this standalone CLI.

## GATT characteristics

- Write: `00010203-0405-0607-0809-0a0b0c0d2b11`
- Read/notify: `00010203-0405-0607-0809-0a0b0c0d2b10`

## Frame format

- 20-byte command/query frames
- Byte `0`: head byte
  - `0x33` for writes
  - `0xAA` for queries and status responses
- Byte `1`: command
  - `0x01` power
  - `0x04` brightness
  - `0x05` color / color temperature
- Byte `19`: XOR checksum of bytes `0..18`

## Verified command behavior

- Power uses `0x33 0x01 <0|1>`
- Brightness uses `0x33 0x04 <0-100>`
- RGB uses mode byte `0x0D`
- Color temperature uses mode byte `0x0D`, zero RGB payload, and big-endian kelvin bytes

Examples:

- RGB blue:
  - `33 05 0D 00 00 FF ...`
- Warm white 2700K:
  - `33 05 0D 00 00 00 0A 8C ...`

## Verified response behavior

- Brightness readback is reported on a `0-100` scale
- Blue readback:
  - `AA 05 0D 00 00 FF ...`
- Warm white 2700K readback:
  - `AA 05 0D 00 00 00 0A 8C ...`
- Power-off is reliable within the same BLE session, but a brand-new reconnect/query after power-off may read back as `on` on the tested hardware

## BLE connection behavior

- The write characteristic (`...2b11`) supports Write Without Response only. Write With Response (`response=True` in bleak) is rejected.
- The H6006 firmware disconnects BLE connections after approximately 15 seconds. This is consistent across all tested write rates (10-43 fps) and is not affected by GATT reads or write-with-response attempts. The timeout appears to be an application-level timer in the bulb firmware, not a standard BLE supervision timeout.
- Short-lived sessions (single commands, state queries) are unaffected. Long-running sessions (demos, continuous control) must cycle connections before the ~15s limit.

## Address cache

The CLI caches discovered device addresses to skip BLE scanning on repeat invocations. Cache location:

- `$XDG_CONFIG_HOME/h6006ctl/bulbs.json` (default `~/.config/h6006ctl/bulbs.json`)

The cache stores only device addresses and advertising names. It is written atomically and validated on load. Use `h6006ctl scan --save` to populate and `--no-cache` to bypass.

## Attribution

This standalone CLI was informed by prior public research, especially:

- `flippinhutt/govee-H6006-HA`
- `chvolkmann/govee_btled`
- `wez/govee2mqtt`

Those projects helped narrow the packet format, but this repo only documents the sanitized subset that was confirmed on real H6006 bulbs during implementation.
