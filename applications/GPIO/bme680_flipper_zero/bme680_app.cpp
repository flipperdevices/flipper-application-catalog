#include "furi.h"
#include "furi_hal.h"
#include "gui/gui.h"
#include "gui/canvas.h"
#include <furi_hal_i2c.h>
#include <furi_hal_gpio.h>
#include <furi_hal_bus.h>
#include "bme68x.h"
#include "bme68x_defs.h"
#include <stdio.h> // snprintf
#include <string.h>
#include <math.h>
#include <storage/storage.h>

// BME680 I2C address options
#define BME680_I2C_ADDR_LOW  0x77
#define BME680_I2C_ADDR_HIGH 0x76
#define BME680_I2C_TIMEOUT   100

#define BME680_CONFIG_FILE    "/ext/apps_data/bme680/config.bin"
#define BME680_CONFIG_MAGIC   0x42534D45 // "BSME"
#define BME680_CONFIG_VERSION 1

// Application States
typedef enum {
    AppState_Main,
    AppState_Settings,
    AppState_About,
    AppState_StartConfirm,
    AppState_Legend, // Legend screen with icon explanations and author
} AppState;

// Enumeration for options in the settings menu
typedef enum {
    SettingsItem_Start,
    SettingsItem_Address,
    SettingsItem_OperationMode,
    SettingsItem_GasSensor, // Enable/disable heater (gas)
    SettingsItem_Altitude, // Altitude in meters for sea-level pressure calc
    SettingsItem_Legend, // Legend: icons and author info
    SettingsItem_DarkMode,
    SettingsItem_Count
} SettingsItem;

// Configuration structure for persistent storage
typedef struct {
    uint32_t magic;
    uint8_t version;
    uint8_t i2c_address;
    uint8_t op_mode;
    bool gas_enabled;
    bool dark_mode;
    float altitude_m;
} BME680Config;

// Structure to store application state
typedef struct {
    Gui* gui;
    ViewPort* view_port;
    FuriMutex* mutex;
    AppState current_state;
    bool running;
    bool is_sensor_initialized;
    bool started;
    struct bme68x_dev bme;
    struct bme68x_conf conf;
    struct bme68x_data sensor_data[3];
    uint8_t settings_cursor;
    uint8_t i2c_address;
    uint8_t op_mode;
    int8_t last_error;
    bool dark_mode;

    // Sensor readings
    float temperature;
    float pressure;
    float humidity;
    uint32_t gas_resistance;
    uint8_t data_status;
    uint16_t sample_interval_ms;
    uint16_t sample_elapsed_ms;
    uint16_t heatr_dur_ms;
    bool gas_enabled; // heater/gas toggle
    float dew_point_c; // calculated dew point
    float altitude_m; // user altitude [m] for sea-level pressure calc
    // Scroll state for main screen cards
    uint8_t list_offset; // index of the first visible item (0..items_count-visible)
    // Legend pan (2D)
    int16_t legend_pan_x;
    int16_t legend_pan_y;
} BME680App;

// --- Configuration File Functions ---

static bool bme680_save_config(BME680App* app) {
    Storage* storage = (Storage*)furi_record_open(RECORD_STORAGE);

    // Create directory if it doesn't exist
    storage_simply_mkdir(storage, "/ext/apps_data/bme680");

    File* file = storage_file_alloc(storage);

    bool success = false;
    if(storage_file_open(file, BME680_CONFIG_FILE, FSAM_WRITE, FSOM_CREATE_ALWAYS)) {
        BME680Config config = {
            .magic = BME680_CONFIG_MAGIC,
            .version = BME680_CONFIG_VERSION,
            .i2c_address = app->i2c_address,
            .op_mode = app->op_mode,
            .gas_enabled = app->gas_enabled,
            .dark_mode = app->dark_mode,
            .altitude_m = app->altitude_m,
        };

        size_t written = storage_file_write(file, &config, sizeof(BME680Config));
        success = (written == sizeof(BME680Config));
        storage_file_close(file);

        if(success) {
            FURI_LOG_I("BME680", "Config saved: %zu bytes to %s", written, BME680_CONFIG_FILE);
        } else {
            FURI_LOG_E(
                "BME680",
                "Failed to write config (wrote %zu/%zu bytes)",
                written,
                sizeof(BME680Config));
        }
    } else {
        FURI_LOG_E("BME680", "Failed to open config file for writing: %s", BME680_CONFIG_FILE);
    }

    storage_file_free(file);
    furi_record_close(RECORD_STORAGE);

    return success;
}

