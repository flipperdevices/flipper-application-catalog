#include <furi.h>
#include <furi_hal.h>
#include <gui/gui.h>
#include <input/input.h>
#include <notification/notification.h>
#include <notification/notification_messages.h>
#include <storage/storage.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "bme680.h"

// ============================================================
// Types
// ============================================================

typedef enum {
    AlarmLedOff,
    AlarmLedRed,
    AlarmLedGreen,
    AlarmLedOrange,
    AlarmLedCount,
} AlarmLedColor;

static const char* led_names[] = {"Off", "Red", "Green", "Orange"};

typedef struct {
    uint8_t       i2c_addr;
    bool          temp_fahrenheit;
    uint8_t       read_interval;
    uint16_t      heater_temp;
    bool          alarm_iaq_on;
    uint16_t      alarm_iaq_thresh;
    bool          alarm_temp_on;
    int16_t       alarm_temp_low;
    int16_t       alarm_temp_high;
    bool          alarm_hum_on;
    uint8_t       alarm_hum_low;
    uint8_t       alarm_hum_high;
    AlarmLedColor alarm_led;
    bool          alarm_vibro;
    bool          alarm_sound;
    bool          log_enabled;
    uint8_t       log_interval; // how many readings between log writes
} AppSettings;

typedef enum { PageOverview, PageGas, PageComfort, DataPageCount } DataPage;

// Menu items: settings + alarms + logging in one scrollable list
typedef enum {
    MenuI2cAddr,
    MenuTempUnit,
    MenuInterval,
    MenuHeaterTemp,
    MenuSep1,          // --- Alarms ---
    MenuIaqOn,
    MenuIaqThresh,
    MenuTempAlarmOn,
    MenuTempLow,
    MenuTempHigh,
    MenuHumAlarmOn,
    MenuHumLow,
    MenuHumHigh,
    MenuSep2,          // --- Outputs ---
    MenuLed,
    MenuVibro,
    MenuSound,
    MenuSep3,          // --- Logging ---
    MenuLogOn,
    MenuLogInterval,
    MenuItemCount,
} MenuItem;

typedef struct {
    Gui*              gui;
    ViewPort*         viewport;
    FuriMessageQueue* event_queue;
    FuriTimer*        timer;
    NotificationApp*  notif;
    Bme680Device      sensor;
    AppSettings       s;
    bool              sensor_found;
    bool              reading;
    DataPage          page;
    bool              menu_open;
    int               menu_sel;
    uint32_t          read_count;
    float             iaq;
    uint8_t           iaq_level;
    bool              alarm_active;
    char              alarm_reason[24];
    // Logging
    uint32_t          log_counter;
    bool              log_header_written;
    char              log_filename[64];
} Bme680App;

// ============================================================
// Helpers
// ============================================================

static const char* iaq_labels[] = {
    "Excellent", "Good", "Moderate", "Poor", "Unhealthy", "Hazardous", "N/A"};

static uint8_t get_iaq_level(float iaq) {
    if(iaq < 0.0f) return 6;
    if(iaq <= 50.0f) return 0;
    if(iaq <= 100.0f) return 1;
    if(iaq <= 150.0f) return 2;
    if(iaq <= 200.0f) return 3;
    if(iaq <= 300.0f) return 4;
    return 5;
}

static float c_to_f(float c) { return c * 9.0f / 5.0f + 32.0f; }
static int clamp_i(int v, int lo, int hi) { return (v < lo) ? lo : (v > hi) ? hi : v; }

static const char* comfort_str(float tc, float h) {
    bool cold = tc < 18.0f, hot = tc > 28.0f;
    bool dry = h < 30.0f, humid = h > 60.0f;
    if(cold && dry)   return "Cold & Dry";
    if(cold && humid)  return "Cold & Damp";
    if(cold)           return "Cold";
    if(hot && humid)   return "Hot & Humid";
    if(hot && dry)     return "Hot & Dry";
    if(hot)            return "Hot";
    if(dry)            return "Dry";
    if(humid)          return "Humid";
    if(tc >= 20.0f && tc <= 26.0f && h >= 30.0f && h <= 60.0f)
        return "Comfortable";
    return "Fair";
}

