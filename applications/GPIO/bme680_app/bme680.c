#include "bme680.h"
#include <math.h>
#include <string.h>

// I2C read/write matching the working bme680 app pattern:
//   acquire -> tx_ext (register addr) -> rx_ext (data) -> release
// Address is 7-bit, shifted left by 1 at call time.

static bool bme680_i2c_read(uint8_t i2c_addr, uint8_t reg, uint8_t* data, size_t len) {
    uint8_t addr8 = i2c_addr << 1;

    furi_hal_i2c_acquire(&furi_hal_i2c_handle_external);

    // TX: send register address with restart (no stop)
    bool ok = furi_hal_i2c_tx_ext(
        &furi_hal_i2c_handle_external,
        addr8,
        false, // not 10-bit
        &reg,
        1,
        FuriHalI2cBeginStart,
        FuriHalI2cEndAwaitRestart,
        100);

    if(ok) {
        // RX: read data with restart begin, stop end
        ok = furi_hal_i2c_rx_ext(
            &furi_hal_i2c_handle_external,
            addr8,
            false,
            data,
            len,
            FuriHalI2cBeginRestart,
            FuriHalI2cEndStop,
            100);
    }

    furi_hal_i2c_release(&furi_hal_i2c_handle_external);
    return ok;
}

static bool bme680_i2c_write(uint8_t i2c_addr, uint8_t reg, const uint8_t* data, size_t len) {
    if(len > 30) return false;

    uint8_t addr8 = i2c_addr << 1;
    uint8_t buf[32];
    buf[0] = reg;
    memcpy(&buf[1], data, len);

    furi_hal_i2c_acquire(&furi_hal_i2c_handle_external);

    bool ok = furi_hal_i2c_tx_ext(
        &furi_hal_i2c_handle_external,
        addr8,
        false,
        buf,
        len + 1,
        FuriHalI2cBeginStart,
        FuriHalI2cEndStop,
        100);

    furi_hal_i2c_release(&furi_hal_i2c_handle_external);
    return ok;
}

// Convenience: write single register byte
static bool bme680_write_reg(uint8_t i2c_addr, uint8_t reg, uint8_t val) {
    return bme680_i2c_write(i2c_addr, reg, &val, 1);
}

// Convenience: read single register byte
static bool bme680_read_reg(uint8_t i2c_addr, uint8_t reg, uint8_t* val) {
    return bme680_i2c_read(i2c_addr, reg, val, 1);
}

// --- Calibration ---

static bool bme680_read_calib(Bme680Device* dev) {
    uint8_t coeff1[25], coeff2[16];
    uint8_t a = dev->i2c_addr;

    if(!bme680_i2c_read(a, 0x89, coeff1, 25)) return false;
    if(!bme680_i2c_read(a, 0xE1, coeff2, 16)) return false;

    Bme680Calib* c = &dev->calib;
    c->par_t1 = (uint16_t)(coeff2[9] << 8 | coeff2[8]);
    c->par_t2 = (int16_t)(coeff1[2] << 8 | coeff1[1]);
    c->par_t3 = (int8_t)coeff1[3];
    c->par_p1  = (uint16_t)(coeff1[6] << 8 | coeff1[5]);
    c->par_p2  = (int16_t)(coeff1[8] << 8 | coeff1[7]);
    c->par_p3  = (int8_t)coeff1[9];
    c->par_p4  = (int16_t)(coeff1[12] << 8 | coeff1[11]);
    c->par_p5  = (int16_t)(coeff1[14] << 8 | coeff1[13]);
    c->par_p6  = (int8_t)coeff1[16];
    c->par_p7  = (int8_t)coeff1[15];
    c->par_p8  = (int16_t)(coeff1[20] << 8 | coeff1[19]);
    c->par_p9  = (int16_t)(coeff1[22] << 8 | coeff1[21]);
    c->par_p10 = coeff1[23];
    c->par_h1 = (uint16_t)((coeff2[2] << 4) | (coeff2[1] & 0x0F));
    c->par_h2 = (uint16_t)((coeff2[0] << 4) | (coeff2[1] >> 4));
    c->par_h3 = (int8_t)coeff2[3];
    c->par_h4 = (int8_t)coeff2[4];
    c->par_h5 = (int8_t)coeff2[5];
    c->par_h6 = coeff2[6];
    c->par_h7 = (int8_t)coeff2[7];
    c->par_gh1 = (int8_t)coeff2[12];
    c->par_gh2 = (int16_t)(coeff2[11] << 8 | coeff2[10]);
    c->par_gh3 = (int8_t)coeff2[13];

    uint8_t tmp;
    if(!bme680_read_reg(a, 0x02, &tmp)) return false;
    c->res_heat_range = (tmp & 0x30) >> 4;
    if(!bme680_read_reg(a, 0x00, &tmp)) return false;
    c->res_heat_val = (int8_t)tmp;
    if(!bme680_read_reg(a, 0x04, &tmp)) return false;
    c->range_sw_err = ((int8_t)tmp) / 16;

    return true;
}