static bool bme680_load_config(BME680App* app) {
    Storage* storage = (Storage*)furi_record_open(RECORD_STORAGE);
    File* file = storage_file_alloc(storage);

    bool success = false;
    if(storage_file_open(file, BME680_CONFIG_FILE, FSAM_READ, FSOM_OPEN_EXISTING)) {
        BME680Config config;
        memset(&config, 0, sizeof(BME680Config));
        size_t read = storage_file_read(file, &config, sizeof(BME680Config));
        storage_file_close(file);

        FURI_LOG_I("BME680", "Read %zu bytes from config", read);
        FURI_LOG_I(
            "BME680",
            "Magic: 0x%08X (expected 0x%08X)",
            (unsigned int)config.magic,
            (unsigned int)BME680_CONFIG_MAGIC);
        FURI_LOG_I("BME680", "Version: %u (expected %u)", config.version, BME680_CONFIG_VERSION);

        if(read == sizeof(BME680Config) && config.magic == BME680_CONFIG_MAGIC &&
           config.version == BME680_CONFIG_VERSION) {
            // Validate values before applying
            if(config.i2c_address == BME680_I2C_ADDR_LOW ||
               config.i2c_address == BME680_I2C_ADDR_HIGH) {
                app->i2c_address = config.i2c_address;
            }

            app->op_mode = config.op_mode;
            app->gas_enabled = config.gas_enabled;
            app->dark_mode = config.dark_mode;

            if(config.altitude_m >= 0.0f && config.altitude_m <= 5000.0f) {
                app->altitude_m = config.altitude_m;
            }

            success = true;
            FURI_LOG_I(
                "BME680",
                "Config loaded: addr=0x%02X gas=%d dark=%d alt=%.0fm",
                app->i2c_address,
                app->gas_enabled,
                app->dark_mode,
                (double)app->altitude_m);
        } else {
            FURI_LOG_W("BME680", "Invalid config file or version mismatch");
        }
    } else {
        FURI_LOG_I("BME680", "No config file found at %s, using defaults", BME680_CONFIG_FILE);
    }

    storage_file_free(file);
    furi_record_close(RECORD_STORAGE);

    return success;
}

// --- Platform specific BME68X functions ---

int8_t bme68x_i2c_read(uint8_t reg_addr, uint8_t* reg_data, uint32_t length, void* intf_ptr) {
    if(!intf_ptr) return BME68X_E_NULL_PTR;
    BME680App* app = static_cast<BME680App*>(intf_ptr);

    furi_hal_i2c_acquire(&furi_hal_i2c_handle_external);

    bool success_tx = furi_hal_i2c_tx_ext(
        &furi_hal_i2c_handle_external,
        app->i2c_address << 1,
        false,
        &reg_addr,
        1,
        FuriHalI2cBeginStart,
        FuriHalI2cEndAwaitRestart,
        BME680_I2C_TIMEOUT);

    bool success_rx = false;
    if(success_tx) {
        success_rx = furi_hal_i2c_rx_ext(
            &furi_hal_i2c_handle_external,
            app->i2c_address << 1,
            false,
            reg_data,
            length,
            FuriHalI2cBeginRestart,
            FuriHalI2cEndStop,
            BME680_I2C_TIMEOUT);
    }

    furi_hal_i2c_release(&furi_hal_i2c_handle_external);

    return (success_tx && success_rx) ? BME68X_OK : BME68X_E_COM_FAIL;
}

int8_t
    bme68x_i2c_write(uint8_t reg_addr, const uint8_t* reg_data, uint32_t length, void* intf_ptr) {
    if(!intf_ptr) return BME68X_E_NULL_PTR;
    BME680App* app = static_cast<BME680App*>(intf_ptr);

    // Avoid VLA; BME68x uses small writes – guard length
    if(length > 31) return BME68X_E_COM_FAIL;
    uint8_t write_buffer[32];
    write_buffer[0] = reg_addr;
    memcpy(&write_buffer[1], reg_data, length);

    furi_hal_i2c_acquire(&furi_hal_i2c_handle_external);
    bool success = furi_hal_i2c_tx_ext(
        &furi_hal_i2c_handle_external,
        app->i2c_address << 1,
        false,
        write_buffer,
        length + 1,
        FuriHalI2cBeginStart,
        FuriHalI2cEndStop,
        BME680_I2C_TIMEOUT);
    furi_hal_i2c_release(&furi_hal_i2c_handle_external);

    return success ? BME68X_OK : BME68X_E_COM_FAIL;
}

void bme68x_delay_us(uint32_t period, void* intf_ptr) {
    UNUSED(intf_ptr);
    furi_delay_us(period);
}

// --- Sensor Core Logic ---

static bool bme680_apply_heater(BME680App* app) {
    struct bme68x_heatr_conf heatr_conf;
    memset(&heatr_conf, 0, sizeof(heatr_conf));
    if(app->gas_enabled) {
        heatr_conf.enable = BME68X_ENABLE;
        heatr_conf.heatr_temp = 320;
        heatr_conf.heatr_dur = 150;
    } else {
        heatr_conf.enable = BME68X_DISABLE;
        heatr_conf.heatr_temp = 0;
        heatr_conf.heatr_dur = 0;
    }
    int8_t rslt = bme68x_set_heatr_conf(BME68X_FORCED_MODE, &heatr_conf, &app->bme);
    app->last_error = rslt;
    if(rslt == BME68X_OK) {
        app->heatr_dur_ms = heatr_conf.heatr_dur;
        return true;
    }
    return false;
}