static float heat_index_c(float tc, float rh) {
    float tf = c_to_f(tc);
    if(tf < 80.0f) return tc;
    float hi = -42.379f + 2.04901523f * tf + 10.14333127f * rh
        - 0.22475541f * tf * rh - 0.00683783f * tf * tf
        - 0.05481717f * rh * rh + 0.00122874f * tf * tf * rh
        + 0.00085282f * tf * rh * rh - 0.00000199f * tf * tf * rh * rh;
    return (hi - 32.0f) * 5.0f / 9.0f;
}

// ============================================================
// SD Card Logging
// ============================================================

#define LOG_DIR  "/ext/apps_data/bme680"

static void log_ensure_filename(Bme680App* app) {
    if(app->log_filename[0] != '\0') return;
    uint32_t ts = furi_hal_rtc_get_timestamp();
    // Convert unix timestamp to date/time components
    uint32_t days = ts / 86400;
    uint32_t rem = ts % 86400;
    uint8_t hh = rem / 3600;
    uint8_t mm = (rem % 3600) / 60;
    uint8_t ss = rem % 60;
    // Days since 1970-01-01
    uint32_t y = 1970;
    while(1) {
        uint32_t dy = ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0) ? 366 : 365;
        if(days < dy) break;
        days -= dy;
        y++;
    }
    bool leap = ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0);
    uint8_t mdays[] = {31, (uint8_t)(leap ? 29 : 28), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    uint8_t mo = 1;
    for(int i = 0; i < 12; i++) {
        if(days < mdays[i]) break;
        days -= mdays[i];
        mo++;
    }
    snprintf(app->log_filename, sizeof(app->log_filename),
        LOG_DIR "/%04lu-%02u-%02u_%02u%02u%02u.csv",
        y, mo, (uint8_t)(days + 1), hh, mm, ss);
}

static void log_write(Bme680App* app) {
    if(!app->s.log_enabled) return;

    app->log_counter++;
    if(app->log_counter < app->s.log_interval) return;
    app->log_counter = 0;

    log_ensure_filename(app);

    Storage* storage = furi_record_open(RECORD_STORAGE);
    storage_simply_mkdir(storage, LOG_DIR);

    File* file = storage_file_alloc(storage);
    bool opened = storage_file_open(file, app->log_filename, FSAM_WRITE, FSOM_OPEN_APPEND);

    if(opened) {
        uint64_t fsize = storage_file_size(file);
        if(fsize == 0) {
            const char* header = "timestamp,date,time,temp_c,humidity,pressure_hpa,gas_ohm,gas_valid,heat_stable,iaq\n";
            storage_file_write(file, header, strlen(header));
        }

        uint32_t ts = furi_hal_rtc_get_timestamp();
        // Convert to date/time
        uint32_t days = ts / 86400;
        uint32_t rem = ts % 86400;
        uint8_t hh = rem / 3600;
        uint8_t mm = (rem % 3600) / 60;
        uint8_t ss = rem % 60;
        uint32_t y = 1970;
        while(1) {
            uint32_t dy = ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0) ? 366 : 365;
            if(days < dy) break;
            days -= dy;
            y++;
        }
        bool leap = ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0);
        uint8_t mdays[] = {31, (uint8_t)(leap ? 29 : 28), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
        uint8_t mo = 1;
        for(int i = 0; i < 12; i++) {
            if(days < mdays[i]) break;
            days -= mdays[i];
            mo++;
        }
        uint8_t dd = (uint8_t)(days + 1);

        Bme680Data* d = &app->sensor.data;
        char line[148];
        int len = snprintf(line, sizeof(line),
            "%lu,%04lu-%02u-%02u,%02u:%02u:%02u,%.2f,%.2f,%.2f,%.0f,%d,%d,%.0f\n",
            ts,
            y, mo, dd,
            hh, mm, ss,
            (double)d->temperature,
            (double)d->humidity,
            (double)d->pressure,
            (double)d->gas_resistance,
            d->gas_valid ? 1 : 0,
            d->heat_stable ? 1 : 0,
            (double)app->iaq);
        storage_file_write(file, line, (uint16_t)len);
        storage_file_close(file);
    }

    storage_file_free(file);
    furi_record_close(RECORD_STORAGE);
}

