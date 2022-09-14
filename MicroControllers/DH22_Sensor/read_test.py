"""
    This file is used to test that the DHT22 sensor
    has been wired correctly to the Micro-Controller,
    additionally this can be used to ensure that it is 
    functioning as inteded.
"""

# Imports the required modules

import dht
from machine import Pin
from time import sleep

# Sets up the sensor for reading
dht22_sensor = dht.DHT22(Pin(12))

# Runs until the user terminates the script
while True:
    # Attempts to read the sensor
    try:
        # Measures the environment
        dht22_sensor.measure()
        # Gets the temperature
        temp = dht22_sensor.temperature()
        # Gets the humidity
        hum = dht22_sensor.humidity()
        # Prints out the recorded data
        print(temp, hum)
    except OSError:
        # Prints out an error for the user
        print("Failed to read DH22")
    # Informs the user that the program is about to sleep
    print("Sleeping")
    # Waits the cooldown
    sleep(2)
    # Informs the user the sleeping has concluded.
    print("Finished Sleeping")