static bool init_bme680(BME680App* app) {
    app->last_error = BME68X_OK;
    app->is_sensor_initialized = false;

    // Test I2C communication first
    furi_hal_i2c_acquire(&furi_hal_i2c_handle_external);
    bool is_device_ready = furi_hal_i2c_is_device_ready(
        &furi_hal_i2c_handle_external, app->i2c_address << 1, BME680_I2C_TIMEOUT);
    furi_hal_i2c_release(&furi_hal_i2c_handle_external);

    if(!is_device_ready) {
        FURI_LOG_E("BME680", "I2C device not ready at 0x%02X", app->i2c_address);
        return false;
    }
    FURI_LOG_I("BME680", "I2C device detected at 0x%02X", app->i2c_address);

    app->bme.read = bme68x_i2c_read;
    app->bme.write = bme68x_i2c_write;
    app->bme.delay_us = bme68x_delay_us;
    app->bme.intf = BME68X_I2C_INTF;
    app->bme.intf_ptr = app;
    app->bme.amb_temp = 25;

    app->last_error = bme68x_init(&app->bme);
    if(app->last_error != BME68X_OK) {
        FURI_LOG_E("BME680", "Init failed: %d", app->last_error);
        return false;
    }
    FURI_LOG_I("BME680", "bme68x_init OK");

    app->conf.os_hum = BME68X_OS_16X;
    app->conf.os_pres = BME68X_OS_16X;
    app->conf.os_temp = BME68X_OS_16X;
    app->conf.filter = BME68X_FILTER_OFF;
    app->last_error = bme68x_set_conf(&app->conf, &app->bme);
    if(app->last_error != BME68X_OK) {
        FURI_LOG_E("BME680", "Set Conf failed: %d", app->last_error);
        return false;
    }

    if(!bme680_apply_heater(app)) {
        FURI_LOG_E("BME680", "Set Heatr Conf failed: %d", app->last_error);
        return false;
    }
    app->op_mode = BME68X_FORCED_MODE; // forced mode used in reads

    app->is_sensor_initialized = true;
    FURI_LOG_I("BME680", "Sensor initialized successfully.");
    return true;
}

// Function to read data from BME680
static bool read_bme680(BME680App* app) {
    bool success = false;
    uint8_t n_fields = 0;

    // 1) Start forced measurement now
    int8_t rslt = bme68x_set_op_mode(app->op_mode, &app->bme);
    if(rslt != BME68X_OK) {
        app->last_error = rslt;
        return false;
    }

    // 2) Wait TPH duration (us) + heater duration (ms) + small margin
    uint32_t meas_us = bme68x_get_meas_dur(app->op_mode, &app->conf, &app->bme);
    uint32_t total_us = meas_us + ((uint32_t)app->heatr_dur_ms * 1000U) + 2000U; // +2ms margin
    if(total_us > 1000000U) total_us = 1000000U; // clamp to 1s just in case
    furi_delay_us(total_us);

    // 3) Poll get_data a few times until we get at least one field
    //    (niektóre konfiguracje wymagają krótkiego sondowania)
    const uint8_t max_attempts = 5;
    for(uint8_t attempt = 0; attempt < max_attempts; attempt++) {
        rslt = bme68x_get_data(app->op_mode, app->sensor_data, &n_fields, &app->bme);
        if((rslt == BME68X_OK) && (n_fields > 0)) break;
        furi_delay_ms(5);
    }

    app->last_error = rslt;

    if((rslt == BME68X_OK) && (n_fields > 0)) {
        // 4) Wybierz najświeższe pole (z NEW_DATA); jeśli brak flagi, weź ostatnie
        uint8_t idx = 0;
        for(uint8_t i = 0; i < n_fields; i++) {
            if(app->sensor_data[i].status & BME68X_NEW_DATA_MSK) idx = i;
        }

        // 5) Zaktualizuj odczyty
        const struct bme68x_data* d = &app->sensor_data[idx];
        furi_mutex_acquire(app->mutex, FuriWaitForever);
        app->temperature = d->temperature;
        app->pressure = d->pressure / 100.0f;
        app->humidity = d->humidity;
        app->gas_resistance = (uint32_t)d->gas_resistance;
        app->data_status = d->status;
        // Compute dew point (Magnus formula)
        {
            const float a = 17.62f;
            const float b = 243.12f;
            float rh = app->humidity;
            if(rh < 0.1f) rh = 0.1f; // avoid log(0)
            float gamma = logf(rh / 100.0f) + (a * app->temperature) / (b + app->temperature);
            app->dew_point_c = (b * gamma) / (a - gamma);
        }
        furi_mutex_release(app->mutex);

        success = true;
    } else {
        // brak danych – pozostaw ostatnie wartości, last_error już ustawiony
        FURI_LOG_W("BME680", "No data (rslt=%d, fields=%u)", rslt, n_fields);
    }

    return success;
}

// Definicja pomocniczej funkcji przeliczenia na ciśnienie na poziomie morza (NPM)
static float bme680_sea_level_pressure_hpa(float p_local_hpa, float t_c, float alt_m) {
    if(alt_m <= 0.01f) return p_local_hpa;
    float t_k = t_c + 273.15f;
    if(t_k < 200.0f) t_k = 200.0f; // zabezpieczenie
    // Wzór barometryczny ze standardowym gradientem temperatury
    float factor = 1.0f - (0.0065f * alt_m) / t_k;
    if(factor <= 0.0f) factor = 0.0001f;
    return p_local_hpa * powf(factor, -5.257f);
}