// ============================================================
// Alarms
// ============================================================

static void check_alarms(Bme680App* app) {
    AppSettings* s = &app->s;
    Bme680Data* d = &app->sensor.data;
    app->alarm_active = false;
    app->alarm_reason[0] = '\0';

    float dt = s->temp_fahrenheit ? c_to_f(d->temperature) : d->temperature;

    if(s->alarm_iaq_on && app->iaq >= 0.0f && app->iaq > (float)s->alarm_iaq_thresh) {
        app->alarm_active = true;
        snprintf(app->alarm_reason, sizeof(app->alarm_reason), "IAQ > %u", s->alarm_iaq_thresh);
    }
    if(!app->alarm_active && s->alarm_temp_on) {
        if(dt < (float)s->alarm_temp_low) {
            app->alarm_active = true;
            snprintf(app->alarm_reason, sizeof(app->alarm_reason), "Temp LOW");
        } else if(dt > (float)s->alarm_temp_high) {
            app->alarm_active = true;
            snprintf(app->alarm_reason, sizeof(app->alarm_reason), "Temp HIGH");
        }
    }
    if(!app->alarm_active && s->alarm_hum_on) {
        if(d->humidity < (float)s->alarm_hum_low) {
            app->alarm_active = true;
            snprintf(app->alarm_reason, sizeof(app->alarm_reason), "Hum LOW");
        } else if(d->humidity > (float)s->alarm_hum_high) {
            app->alarm_active = true;
            snprintf(app->alarm_reason, sizeof(app->alarm_reason), "Hum HIGH");
        }
    }

    if(app->alarm_active) {
        if(s->alarm_led == AlarmLedRed)
            notification_message(app->notif, &sequence_set_only_red_255);
        else if(s->alarm_led == AlarmLedGreen)
            notification_message(app->notif, &sequence_set_only_green_255);
        else if(s->alarm_led == AlarmLedOrange) {
            notification_message(app->notif, &sequence_set_only_red_255);
            notification_message(app->notif, &sequence_set_only_green_255);
        }
        if(s->alarm_vibro) {
            static const NotificationSequence seq_vib = {
                &message_vibro_on, &message_delay_100, &message_vibro_off, NULL};
            notification_message(app->notif, &seq_vib);
        }
        if(s->alarm_sound) {
            static const NotificationSequence seq_beep = {
                &message_note_c5, &message_delay_100, &message_sound_off, NULL};
            notification_message(app->notif, &seq_beep);
        }
    } else {
        if(s->alarm_led != AlarmLedOff)
            notification_message(app->notif, &sequence_reset_rgb);
    }
}

// ============================================================
// Drawing - Data pages
// ============================================================

static void draw_page_dots(Canvas* canvas, int cur, int total) {
    int sx = 64 - (total * 4);
    for(int i = 0; i < total; i++) {
        int x = sx + i * 8;
        if(i == cur) canvas_draw_disc(canvas, x, 62, 2);
        else canvas_draw_circle(canvas, x, 62, 2);
    }
}

static void draw_alarm_bar(Canvas* canvas, Bme680App* app) {
    if(!app->alarm_active) return;
    canvas_draw_box(canvas, 0, 55, 128, 9);
    canvas_set_color(canvas, ColorWhite);
    char buf[32];
    snprintf(buf, sizeof(buf), "!! %s !!", app->alarm_reason);
    canvas_draw_str_aligned(canvas, 64, 56, AlignCenter, AlignTop, buf);
    canvas_set_color(canvas, ColorBlack);
}

