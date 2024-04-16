from machine import Pin, I2C
from utime import sleep

from bh1750 import BH1750

i2c0_sda = Pin(38)
i2c0_scl = Pin(39)
i2c0 = I2C(0, sda=i2c0_sda, scl=i2c0_scl)

bh1750 = BH1750(0x23, i2c0)

while True:
    print(bh1750.measurement)
    sleep(1)