// --- Drawing Logic ---

// ICON BITMAPS (10x10 px, XBM-like, LSB-first per byte)
// Możesz podmienić zawartość poniższych tablic na własne bitmapy.
static const uint8_t ICON_THERMO_10x10[] = {
    // Ikona: ICON_THERMO
    0x70, 0x03, // ....###.##
    0x50, 0x01, // ....#.#.#.
    0x50, 0x01, // ....#.#.#.
    0x50, 0x01, // ....#.#.#.
    0x50, 0x03, // ....#.#.##
    0x50, 0x00, // ....#.#...
    0x50, 0x00, // ....#.#...
    0x88, 0x00, // ...#...#..
    0x88, 0x00, // ...#...#..
    0xf8, 0x00, // ...#####..
};
static const uint8_t ICON_PRESSURE_10x10[] = {
    0x00, 0x00, // ..........
    0x00, 0x00, // ..........
    0x18, 0x00, // ...##.....
    0x3c, 0x00, // ..####....
    0x7e, 0x00, // .######...
    0xdb, 0x00, // ##.##.##..
    0x18, 0x00, // ...##.....
    0xd8, 0x00, // ...##.##..
    0xd8, 0x00, // ...##.##..
    0x18, 0x00, // ...##.....
};
static const uint8_t ICON_DROP_10x10[] = {
    // Ikona: ICON_DROP
    0x00, 0x00, // ..........
    0x10, 0x00, // ....#.....
    0x10, 0x00, // ....#.....
    0x28, 0x00, // ...#.#....
    0x44, 0x00, // ..#...#...
    0x82, 0x00, // .#.....#..
    0x82, 0x00, // .#.....#..
    0x82, 0x00, // .#.....#..
    0x44, 0x00, // ..#...#...
    0x38, 0x00, // ...###....
};
static const uint8_t ICON_FLAME_10x10[] = {
    // płomyk
    0x08, 0x00, // ...#......
    0x1C, 0x00, // ..###.....
    0x1C, 0x00, // ..###.....
    0x3E, 0x00, // .#####....
    0x36, 0x00, // .##.##....
    0x1C, 0x00, // ..###.....
    0x08, 0x00, // ...#......
    0x08, 0x00, // ...#......
    0x00, 0x00, //
    0x00, 0x00, //
};

// Small helpers for rounded frames and icons
static void draw_round_frame(Canvas* canvas, int x, int y, int w, int h, int r) {
    // Try rounded frame if available, fall back to normal frame if not
    // Most Flipper SDKs provide canvas_draw_rframe
    canvas_draw_rframe(canvas, x, y, w, h, r);
}

// Ikony rysowane z tablicy bajtów (XBM). Argumenty x,y traktujemy jako środek ikony.
static void draw_icon_thermo(Canvas* canvas, int cx, int cy) {
    const int w = 10, h = 10;
    canvas_draw_xbm(canvas, cx - w / 2, cy - h / 2, w, h, ICON_THERMO_10x10);
}

static void draw_icon_pressure(Canvas* canvas, int cx, int cy) {
    const int w = 10, h = 10;
    canvas_draw_xbm(canvas, cx - w / 2, cy - h / 2, w, h, ICON_PRESSURE_10x10);
}

static void draw_icon_drop(Canvas* canvas, int cx, int cy) {
    const int w = 10, h = 10;
    canvas_draw_xbm(canvas, cx - w / 2, cy - h / 2, w, h, ICON_DROP_10x10);
}

static void draw_icon_flame(Canvas* canvas, int cx, int cy) {
    const int w = 10, h = 10;
    canvas_draw_xbm(canvas, cx - w / 2, cy - h / 2, w, h, ICON_FLAME_10x10);
}

