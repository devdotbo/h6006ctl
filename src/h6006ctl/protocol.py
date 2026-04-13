"""Packet builders for the reverse-engineered H6006 BLE protocol."""

from __future__ import annotations

MODEL_PREFIX = "ihoment_H6006"
READ_UUID = "00010203-0405-0607-0809-0a0b0c0d2b10"
WRITE_UUID = "00010203-0405-0607-0809-0a0b0c0d2b11"

MIN_KELVIN = 2700
MAX_KELVIN = 6500
MIN_BRIGHTNESS = 0
MAX_BRIGHTNESS = 100
DEFAULT_KELVIN = MIN_KELVIN
DEFAULT_BRIGHTNESS = MAX_BRIGHTNESS

REQUEST_HEAD = 0xAA
COMMAND_HEAD = 0x33

POWER_CMD = 0x01
BRIGHTNESS_CMD = 0x04
COLOR_CMD = 0x05
RGB_MODE = 0x0D
# Verified H6006 CT writes and readbacks use the same leading mode byte as RGB.
COLOR_TEMP_MODE = RGB_MODE


def clamp_brightness(value: int) -> int:
    """Clamp user-facing brightness to the verified H6006 0-100 scale."""

    return max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, value))


def clamp_kelvin(value: int) -> int:
    """Clamp color temperature to the verified H6006 range."""

    return max(MIN_KELVIN, min(MAX_KELVIN, value))


def build_frame(cmd: int, payload: list[int]) -> bytes:
    """Build a 20-byte command packet with the protocol XOR checksum."""

    frame = [COMMAND_HEAD, cmd & 0xFF] + payload
    frame += [0] * (19 - len(frame))
    checksum = 0
    for byte in frame:
        checksum ^= byte
    frame.append(checksum & 0xFF)
    return bytes(frame)


def build_query(cmd: int) -> bytes:
    """Build a 20-byte state query packet."""

    frame = [REQUEST_HEAD, cmd & 0xFF] + [0] * 17
    checksum = 0
    for byte in frame:
        checksum ^= byte
    frame.append(checksum & 0xFF)
    return bytes(frame)


def power_packet(on: bool) -> bytes:
    return build_frame(POWER_CMD, [0x01 if on else 0x00])


def brightness_packet(value: int) -> bytes:
    return build_frame(BRIGHTNESS_CMD, [clamp_brightness(value)])


def rgb_packet(red: int, green: int, blue: int) -> bytes:
    return build_frame(
        COLOR_CMD,
        [
            RGB_MODE,
            max(0, min(255, red)),
            max(0, min(255, green)),
            max(0, min(255, blue)),
        ],
    )


def color_temp_packet(kelvin: int) -> bytes:
    kelvin = clamp_kelvin(kelvin)
    high_byte = (kelvin >> 8) & 0xFF
    low_byte = kelvin & 0xFF
    return build_frame(COLOR_CMD, [COLOR_TEMP_MODE, 0x00, 0x00, 0x00, high_byte, low_byte])