static void draw_overview(Canvas* canvas, Bme680App* app) {
    char buf[48];
    Bme680Data* d = &app->sensor.data;
    const char* u = app->s.temp_fahrenheit ? "F" : "C";
    float t = app->s.temp_fahrenheit ? c_to_f(d->temperature) : d->temperature;

    canvas_set_font(canvas, FontSecondary);
    snprintf(buf, sizeof(buf), "T: %.1f*%s", (double)t, u);
    canvas_draw_str(canvas, 0, 8, buf);
    snprintf(buf, sizeof(buf), "H: %.1f%%", (double)d->humidity);
    canvas_draw_str(canvas, 68, 8, buf);

    snprintf(buf, sizeof(buf), "P: %.1f hPa", (double)d->pressure);
    canvas_draw_str(canvas, 0, 18, buf);

    float av = 17.625f, bv = 243.04f;
    float al = (av * d->temperature) / (bv + d->temperature) + logf(d->humidity / 100.0f);
    float dew = (bv * al) / (av - al);
    if(app->s.temp_fahrenheit) dew = c_to_f(dew);
    snprintf(buf, sizeof(buf), "Dew: %.1f*%s", (double)dew, u);
    canvas_draw_str(canvas, 68, 18, buf);

    canvas_draw_line(canvas, 0, 21, 127, 21);

    canvas_set_font(canvas, FontPrimary);
    if(app->iaq >= 0.0f) {
        snprintf(buf, sizeof(buf), "IAQ: %.0f %s", (double)app->iaq, iaq_labels[app->iaq_level]);
        canvas_draw_str(canvas, 0, 33, buf);
        canvas_draw_frame(canvas, 0, 36, 128, 5);
        int bw = clamp_i((int)(app->iaq * 126.0f / 500.0f), 0, 126);
        canvas_draw_box(canvas, 1, 37, bw, 3);
    } else {
        canvas_draw_str(canvas, 0, 33, "IAQ: Stabilizing...");
    }

    canvas_set_font(canvas, FontSecondary);
    snprintf(buf, sizeof(buf), "#%lu", app->read_count);
    canvas_draw_str(canvas, 0, 50, buf);

    if(app->s.log_enabled) {
        canvas_draw_str_aligned(canvas, 127, 50, AlignRight, AlignBottom, "LOG");
    }

    draw_alarm_bar(canvas, app);
}

static void draw_gas(Canvas* canvas, Bme680App* app) {
    char buf[48];
    Bme680Data* d = &app->sensor.data;

    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str(canvas, 0, 10, "Gas & Air Quality");
    canvas_draw_line(canvas, 0, 12, 127, 12);
    canvas_set_font(canvas, FontSecondary);

    if(d->gas_resistance > 1000.0f)
        snprintf(buf, sizeof(buf), "Resistance: %.1f kOhm", (double)(d->gas_resistance / 1000.0f));
    else
        snprintf(buf, sizeof(buf), "Resistance: %.0f Ohm", (double)d->gas_resistance);
    canvas_draw_str(canvas, 0, 23, buf);

    snprintf(buf, sizeof(buf), "Valid: %s  Stable: %s",
        d->gas_valid ? "Yes" : "No", d->heat_stable ? "Yes" : "No");
    canvas_draw_str(canvas, 0, 33, buf);

    snprintf(buf, sizeof(buf), "Heater: %u*C  Int: %us", app->s.heater_temp, app->s.read_interval);
    canvas_draw_str(canvas, 0, 43, buf);

    snprintf(buf, sizeof(buf), "Readings: %lu", app->read_count);
    canvas_draw_str(canvas, 0, 53, buf);

    draw_alarm_bar(canvas, app);
}

static void draw_comfort(Canvas* canvas, Bme680App* app) {
    char buf[48];
    Bme680Data* d = &app->sensor.data;
    const char* u = app->s.temp_fahrenheit ? "F" : "C";

    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str(canvas, 0, 10, "Comfort");
    canvas_draw_line(canvas, 0, 12, 127, 12);
    canvas_set_font(canvas, FontSecondary);

    const char* cmf = comfort_str(d->temperature, d->humidity);
    snprintf(buf, sizeof(buf), "Status: %s", cmf);
    canvas_draw_str(canvas, 0, 23, buf);

    float hi = heat_index_c(d->temperature, d->humidity);
    if(app->s.temp_fahrenheit) hi = c_to_f(hi);
    float actual = app->s.temp_fahrenheit ? c_to_f(d->temperature) : d->temperature;
    snprintf(buf, sizeof(buf), "Feels like: %.1f*%s (%.1f*%s)", (double)hi, u, (double)actual, u);
    canvas_draw_str(canvas, 0, 33, buf);

    float ah = (6.112f * expf((17.67f * d->temperature) / (d->temperature + 243.5f))
        * d->humidity * 2.1674f) / (273.15f + d->temperature);
    snprintf(buf, sizeof(buf), "Abs humidity: %.1f g/m3", (double)ah);
    canvas_draw_str(canvas, 0, 43, buf);

    float av = 17.625f, bv = 243.04f;
    float al = (av * d->temperature) / (bv + d->temperature) + logf(d->humidity / 100.0f);
    float dew = (bv * al) / (av - al);
    if(app->s.temp_fahrenheit) dew = c_to_f(dew);
    snprintf(buf, sizeof(buf), "Dew point: %.1f*%s", (double)dew, u);
    canvas_draw_str(canvas, 0, 53, buf);

    draw_alarm_bar(canvas, app);
}