static void draw_legend_screen(Canvas* canvas, BME680App* app) {
    canvas_clear(canvas);
    if(app->dark_mode) {
        canvas_set_color(canvas, ColorBlack);
        canvas_draw_box(canvas, 0, 0, 128, 64);
        canvas_set_color(canvas, ColorWhite);
    } else {
        canvas_set_color(canvas, ColorBlack);
    }

    // Content area with panning
    const int content_w = 200; // virtual width
    const int content_h = 100; // virtual height (slightly larger, no fixed title)
    int16_t ox = app->legend_pan_x;
    int16_t oy = app->legend_pan_y;
    if(ox < 0) ox = 0;
    if(oy < 0) oy = 0;
    int16_t max_ox = (content_w > 128) ? (content_w - 128) : 0;
    int16_t max_oy = (content_h > 64) ? (content_h - 64) : 0;
    if(ox > max_ox) ox = max_ox;
    if(oy > max_oy) oy = max_oy;
    // store clamped (optional)
    app->legend_pan_x = ox;
    app->legend_pan_y = oy;

    canvas_set_font(canvas, FontSecondary);
    // Rows (y positions in content space)
    int base_x = 6; // left margin in content
    int y = 4; // start near the top (no fixed title)
    int row = 0;
    char buf[64];

    // Row 0: Thermometer - Temperature
    // ICON PLACEHOLDER (bitmap): Temperature – podmień ICON_THERMO_10x10
    draw_icon_thermo(canvas, (base_x + 5) - ox, (y + 6) - oy);
    snprintf(buf, sizeof(buf), "Thermometer - Temperature");
    canvas_draw_str(canvas, (base_x + 16) - ox, (y + 10) - oy, buf);
    y += 16;
    row++;

    // Row 1: Gauge - Pressure local/SLP
    // ICON PLACEHOLDER (bitmap): Pressure – podmień ICON_PRESSURE_10x10
    draw_icon_pressure(canvas, (base_x + 5) - ox, (y + 6) - oy);
    snprintf(buf, sizeof(buf), "Gauge - Pressure local/SLP");
    canvas_draw_str(canvas, (base_x + 16) - ox, (y + 10) - oy, buf);
    y += 16;
    row++;

    // Row 2: Drop - Humidity, Dew point
    // ICON PLACEHOLDER (bitmap): Humidity/Dew – podmień ICON_DROP_10x10
    draw_icon_drop(canvas, (base_x + 5) - ox, (y + 6) - oy);
    snprintf(buf, sizeof(buf), "Drop - Humidity, Dew point");
    canvas_draw_str(canvas, (base_x + 16) - ox, (y + 10) - oy, buf);
    y += 16;
    row++;

    // Row 3: Flame - Gas/Heater
    // ICON PLACEHOLDER (bitmap): Gas/Heater – podmień ICON_FLAME_10x10
    draw_icon_flame(canvas, (base_x + 5) - ox, (y + 6) - oy);
    snprintf(buf, sizeof(buf), "Flame - Gas/Heater");
    canvas_draw_str(canvas, (base_x + 16) - ox, (y + 10) - oy, buf);
    y += 16;
    row++;

    // Row 4: Creator
    snprintf(buf, sizeof(buf), "Creator - Dr. Mosfet");
    canvas_draw_str(canvas, (base_x + 0) - ox, (y + 10) - oy, buf);
}

static void draw_main_screen(Canvas* canvas, BME680App* app) {
    canvas_clear(canvas);

    if(app->dark_mode) {
        canvas_set_color(canvas, ColorBlack);
        canvas_draw_box(canvas, 0, 0, 128, 64);
        canvas_set_color(canvas, ColorWhite);
    } else {
        canvas_set_color(canvas, ColorBlack);
    }

    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str_aligned(canvas, 64, 2, AlignCenter, AlignTop, "BME680 Sensor");

    bool sensor_ok;
    float temp, pres, hum;
    uint32_t gas;
    uint8_t status;
    int8_t error;
    bool started;
    float dew;
    float altitude_m;
    if(furi_mutex_acquire(app->mutex, 0) == FuriStatusOk) {
        sensor_ok = app->is_sensor_initialized;
        temp = app->temperature;
        pres = app->pressure;
        hum = app->humidity;
        gas = app->gas_resistance;
        status = app->data_status;
        error = app->last_error;
        started = app->started;
        dew = app->dew_point_c;
        altitude_m = app->altitude_m;
        furi_mutex_release(app->mutex);
    } else {
        // Bez blokowania UI – użyj ostatnich wartości (jeśli były) albo wartości domyślnych
        sensor_ok = app->is_sensor_initialized;
        temp = app->temperature;
        pres = app->pressure;
        hum = app->humidity;
        gas = app->gas_resistance;
        status = app->data_status;
        error = app->last_error;
        started = app->started;
        dew = app->dew_point_c;
        altitude_m = app->altitude_m;
    }

    if(sensor_ok) {
        canvas_set_font(canvas, FontSecondary);
        char buf[32];

        // Scrollable card layout: show 3 items, scroll with Up/Down; draw scrollbar at right
        const int items_count = 4; // 0:T, 1:P, 2:H+Dew, 3:Gas
        const int visible = 3;
        const int x = 2;
        const int w = 118; // leave room for scrollbar on the right
        const int h = 14;
        const int r = 3;
        const int y0 = 14;
        const int y_step = 16;

        int max_offset = items_count - visible;
        if(max_offset < 0) max_offset = 0;
        int offset = app->list_offset;
        if(offset > max_offset) offset = max_offset;

        for(int i = 0; i < visible; i++) {
            int idx = offset + i;
            int y = y0 + i * y_step;
            draw_round_frame(canvas, x, y, w, h, r);
            switch(idx) {
            case 0: {
                // ICON PLACEHOLDER (bitmap): Temperature – podmień ICON_THERMO_10x10
                draw_icon_thermo(canvas, x + 9, y + 7);
                snprintf(buf, sizeof(buf), "T: %.1fC", (double)temp);
                canvas_draw_str(canvas, x + 18, y + 10, buf);
            } break;
            case 1: {
                // ICON PLACEHOLDER (bitmap): Pressure – podmień ICON_PRESSURE_10x10
                float slp = bme680_sea_level_pressure_hpa(pres, temp, altitude_m);
                draw_icon_pressure(canvas, x + 9, y + 7);
                snprintf(buf, sizeof(buf), "P: %.1f/%.1fhPa", (double)pres, (double)slp);
                canvas_draw_str(canvas, x + 18, y + 10, buf);
            } break;
            case 2: {
                // ICON PLACEHOLDER (bitmap): Humidity/Dew – podmień ICON_DROP_10x10
                draw_icon_drop(canvas, x + 9, y + 7);
                snprintf(buf, sizeof(buf), "H: %.1f%%  Dew: %.1fC", (double)hum, (double)dew);
                canvas_draw_str(canvas, x + 18, y + 10, buf);
            } break;
            case 3: {
                // ICON PLACEHOLDER (bitmap): Gas/Heater – podmień ICON_FLAME_10x10
                draw_icon_flame(canvas, x + 9, y + 7);
                if(!app->gas_enabled) {
                    snprintf(buf, sizeof(buf), "G: Off");
                } else if(status & BME68X_NEW_DATA_MSK) {
                    if(status & BME68X_HEAT_STAB_MSK) {
                        snprintf(buf, sizeof(buf), "G: %lukOhm", gas / 1000);
                    } else {
                        snprintf(buf, sizeof(buf), "G: Heating...");
                    }
                } else {
                    snprintf(buf, sizeof(buf), "G: Wait...");
                }
                canvas_draw_str(canvas, x + 18, y + 10, buf);
            } break;
            default:
                break;
            }
        }

        // Scrollbar
        const int sb_x = 122; // right side
        const int sb_y = y0;
        const int sb_w = 4;
        const int sb_h = y_step * visible - 2; // height of visible area (approx)
        canvas_draw_frame(canvas, sb_x, sb_y, sb_w, sb_h);
        int slider_h = (visible * sb_h) / items_count;
        if(slider_h < 6) slider_h = 6;
        int slider_range = sb_h - slider_h;
        int slider_y = sb_y;
        if(max_offset > 0) {
            slider_y = sb_y + (offset * slider_range) / max_offset;
        }
        canvas_draw_box(canvas, sb_x + 1, slider_y + 1, sb_w - 2, slider_h - 2);
    } else {
        canvas_set_font(canvas, FontPrimary);
        if(!started) {
            canvas_draw_str_aligned(canvas, 64, 30, AlignCenter, AlignTop, "Press OK > Start");
        } else {
            canvas_draw_str_aligned(canvas, 64, 25, AlignCenter, AlignTop, "Connect sensor");
            canvas_set_font(canvas, FontSecondary);
            char buf[32];
            snprintf(buf, sizeof(buf), "Addr:0x%02X Err:%d", app->i2c_address, error);
            canvas_draw_str_aligned(canvas, 64, 40, AlignCenter, AlignTop, buf);
        }
    }
}

