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

## Attribution

This standalone CLI was informed by prior public research, especially:

- `flippinhutt/govee-H6006-HA`
- `chvolkmann/govee_btled`
- `wez/govee2mqtt`

Those projects helped narrow the packet format, but this repo only documents the sanitized subset that was confirmed on real H6006 bulbs during implementation.