// ============================================================
// Drawing - Menu overlay (fixed spacing)
// ============================================================

static bool is_separator(int item) {
    return item == MenuSep1 || item == MenuSep2 || item == MenuSep3;
}

static void get_menu_text(Bme680App* app, int item, char* buf, size_t len) {
    AppSettings* s = &app->s;
    const char* u = s->temp_fahrenheit ? "F" : "C";
    switch(item) {
    case MenuI2cAddr:     snprintf(buf, len, "I2C: 0x%02X", s->i2c_addr); break;
    case MenuTempUnit:    snprintf(buf, len, "Unit: %s", s->temp_fahrenheit ? "Fahr." : "Celsius"); break;
    case MenuInterval:    snprintf(buf, len, "Interval: %us", s->read_interval); break;
    case MenuHeaterTemp:  snprintf(buf, len, "Heater: %u*C", s->heater_temp); break;
    case MenuSep1:        snprintf(buf, len, "-- Alarms --"); break;
    case MenuIaqOn:       snprintf(buf, len, "IAQ: %s", s->alarm_iaq_on ? "ON" : "OFF"); break;
    case MenuIaqThresh:   snprintf(buf, len, "  Thresh: %u", s->alarm_iaq_thresh); break;
    case MenuTempAlarmOn: snprintf(buf, len, "Temp: %s", s->alarm_temp_on ? "ON" : "OFF"); break;
    case MenuTempLow:     snprintf(buf, len, "  Lo: %d*%s", s->alarm_temp_low, u); break;
    case MenuTempHigh:    snprintf(buf, len, "  Hi: %d*%s", s->alarm_temp_high, u); break;
    case MenuHumAlarmOn:  snprintf(buf, len, "Hum: %s", s->alarm_hum_on ? "ON" : "OFF"); break;
    case MenuHumLow:      snprintf(buf, len, "  Lo: %u%%", s->alarm_hum_low); break;
    case MenuHumHigh:     snprintf(buf, len, "  Hi: %u%%", s->alarm_hum_high); break;
    case MenuSep2:        snprintf(buf, len, "-- Outputs --"); break;
    case MenuLed:         snprintf(buf, len, "LED: %s", led_names[s->alarm_led]); break;
    case MenuVibro:       snprintf(buf, len, "Vibrate: %s", s->alarm_vibro ? "ON" : "OFF"); break;
    case MenuSound:       snprintf(buf, len, "Sound: %s", s->alarm_sound ? "ON" : "OFF"); break;
    case MenuSep3:        snprintf(buf, len, "-- Logging --"); break;
    case MenuLogOn:       snprintf(buf, len, "Log SD: %s", s->log_enabled ? "ON" : "OFF"); break;
    case MenuLogInterval: snprintf(buf, len, "Log every: %u reads", s->log_interval); break;
    default: buf[0] = '\0'; break;
    }
}