// Function to draw the settings screen
static void draw_settings_screen(Canvas* canvas, BME680App* app) {
    canvas_clear(canvas);
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str_aligned(canvas, 64, 5, AlignCenter, AlignTop, "Settings");

    FuriString* value_str = furi_string_alloc();
    canvas_set_font(canvas, FontSecondary);

    uint8_t start_item = (app->settings_cursor / 2) * 2;

    uint8_t scroll_height = 40;
    uint8_t scroll_y = 15;
    uint8_t slider_height = (2 * scroll_height) / SettingsItem_Count;
    uint8_t max_slider_position = scroll_height - slider_height;
    uint8_t denom = (SettingsItem_Count > 2) ? (SettingsItem_Count - 2) : 1;
    uint8_t slider_position = (start_item * max_slider_position) / denom;
    if(slider_position > max_slider_position) slider_position = max_slider_position;

    canvas_draw_frame(canvas, 120, scroll_y, 3, scroll_height);
    canvas_draw_box(canvas, 121, scroll_y + slider_position, 1, slider_height);

    for(uint8_t i = 0; i < 2 && (start_item + i) < SettingsItem_Count; i++) {
        uint8_t current_item = start_item + i;
        uint8_t y_pos = 25 + (i * 15);

        if(app->settings_cursor == current_item) {
            canvas_draw_box(canvas, 0, y_pos - 4, 118, 15);
            canvas_set_color(canvas, ColorWhite);
        } else {
            canvas_set_color(canvas, ColorBlack);
        }

        if(app->settings_cursor == current_item) {
            canvas_draw_str(canvas, 1, y_pos + 5, ">");
        }

        switch(current_item) {
        case SettingsItem_Start:
            canvas_draw_str(canvas, 5, y_pos + 5, "Start");
            break;

        case SettingsItem_Address:
            canvas_draw_str(canvas, 5, y_pos + 5, "I2C Addr:");
            furi_string_printf(value_str, "0x%02X", app->i2c_address);
            canvas_draw_str_aligned(
                canvas, 113, y_pos - 1, AlignRight, AlignTop, furi_string_get_cstr(value_str));
            break;

        case SettingsItem_OperationMode:
            canvas_draw_str(canvas, 5, y_pos + 5, "Op Mode:");
            canvas_draw_str_aligned(
                canvas,
                113,
                y_pos - 1,
                AlignRight,
                AlignTop,
                app->op_mode == BME68X_FORCED_MODE ? "Forced" : "Sleep");
            break;

        case SettingsItem_GasSensor:
            canvas_draw_str(canvas, 5, y_pos + 5, "Gas Sensor:");
            canvas_draw_str_aligned(
                canvas, 113, y_pos - 1, AlignRight, AlignTop, app->gas_enabled ? "On" : "Off");
            break;

        case SettingsItem_Altitude:
            canvas_draw_str(canvas, 5, y_pos + 5, "Altitude:");
            {
                char buf[16];
                snprintf(buf, sizeof(buf), "%.0fm", (double)app->altitude_m);
                canvas_draw_str_aligned(canvas, 113, y_pos - 1, AlignRight, AlignTop, buf);
            }
            break;

        case SettingsItem_Legend:
            canvas_draw_str(canvas, 5, y_pos + 5, "Legend");
            break;

        case SettingsItem_DarkMode:
            canvas_draw_str(canvas, 5, y_pos + 5, "Dark Mode:");
            canvas_draw_str_aligned(
                canvas, 113, y_pos - 1, AlignRight, AlignTop, app->dark_mode ? "(*)" : "( )");
            break;
        }
        canvas_set_color(canvas, ColorBlack);
    }

    furi_string_free(value_str);

    canvas_set_color(canvas, ColorBlack);
    canvas_set_font(canvas, FontSecondary);
    canvas_draw_str_aligned(canvas, 64, 60, AlignCenter, AlignBottom, "[Ok] Back");
}

