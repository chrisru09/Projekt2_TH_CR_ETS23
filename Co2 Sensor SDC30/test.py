import time
from machine import Pin, SoftI2C
from scd30 import SCD30


i2c_sda = Pin(38)
i2c_scl = Pin(39)
I2C = SoftI2C(sda=i2c_sda, scl=i2c_scl)


scd30 = SCD30(I2C, 0x61)

while True:
    # Wait for sensor data to be ready to read (by default every 2 seconds)
    while scd30.get_status_ready() != 1:
        time.sleep_ms(200)
    messwerte = scd30.read_measurement()
    print(messwerte)