static void draw_menu(Canvas* canvas, Bme680App* app) {
    canvas_clear(canvas);

    // Title bar
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str(canvas, 0, 10, "Settings");
    canvas_draw_line(canvas, 0, 12, 127, 12);

    // Scrollable list area: y=14 to y=58 (44px), 10px per row = ~4 visible rows
    // Using FontSecondary which is 8px tall, with 10px line height
    const int row_h = 10;
    const int list_y = 14;
    const int list_h = 44;
    const int visible = list_h / row_h; // 4 rows

    int sel = app->menu_sel;
    int scroll = sel - visible / 2;
    if(scroll > MenuItemCount - visible) scroll = MenuItemCount - visible;
    if(scroll < 0) scroll = 0;

    canvas_set_font(canvas, FontSecondary);

    for(int vi = 0; vi < visible && (scroll + vi) < MenuItemCount; vi++) {
        int i = scroll + vi;
        int y = list_y + vi * row_h;
        char text[28];
        get_menu_text(app, i, text, sizeof(text));

        if(is_separator(i)) {
            // Centered separator text
            canvas_draw_str_aligned(canvas, 64, y + 8, AlignCenter, AlignBottom, text);
        } else if(i == sel) {
            // Inverted highlight for selected row
            canvas_draw_box(canvas, 0, y, 124, row_h);
            canvas_set_color(canvas, ColorWhite);
            char line[36];
            snprintf(line, sizeof(line), "< %s >", text);
            canvas_draw_str(canvas, 2, y + 8, line);
            canvas_set_color(canvas, ColorBlack);
        } else {
            canvas_draw_str(canvas, 4, y + 8, text);
        }
    }

    // Scrollbar
    if(MenuItemCount > visible) {
        int sb_y = list_y;
        int sb_h = list_h;
        int thumb_h = clamp_i(sb_h * visible / MenuItemCount, 4, sb_h);
        int max_scroll = MenuItemCount - visible;
        int thumb_y = sb_y + (sb_h - thumb_h) * scroll / (max_scroll > 0 ? max_scroll : 1);
        canvas_draw_box(canvas, 125, thumb_y, 3, thumb_h);
    }
}

// ============================================================
// Main draw callback
// ============================================================

static void draw_cb(Canvas* canvas, void* ctx) {
    Bme680App* app = ctx;
    canvas_clear(canvas);

    if(app->menu_open) {
        draw_menu(canvas, app);
        return;
    }

    if(!app->sensor_found) {
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str_aligned(canvas, 64, 14, AlignCenter, AlignCenter, "BME680 Searching...");
        canvas_set_font(canvas, FontSecondary);
        char buf[32];
        snprintf(buf, sizeof(buf), "Addr: 0x%02X", app->s.i2c_addr);
        canvas_draw_str_aligned(canvas, 64, 28, AlignCenter, AlignCenter, buf);
        canvas_draw_str_aligned(canvas, 64, 40, AlignCenter, AlignCenter, "SDA=C1(15) SCL=C0(16)");
        canvas_draw_str_aligned(canvas, 64, 52, AlignCenter, AlignCenter, "Retrying... Hold OK:Menu");
        draw_page_dots(canvas, app->page, DataPageCount);
        return;
    }

    switch(app->page) {
    case PageOverview: draw_overview(canvas, app); break;
    case PageGas:      draw_gas(canvas, app); break;
    case PageComfort:  draw_comfort(canvas, app); break;
    default: break;
    }

    draw_page_dots(canvas, app->page, DataPageCount);
}

// ============================================================
// Input / Timer
// ============================================================

static void input_cb(InputEvent* event, void* ctx) {
    furi_message_queue_put(((Bme680App*)ctx)->event_queue, event, FuriWaitForever);
}

static void timer_cb(void* ctx) {
    InputEvent ev = {.type = InputTypePress, .key = InputKeyMAX};
    furi_message_queue_put(((Bme680App*)ctx)->event_queue, &ev, 0);
}

static void do_reading(Bme680App* app) {
    if(!app->sensor_found || app->reading) return;
    app->reading = true;
    if(bme680_read_forced(&app->sensor, app->s.heater_temp)) {
        app->read_count++;
        app->iaq = bme680_calc_iaq(&app->sensor.data);
        app->iaq_level = get_iaq_level(app->iaq);
        check_alarms(app);
        log_write(app);
    }
    app->reading = false;
    view_port_update(app->viewport);
}

static void try_init_sensor(Bme680App* app) {
    // Try primary address
    app->sensor_found = bme680_init(&app->sensor, app->s.i2c_addr);
    if(!app->sensor_found) {
        // Try alternate address
        uint8_t alt = (app->s.i2c_addr == 0x76) ? 0x77 : 0x76;
        app->sensor_found = bme680_init(&app->sensor, alt);
        if(app->sensor_found) app->s.i2c_addr = alt;
    }
    if(app->sensor_found) {
        app->read_count = 0;
        app->iaq = -1.0f;
        app->iaq_level = 6;
        // Switch timer to reading mode
        furi_timer_stop(app->timer);
        furi_timer_start(app->timer, app->s.read_interval * 1000);
        // Immediate first reading
        timer_cb(app);
    }
    view_port_update(app->viewport);
}