static void draw_about_screen(Canvas* canvas, BME680App* app) {
    UNUSED(app);
    canvas_clear(canvas);
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str_aligned(canvas, 64, 5, AlignCenter, AlignTop, "About");

    canvas_set_font(canvas, FontSecondary);
    canvas_draw_str_aligned(canvas, 64, 30, AlignCenter, AlignTop, "BME680 Application");
    canvas_draw_str_aligned(canvas, 64, 40, AlignCenter, AlignTop, "Gas/T/P/H Sensor");

    canvas_draw_str_aligned(canvas, 64, 60, AlignCenter, AlignBottom, "[Ok] Back");
}

static void draw_start_confirm_screen(Canvas* canvas, BME680App* app) {
    UNUSED(app);
    canvas_clear(canvas);
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str_aligned(canvas, 64, 20, AlignCenter, AlignTop, "Start Measurement?");

    canvas_set_font(canvas, FontSecondary);
    canvas_draw_str_aligned(canvas, 64, 60, AlignCenter, AlignBottom, "[Ok] Start [Back] Cancel");
}

static void bme680_render_callback(Canvas* canvas, void* ctx) {
    furi_assert(ctx);
    BME680App* app = (BME680App*)ctx;

    switch(app->current_state) {
    case AppState_Main:
        draw_main_screen(canvas, app);
        break;
    case AppState_Settings:
        draw_settings_screen(canvas, app);
        break;
    case AppState_About:
        draw_about_screen(canvas, app);
        break;
    case AppState_StartConfirm:
        draw_start_confirm_screen(canvas, app);
        break;
    case AppState_Legend:
        draw_legend_screen(canvas, app);
        break;
    }
}