// --- Compensation ---

static float comp_temp(Bme680Device* dev, uint32_t adc) {
    Bme680Calib* c = &dev->calib;
    float v1 = (((float)adc / 16384.0f) - ((float)c->par_t1 / 1024.0f)) * (float)c->par_t2;
    float v2 = ((((float)adc / 131072.0f) - ((float)c->par_t1 / 8192.0f)) *
            (((float)adc / 131072.0f) - ((float)c->par_t1 / 8192.0f))) *
           ((float)c->par_t3 * 16.0f);
    c->t_fine = (int32_t)(v1 + v2);
    return (v1 + v2) / 5120.0f;
}

static float comp_pres(Bme680Device* dev, uint32_t adc) {
    Bme680Calib* c = &dev->calib;
    float v1 = ((float)c->t_fine / 2.0f) - 64000.0f;
    float v2 = v1 * v1 * ((float)c->par_p6 / 131072.0f);
    v2 = v2 + (v1 * (float)c->par_p5 * 2.0f);
    v2 = (v2 / 4.0f) + ((float)c->par_p4 * 65536.0f);
    v1 = ((((float)c->par_p3 * v1 * v1) / 16384.0f) + ((float)c->par_p2 * v1)) / 524288.0f;
    v1 = (1.0f + (v1 / 32768.0f)) * (float)c->par_p1;
    float p = 1048576.0f - (float)adc;
    if(v1 != 0.0f) {
        p = ((p - (v2 / 4096.0f)) * 6250.0f) / v1;
        v1 = ((float)c->par_p9 * p * p) / 2147483648.0f;
        v2 = p * ((float)c->par_p8 / 32768.0f);
        float v3 = (p / 256.0f) * (p / 256.0f) * (p / 256.0f) * ((float)c->par_p10 / 131072.0f);
        p = p + (v1 + v2 + v3 + ((float)c->par_p7 * 128.0f)) / 16.0f;
    } else { p = 0.0f; }
    return p / 100.0f;
}

static float comp_hum(Bme680Device* dev, uint16_t adc) {
    Bme680Calib* c = &dev->calib;
    float tc = (float)c->t_fine / 5120.0f;
    float v1 = (float)adc - (((float)c->par_h1 * 16.0f) + (((float)c->par_h3 / 2.0f) * tc));
    float v2 = v1 * (((float)c->par_h2 / 262144.0f) *
            (1.0f + (((float)c->par_h4 / 16384.0f) * tc) +
            (((float)c->par_h5 / 1048576.0f) * tc * tc)));
    float v3 = (float)c->par_h6 / 16384.0f;
    float v4 = (float)c->par_h7 / 2097152.0f;
    float h = v2 + ((v3 + (v4 * tc)) * v2 * v2);
    if(h > 100.0f) h = 100.0f;
    if(h < 0.0f) h = 0.0f;
    return h;
}

static float comp_gas(uint16_t adc, uint8_t range) {
    uint32_t v1 = (uint32_t)(262144 >> range);
    int32_t v2 = (int32_t)adc - 512 + (int32_t)v1;
    if(v2 > 0) return ((float)v1 * 49.0f * 6357.0f) / (float)v2;
    return 0.0f;
}

// --- Heater ---

static uint8_t calc_res_heat(Bme680Device* dev, uint16_t target) {
    Bme680Calib* c = &dev->calib;
    if(target > 400) target = 400;
    float amb = dev->data.temperature;
    if(amb == 0.0f) amb = 25.0f;
    float v1 = ((float)c->par_gh1 / 16.0f) + 49.0f;
    float v2 = (((float)c->par_gh2 / 32768.0f) * 0.0005f) + 0.00784f;
    float v3 = (float)c->par_gh3 / 1024.0f;
    float v4 = v1 * (1.0f + (v2 * (float)target));
    float v5 = v4 + (v3 * amb);
    return (uint8_t)(3.4f * ((v5 * (4.0f / (4.0f + (float)c->res_heat_range)) *
        (1.0f / (1.0f + ((float)c->res_heat_val * 0.002f)))) - 25));
}

static uint8_t calc_gas_wait(uint16_t ms) {
    uint8_t f = 0;
    if(ms >= 0xfc0) return 0xff;
    while(ms > 0x3f) { ms /= 4; f++; }
    return (uint8_t)(ms + (f * 64));
}

// --- Public ---