static void reinit_sensor(Bme680App* app) {
    app->sensor_found = false;
    try_init_sensor(app);
    if(!app->sensor_found) {
        // Start retry timer
        furi_timer_stop(app->timer);
        furi_timer_start(app->timer, 2000);
    }
}

// ============================================================
// Menu navigation & value changes
// ============================================================

static void menu_move(Bme680App* app, int dir) {
    int next = app->menu_sel + dir;
    while(next >= 0 && next < MenuItemCount && is_separator(next)) next += dir;
    if(next >= 0 && next < MenuItemCount) app->menu_sel = next;
}

static void menu_change(Bme680App* app, int dir) {
    AppSettings* s = &app->s;
    switch(app->menu_sel) {
    case MenuI2cAddr:
        s->i2c_addr = (s->i2c_addr == 0x76) ? 0x77 : 0x76;
        reinit_sensor(app);
        break;
    case MenuTempUnit:
        s->temp_fahrenheit = !s->temp_fahrenheit;
        if(s->temp_fahrenheit) {
            s->alarm_temp_low = (int16_t)(s->alarm_temp_low * 9 / 5 + 32);
            s->alarm_temp_high = (int16_t)(s->alarm_temp_high * 9 / 5 + 32);
        } else {
            s->alarm_temp_low = (int16_t)((s->alarm_temp_low - 32) * 5 / 9);
            s->alarm_temp_high = (int16_t)((s->alarm_temp_high - 32) * 5 / 9);
        }
        break;
    case MenuInterval:
        s->read_interval = (uint8_t)clamp_i((int)s->read_interval + dir, 1, 10);
        furi_timer_stop(app->timer);
        if(app->sensor_found)
            furi_timer_start(app->timer, s->read_interval * 1000);
        break;
    case MenuHeaterTemp:
        s->heater_temp = (uint16_t)clamp_i((int)s->heater_temp + dir * 20, 200, 400);
        break;
    case MenuIaqOn:       s->alarm_iaq_on = !s->alarm_iaq_on; break;
    case MenuIaqThresh:   s->alarm_iaq_thresh = (uint16_t)clamp_i((int)s->alarm_iaq_thresh + dir * 25, 25, 500); break;
    case MenuTempAlarmOn: s->alarm_temp_on = !s->alarm_temp_on; break;
    case MenuTempLow:     s->alarm_temp_low = (int16_t)clamp_i((int)s->alarm_temp_low + dir, -40, s->alarm_temp_high - 1); break;
    case MenuTempHigh:    s->alarm_temp_high = (int16_t)clamp_i((int)s->alarm_temp_high + dir, s->alarm_temp_low + 1, 100); break;
    case MenuHumAlarmOn:  s->alarm_hum_on = !s->alarm_hum_on; break;
    case MenuHumLow:      s->alarm_hum_low = (uint8_t)clamp_i((int)s->alarm_hum_low + dir * 5, 0, s->alarm_hum_high - 5); break;
    case MenuHumHigh:     s->alarm_hum_high = (uint8_t)clamp_i((int)s->alarm_hum_high + dir * 5, s->alarm_hum_low + 5, 100); break;
    case MenuLed:         s->alarm_led = (AlarmLedColor)(((int)s->alarm_led + dir + AlarmLedCount) % AlarmLedCount); break;
    case MenuVibro:       s->alarm_vibro = !s->alarm_vibro; break;
    case MenuSound:       s->alarm_sound = !s->alarm_sound; break;
    case MenuLogOn:       s->log_enabled = !s->log_enabled; app->log_counter = 0; app->log_filename[0] = '\0'; break;
    case MenuLogInterval: s->log_interval = (uint8_t)clamp_i((int)s->log_interval + dir, 1, 60); break;
    default: break;
    }
}

// ============================================================
// Main
// ============================================================