static void bme680_input_callback(InputEvent* input_event, void* ctx) {
    furi_assert(ctx);
    BME680App* app = (BME680App*)ctx;

    if(input_event->type == InputTypeShort || input_event->type == InputTypeRepeat) {
        switch(app->current_state) {
        case AppState_Main:
            if(input_event->key == InputKeyOk) {
                app->current_state = AppState_Settings;
            } else if(input_event->key == InputKeyBack) {
                // Back first goes to menu (Settings) before exiting the app
                app->current_state = AppState_Settings;
            } else if(input_event->key == InputKeyRight) {
                app->current_state = AppState_About;
            } else if(input_event->key == InputKeyUp || input_event->key == InputKeyDown) {
                const int items_count = 4;
                const int visible = 3;
                int max_offset = items_count - visible;
                if(max_offset < 0) max_offset = 0;
                if(input_event->key == InputKeyUp) {
                    if(app->list_offset > 0) app->list_offset--;
                } else {
                    if(app->list_offset < max_offset) app->list_offset++;
                }
            }
            break;

        case AppState_Settings:
            if(input_event->key == InputKeyUp) {
                if(app->settings_cursor > 0)
                    app->settings_cursor--;
                else
                    app->settings_cursor = SettingsItem_Count - 1;
            } else if(input_event->key == InputKeyDown) {
                app->settings_cursor++;
                if(app->settings_cursor >= SettingsItem_Count) app->settings_cursor = 0;
            } else if(input_event->key == InputKeyLeft || input_event->key == InputKeyRight) {
                bool config_changed = false;

                if(app->settings_cursor == SettingsItem_Address) {
                    app->i2c_address = (app->i2c_address == BME680_I2C_ADDR_LOW) ?
                                           BME680_I2C_ADDR_HIGH :
                                           BME680_I2C_ADDR_LOW;
                    config_changed = true;
                } else if(app->settings_cursor == SettingsItem_GasSensor) {
                    app->gas_enabled = !app->gas_enabled;
                    if(app->is_sensor_initialized) {
                        bme680_apply_heater(app);
                    }
                    config_changed = true;
                } else if(app->settings_cursor == SettingsItem_Altitude) {
                    float step = 5.0f;
                    if(input_event->key == InputKeyLeft)
                        app->altitude_m -= step;
                    else
                        app->altitude_m += step;
                    if(app->altitude_m < 0.0f) app->altitude_m = 0.0f;
                    if(app->altitude_m > 5000.0f) app->altitude_m = 5000.0f;
                    config_changed = true;
                }

                if(config_changed) {
                    bme680_save_config(app);
                }
            } else if(input_event->key == InputKeyOk) {
                if(app->settings_cursor == SettingsItem_Start) {
                    app->current_state = AppState_StartConfirm;
                } else if(app->settings_cursor == SettingsItem_DarkMode) {
                    app->dark_mode = !app->dark_mode;
                    bme680_save_config(app);
                } else if(app->settings_cursor == SettingsItem_Legend) {
                    // Open Legend screen and reset pan
                    app->legend_pan_x = 0;
                    app->legend_pan_y = 0;
                    app->current_state = AppState_Legend;
                }
            } else if(input_event->key == InputKeyBack) {
                app->running = false;
            }
            break;

        case AppState_About:
            if(input_event->key == InputKeyOk || input_event->key == InputKeyBack) {
                app->current_state = AppState_Main;
            }
            break;

        case AppState_StartConfirm:
            if(input_event->key == InputKeyOk) {
                app->started = true;
                app->is_sensor_initialized = false;
                app->current_state = AppState_Main;
            } else if(input_event->key == InputKeyBack) {
                app->current_state = AppState_Settings;
            }
            break;
        case AppState_Legend: {
            // 2D panning with arrows; Back/Ok returns to Settings
            const int step = 6;
            if(input_event->key == InputKeyLeft) {
                if(app->legend_pan_x > 0) app->legend_pan_x -= step;
                if(app->legend_pan_x < 0) app->legend_pan_x = 0;
            } else if(input_event->key == InputKeyRight) {
                app->legend_pan_x += step;
            } else if(input_event->key == InputKeyUp) {
                if(app->legend_pan_y > 0) app->legend_pan_y -= step;
                if(app->legend_pan_y < 0) app->legend_pan_y = 0;
            } else if(input_event->key == InputKeyDown) {
                app->legend_pan_y += step;
            } else if(input_event->key == InputKeyBack || input_event->key == InputKeyOk) {
                app->current_state = AppState_Settings;
            }
        } break;
        }
    }
}

static BME680App* bme680_app_alloc() {
    BME680App* app = (BME680App*)malloc(sizeof(BME680App));
    furi_assert(app);

    app->running = true;
    app->is_sensor_initialized = false;
    app->started = false;
    app->current_state = AppState_Settings;
    app->last_error = BME68X_OK;
    // Set defaults first
    app->i2c_address = BME680_I2C_ADDR_LOW;
    app->op_mode = BME68X_FORCED_MODE;
    app->dark_mode = false;
    app->settings_cursor = 0;
    app->sample_interval_ms = 1000;
    app->sample_elapsed_ms = 0;
    app->gas_enabled = true;
    app->dew_point_c = 0.0f;
    app->altitude_m = 0.0f;
    app->list_offset = 0;
    app->legend_pan_x = 0;
    app->legend_pan_y = 0;

    app->temperature = 0.0f;
    app->pressure = 0.0f;
    app->humidity = 0.0f;
    app->gas_resistance = 0;
    app->data_status = 0;

    // Initialize mutex BEFORE loading config
    app->mutex = furi_mutex_alloc(FuriMutexTypeNormal);

    // Load saved configuration (will override defaults if valid file exists)
    bme680_load_config(app);

    app->view_port = view_port_alloc();
    view_port_draw_callback_set(app->view_port, bme680_render_callback, app);
    view_port_input_callback_set(app->view_port, bme680_input_callback, app);

    app->gui = (Gui*)furi_record_open(RECORD_GUI);
    gui_add_view_port(app->gui, app->view_port, GuiLayerFullscreen);

    return app;
}

static void bme680_app_free(BME680App* app) {
    furi_assert(app);
    gui_remove_view_port(app->gui, app->view_port);
    view_port_free(app->view_port);
    furi_record_close(RECORD_GUI);
    furi_mutex_free(app->mutex);
    free(app);
}

extern "C" int32_t bme680_app(void* p) {
    UNUSED(p);
    BME680App* app = bme680_app_alloc();

    while(app->running) {
        if(app->started) {
            if(!app->is_sensor_initialized) {
                app->is_sensor_initialized = init_bme680(app);
            }
            if(app->is_sensor_initialized && app->sample_elapsed_ms >= app->sample_interval_ms) {
                read_bme680(app);
                app->sample_elapsed_ms = 0;
            }
        }

        view_port_update(app->view_port);
        furi_delay_ms(50);
        app->sample_elapsed_ms += 50;
    }

    bme680_app_free(app);
    return 0;
}
