#pragma once

#include <stdint.h>
#include <stdbool.h>

typedef struct BleConnection BleConnection;

// Connection management
BleConnection* ble_connection_alloc(uint8_t* address);
void ble_connection_free(BleConnection* conn);
bool ble_connection_connect(BleConnection* conn);
void ble_connection_disconnect(BleConnection* conn);

// Packet sending
bool ble_connection_send_packet(BleConnection* conn, uint8_t* packet);

// Command convenience functions
bool ble_connection_set_power(BleConnection* conn, bool on);
bool ble_connection_set_brightness(BleConnection* conn, uint8_t brightness);
bool ble_connection_set_color(BleConnection* conn, uint8_t r, uint8_t g, uint8_t b);
bool ble_connection_set_white(BleConnection* conn, uint16_t temperature);
