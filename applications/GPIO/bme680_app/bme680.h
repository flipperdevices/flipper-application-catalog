#pragma once

#include <furi.h>
#include <furi_hal.h>
#include <stdbool.h>
#include <stdint.h>

// 7-bit I2C addresses (will be shifted left by 1 at call time)
#define BME680_I2C_ADDR       0x76
#define BME680_I2C_ADDR_ALT   0x77

#define BME680_REG_CHIP_ID    0xD0
#define BME680_REG_RESET      0xE0
#define BME680_REG_CTRL_HUM   0x72
#define BME680_REG_CTRL_MEAS  0x74
#define BME680_REG_CONFIG     0x75
#define BME680_REG_CTRL_GAS_1 0x71
#define BME680_REG_GAS_WAIT_0 0x64
#define BME680_REG_RES_HEAT_0 0x5A
#define BME680_REG_MEAS_STATUS 0x1D
#define BME680_REG_PRESS_MSB   0x1F
#define BME680_REG_GAS_R_MSB   0x2A
#define BME680_CHIP_ID        0x61

typedef struct {
    uint16_t par_t1;  int16_t par_t2;  int8_t par_t3;
    uint16_t par_p1;  int16_t par_p2;  int8_t par_p3;
    int16_t par_p4;   int16_t par_p5;  int8_t par_p6;
    int8_t par_p7;    int16_t par_p8;  int16_t par_p9; uint8_t par_p10;
    uint16_t par_h1;  uint16_t par_h2; int8_t par_h3;
    int8_t par_h4;    int8_t par_h5;   uint8_t par_h6; int8_t par_h7;
    int8_t par_gh1;   int16_t par_gh2; int8_t par_gh3;
    uint8_t res_heat_range; int8_t res_heat_val; int8_t range_sw_err;
    int32_t t_fine;
} Bme680Calib;

typedef struct {
    float temperature;
    float humidity;
    float pressure;
    float gas_resistance;
    bool  gas_valid;
    bool  heat_stable;
    // Raw ADC
    uint32_t raw_temp;
    uint32_t raw_pres;
    uint16_t raw_hum;
    uint16_t raw_gas;
    uint8_t  raw_gas_range;
} Bme680Data;

typedef struct {
    uint8_t     i2c_addr;  // 7-bit address (0x76 or 0x77)
    Bme680Calib calib;
    Bme680Data  data;
    bool        initialized;
} Bme680Device;

bool bme680_init(Bme680Device* dev, uint8_t i2c_addr_7bit);
bool bme680_read_forced(Bme680Device* dev, uint16_t heater_temp_c);
float bme680_calc_iaq(const Bme680Data* data);
