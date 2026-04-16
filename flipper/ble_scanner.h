#pragma once

#include <stdint.h>
#include <stdbool.h>

typedef struct BleScanner BleScanner;

BleScanner* ble_scanner_alloc(void);
void ble_scanner_free(BleScanner* scanner);
void ble_scanner_start(BleScanner* scanner, void (*callback)(uint8_t*, const char*, int8_t));
void ble_scanner_stop(BleScanner* scanner);