int32_t bme680_iaq_app(void* p) {
    UNUSED(p);

    Bme680App* app = malloc(sizeof(Bme680App));
    memset(app, 0, sizeof(Bme680App));
    app->event_queue = furi_message_queue_alloc(8, sizeof(InputEvent));
    app->iaq = -1.0f;
    app->iaq_level = 6;

    // Defaults
    app->s.i2c_addr = BME680_I2C_ADDR;
    app->s.temp_fahrenheit = false;
    app->s.read_interval = 3;
    app->s.heater_temp = 320;
    app->s.alarm_iaq_on = false;
    app->s.alarm_iaq_thresh = 150;
    app->s.alarm_temp_on = false;
    app->s.alarm_temp_low = 15;
    app->s.alarm_temp_high = 30;
    app->s.alarm_hum_on = false;
    app->s.alarm_hum_low = 20;
    app->s.alarm_hum_high = 70;
    app->s.alarm_led = AlarmLedRed;
    app->s.alarm_vibro = true;
    app->s.alarm_sound = false;
    app->s.log_enabled = false;
    app->s.log_interval = 1;

    app->notif = furi_record_open(RECORD_NOTIFICATION);

    // Timer - create BEFORE init attempt since try_init_sensor uses it
    app->timer = furi_timer_alloc(timer_cb, FuriTimerTypePeriodic, app);

    // GUI
    app->viewport = view_port_alloc();
    view_port_draw_callback_set(app->viewport, draw_cb, app);
    view_port_input_callback_set(app->viewport, input_cb, app);
    app->gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(app->gui, app->viewport, GuiLayerFullscreen);

    // Init sensor - try once, timer will keep retrying if not found
    FURI_LOG_I("BME680", "Starting...");
    try_init_sensor(app);

    if(!app->sensor_found) {
        furi_timer_start(app->timer, 2000); // Retry every 2 seconds
    }

    InputEvent event;
    bool running = true;
    while(running) {
        if(furi_message_queue_get(app->event_queue, &event, 100) != FuriStatusOk) continue;

        // Timer tick - either retry init or do reading
        if(event.key == InputKeyMAX) {
            if(!app->sensor_found) {
                try_init_sensor(app);
            } else {
                do_reading(app);
            }
            continue;
        }

        if(app->menu_open) {
            // ---- Menu mode ----
            if(event.type == InputTypePress || event.type == InputTypeRepeat) {
                switch(event.key) {
                case InputKeyBack:
                    app->menu_open = false;
                    break;
                case InputKeyUp:
                    menu_move(app, -1);
                    break;
                case InputKeyDown:
                    menu_move(app, 1);
                    break;
                case InputKeyLeft:
                    menu_change(app, -1);
                    break;
                case InputKeyRight:
                    menu_change(app, 1);
                    break;
                case InputKeyOk:
                    menu_change(app, 1); // Toggle booleans
                    break;
                default:
                    break;
                }
                view_port_update(app->viewport);
            }
        } else {
            // ---- Data page mode ----
            if(event.type == InputTypeLong && event.key == InputKeyOk) {
                app->menu_open = true;
                app->menu_sel = 0;
                view_port_update(app->viewport);
            } else if(event.type == InputTypeShort && event.key == InputKeyOk) {
                do_reading(app);
            } else if(event.type == InputTypePress || event.type == InputTypeRepeat) {
                switch(event.key) {
                case InputKeyBack:
                    running = false;
                    break;
                case InputKeyLeft:
                    app->page = (app->page > 0) ? app->page - 1 : DataPageCount - 1;
                    view_port_update(app->viewport);
                    break;
                case InputKeyRight:
                    app->page = (app->page + 1) % DataPageCount;
                    view_port_update(app->viewport);
                    break;
                case InputKeyUp:
                case InputKeyDown:
                    do_reading(app);
                    break;
                default:
                    break;
                }
            }
        }
    }

    // Cleanup
    notification_message(app->notif, &sequence_reset_rgb);
    furi_timer_stop(app->timer);
    furi_timer_free(app->timer);
    gui_remove_view_port(app->gui, app->viewport);
    view_port_free(app->viewport);
    furi_record_close(RECORD_GUI);
    furi_record_close(RECORD_NOTIFICATION);
    furi_message_queue_free(app->event_queue);
    free(app);
    return 0;
}
