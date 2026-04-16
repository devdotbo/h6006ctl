#include <furi.h>
#include <furi_hal_bt.h>
#include <bt/bt_service/bt.h>
#include <furi_hal.h>
#include "govee_h6006.h"

#define TAG "GoveeBLE"
#define SCAN_DURATION_MS 10000
#define SCAN_INTERVAL_MS 100

typedef struct {
    FuriThread* thread;
    FuriMessageQueue* queue;
    bool scanning;
    void (*device_found_callback)(uint8_t* address, const char* name, int8_t rssi);
    // GAP callback will be added when GAP API is available
    void* gap_callback_context;
} BleScanner;

typedef struct {
    uint8_t address[6];
    char name[32];
    int8_t rssi;
} BleDevice;

static bool is_govee_device(const char* name) {
    if(!name) return false;
    // H6006 devices typically show as "ihoment_H6006_XXXX" or "Govee_H6006_XXXX"
    return (strstr(name, "H6006") != NULL) ||
           (strstr(name, "H6104") != NULL) ||
           (strstr(name, "H6160") != NULL) ||
           (strstr(name, "H6163") != NULL) ||
           (strstr(name, "ihoment") != NULL) ||
           (strstr(name, "Govee") != NULL);
}

// Process BLE advertisement data (for future use with real GAP API)
#ifdef FUTURE_GAP_API
static void process_advertisement(BleScanner* scanner, uint8_t* addr, uint8_t* data, uint8_t data_len, int8_t rssi) {
    char name[32] = {0};
    uint8_t name_len = 0;
    
    // Parse advertisement data for device name
    for(uint8_t i = 0; i < data_len; ) {
        if(i + 1 >= data_len) break;
        uint8_t len = data[i];
        if(i + len + 1 > data_len) break;
        uint8_t type = data[i + 1];
        
        if(type == 0x09 || type == 0x08) { // Complete or shortened local name
            name_len = len - 1;
            if(name_len > 31) name_len = 31;
            memcpy(name, &data[i + 2], name_len);
            name[name_len] = '\0';
            break;
        }
        
        i += len + 1;
    }
    
    // Filter for Govee devices or show all if no name
    if(is_govee_device(name) || name_len == 0) {
        if(scanner->device_found_callback) {
            scanner->device_found_callback(
                addr,
                name[0] ? name : "Unknown BLE",
                rssi
            );
        }
    }
}
#endif

static int32_t ble_scanner_thread(void* context) {
    BleScanner* scanner = context;
    FURI_LOG_I(TAG, "BLE Scanner thread started");
    
    // Set up BT for scanning
    furi_record_open(RECORD_BT);
    
    // Ensure BT is started and not in advertising mode
    if(furi_hal_bt_is_active()) {
        furi_hal_bt_stop_advertising();
        furi_delay_ms(100);
    }
    
    // Start BLE scanning using available API
    FURI_LOG_I(TAG, "Starting BLE scan");
    
    // Try to use BT service for scanning
    // For now, we'll simulate scanning and gradually add real implementation
    uint32_t scan_time = 0;
    static uint8_t sim_devices_found = 0;
    
    while(scanner->scanning && scan_time < SCAN_DURATION_MS) {
        // Simulate finding devices for testing
        // This will be replaced with actual GAP/HCI scanning
        if(sim_devices_found < 3 && (scan_time % 2000) == 0) {
            uint8_t sim_addr[6] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, (uint8_t)(0xF0 + sim_devices_found)};
            char sim_name[32];
            int8_t sim_rssi = -60 - (sim_devices_found * 5);
            
            switch(sim_devices_found) {
                case 0:
                    snprintf(sim_name, sizeof(sim_name), "Govee_H6006_%02X%02X", sim_addr[4], sim_addr[5]);
                    break;
                case 1:
                    snprintf(sim_name, sizeof(sim_name), "ihoment_H6160_%02X%02X", sim_addr[4], sim_addr[5]);
                    break;
                case 2:
                    snprintf(sim_name, sizeof(sim_name), "Unknown_BLE_%02X%02X", sim_addr[4], sim_addr[5]);
                    break;
            }
            
            // Filter for Govee devices or unknown devices
            if(is_govee_device(sim_name) || strstr(sim_name, "Unknown") != NULL) {
                FURI_LOG_I(TAG, "Found device: %s, RSSI: %d", sim_name, sim_rssi);
                
                if(scanner->device_found_callback) {
                    scanner->device_found_callback(sim_addr, sim_name, sim_rssi);
                }
            }
            sim_devices_found++;
        }
        
        furi_delay_ms(SCAN_INTERVAL_MS);
        scan_time += SCAN_INTERVAL_MS;
    }
    
    FURI_LOG_I(TAG, "BLE scan completed");
    
    furi_record_close(RECORD_BT);
    FURI_LOG_I(TAG, "BLE Scanner thread stopped");
    return 0;
}

BleScanner* ble_scanner_alloc() {
    BleScanner* scanner = malloc(sizeof(BleScanner));
    if(!scanner) {
        return NULL;
    }

    scanner->queue = furi_message_queue_alloc(10, sizeof(BleDevice));
    if(!scanner->queue) {
        free(scanner);
        return NULL;
    }

    scanner->thread = furi_thread_alloc();
    if(!scanner->thread) {
        furi_message_queue_free(scanner->queue);
        free(scanner);
        return NULL;
    }

    furi_thread_set_name(scanner->thread, "BleScanner");
    furi_thread_set_stack_size(scanner->thread, 2048);
    furi_thread_set_context(scanner->thread, scanner);
    furi_thread_set_callback(scanner->thread, ble_scanner_thread);
    scanner->scanning = false;
    scanner->device_found_callback = NULL;
    scanner->gap_callback_context = NULL;
    return scanner;
}

void ble_scanner_free(BleScanner* scanner) {
    if(scanner->scanning) {
        scanner->scanning = false;
        furi_thread_join(scanner->thread);
    }
    furi_thread_free(scanner->thread);
    furi_message_queue_free(scanner->queue);
    free(scanner);
}

void ble_scanner_start(BleScanner* scanner, void (*callback)(uint8_t*, const char*, int8_t)) {
    scanner->device_found_callback = callback;
    scanner->scanning = true;
    furi_thread_start(scanner->thread);
}

void ble_scanner_stop(BleScanner* scanner) {
    scanner->scanning = false;
    furi_thread_join(scanner->thread);
}
