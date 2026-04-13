import unittest

from h6006ctl.ble import parse_notification
from h6006ctl.protocol import (
    BRIGHTNESS_CMD,
    COLOR_CMD,
    DEFAULT_BRIGHTNESS,
    REQUEST_HEAD,
    RGB_MODE,
    brightness_packet,
    color_temp_packet,
    rgb_packet,
)


def _build_query_response(cmd: int, payload: list[int]) -> bytes:
    frame = [REQUEST_HEAD, cmd, *payload]
    frame += [0] * (19 - len(frame))

    checksum = 0
    for byte in frame:
        checksum ^= byte
    frame.append(checksum & 0xFF)
    return bytes(frame)


class ProtocolPacketTests(unittest.TestCase):
    def test_brightness_packet_uses_public_0_to_100_scale(self) -> None:
        packet = brightness_packet(DEFAULT_BRIGHTNESS)

        self.assertEqual(packet[1], BRIGHTNESS_CMD)
        self.assertEqual(packet[2], DEFAULT_BRIGHTNESS)

    def test_rgb_packet_uses_hardware_verified_mode_byte(self) -> None:
        packet = rgb_packet(0, 0, 255)

        self.assertEqual(RGB_MODE, 0x0D)
        self.assertEqual(packet[1], COLOR_CMD)
        self.assertEqual(packet[2], RGB_MODE)
        self.assertEqual(packet[3:6], b"\x00\x00\xff")

    def test_color_temp_packet_encodes_kelvin_as_big_endian_with_zero_rgb_payload(self) -> None:
        packet = color_temp_packet(2700)

        self.assertEqual(packet[1], COLOR_CMD)
        self.assertEqual(packet[3:6], b"\x00\x00\x00")
        self.assertEqual(packet[6:8], (2700).to_bytes(2, "big"))


class NotificationParserTests(unittest.TestCase):
    def test_parse_notification_recognizes_brightness_query_frame(self) -> None:
        frame = _build_query_response(BRIGHTNESS_CMD, [DEFAULT_BRIGHTNESS])

        self.assertEqual(parse_notification(frame), ("brightness", DEFAULT_BRIGHTNESS))

    def test_parse_notification_recognizes_rgb_blue_query_frame(self) -> None:
        frame = _build_query_response(COLOR_CMD, [RGB_MODE, 0x00, 0x00, 0xFF])

        self.assertEqual(parse_notification(frame), ("rgb", (0, 0, 255)))

    def test_parse_notification_recognizes_2700k_warm_white_query_frame(self) -> None:
        frame = _build_query_response(COLOR_CMD, [RGB_MODE, 0x00, 0x00, 0x00, 0x0A, 0x8C])

        self.assertEqual(parse_notification(frame), ("ct", 2700))

    def test_parse_notification_rejects_bad_checksum(self) -> None:
        frame = bytearray(_build_query_response(COLOR_CMD, [RGB_MODE, 0x00, 0x00, 0xFF]))
        frame[-1] ^= 0x01

        self.assertIsNone(parse_notification(frame))


if __name__ == "__main__":
    unittest.main()