bool bme680_init(Bme680Device* dev, uint8_t i2c_addr_7bit) {
    dev->i2c_addr = i2c_addr_7bit;
    dev->initialized = false;
    memset(&dev->data, 0, sizeof(Bme680Data));

    // Quick check if device responds
    furi_hal_i2c_acquire(&furi_hal_i2c_handle_external);
    bool ready = furi_hal_i2c_is_device_ready(
        &furi_hal_i2c_handle_external, i2c_addr_7bit << 1, 100);
    furi_hal_i2c_release(&furi_hal_i2c_handle_external);

    if(!ready) {
        FURI_LOG_D("BME680", "No response at 0x%02X", i2c_addr_7bit);
        return false;
    }
    FURI_LOG_I("BME680", "Device found at 0x%02X", i2c_addr_7bit);

    // Soft reset first
    bme680_write_reg(i2c_addr_7bit, BME680_REG_RESET, 0xB6);
    furi_delay_ms(10);

    // Read chip ID after reset
    uint8_t chip_id = 0;
    if(!bme680_read_reg(i2c_addr_7bit, BME680_REG_CHIP_ID, &chip_id)) {
        FURI_LOG_E("BME680", "Chip ID read fail");
        return false;
    }
    FURI_LOG_I("BME680", "Chip ID: 0x%02X", chip_id);
    if(chip_id != BME680_CHIP_ID) return false;

    // Read variant/mem_page register
    uint8_t variant = 0;
    bme680_read_reg(i2c_addr_7bit, 0xF0, &variant);

    if(!bme680_read_calib(dev)) {
        FURI_LOG_E("BME680", "Calib fail");
        return false;
    }

    FURI_LOG_I("BME680", "Init OK");
    dev->initialized = true;
    return true;
}

bool bme680_read_forced(Bme680Device* dev, uint16_t heater_temp_c) {
    if(!dev->initialized) return false;
    uint8_t a = dev->i2c_addr;

    bme680_write_reg(a, BME680_REG_CTRL_HUM, 0x02);
    bme680_write_reg(a, BME680_REG_CONFIG, 0x02 << 2);
    bme680_write_reg(a, BME680_REG_RES_HEAT_0, calc_res_heat(dev, heater_temp_c));
    bme680_write_reg(a, BME680_REG_GAS_WAIT_0, calc_gas_wait(150));
    bme680_write_reg(a, BME680_REG_CTRL_GAS_1, 0x10);
    bme680_write_reg(a, BME680_REG_CTRL_MEAS, (0x04 << 5) | (0x03 << 2) | 0x01);

    furi_delay_ms(250);

    uint8_t status = 0;
    for(int i = 0; i < 10; i++) {
        if(!bme680_read_reg(a, BME680_REG_MEAS_STATUS, &status)) return false;
        if(status & 0x80) break;
        furi_delay_ms(50);
    }
    if(!(status & 0x80)) return false;

    uint8_t raw[8];
    if(!bme680_i2c_read(a, BME680_REG_PRESS_MSB, raw, 8)) return false;
    uint32_t ap = ((uint32_t)raw[0] << 12) | ((uint32_t)raw[1] << 4) | ((uint32_t)raw[2] >> 4);
    uint32_t at = ((uint32_t)raw[3] << 12) | ((uint32_t)raw[4] << 4) | ((uint32_t)raw[5] >> 4);
    uint16_t ah = ((uint16_t)raw[6] << 8) | (uint16_t)raw[7];

    uint8_t gr[2];
    if(!bme680_i2c_read(a, BME680_REG_GAS_R_MSB, gr, 2)) return false;
    uint16_t ag = ((uint16_t)gr[0] << 2) | (gr[1] >> 6);
    uint8_t  rng = gr[1] & 0x0F;

    dev->data.raw_temp = at;
    dev->data.raw_pres = ap;
    dev->data.raw_hum = ah;
    dev->data.raw_gas = ag;
    dev->data.raw_gas_range = rng;
    dev->data.temperature    = comp_temp(dev, at);
    dev->data.pressure       = comp_pres(dev, ap);
    dev->data.humidity       = comp_hum(dev, ah);
    dev->data.gas_resistance = comp_gas(ag, rng);
    dev->data.gas_valid      = (gr[1] & 0x20) != 0;
    dev->data.heat_stable    = (gr[1] & 0x10) != 0;
    return true;
}

float bme680_calc_iaq(const Bme680Data* data) {
    if(!data->gas_valid || !data->heat_stable) return -1.0f;
    float hs = (data->humidity >= 40.0f)
        ? (100.0f - data->humidity) / 60.0f
        : data->humidity / 40.0f;
    float hc = (1.0f - hs) * 125.0f;
    float gr = data->gas_resistance;
    if(gr < 1.0f) gr = 1.0f;
    float gl = log10f(gr);
    float gs = (gl <= 3.7f) ? 0.0f : (gl >= 5.7f) ? 1.0f : (gl - 3.7f) / 2.0f;
    float gc = (1.0f - gs) * 375.0f;
    float iaq = hc + gc;
    if(iaq < 0.0f) iaq = 0.0f;
    if(iaq > 500.0f) iaq = 500.0f;
    return iaq;
}
