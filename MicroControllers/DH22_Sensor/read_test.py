print("I just woke up")
import dht
print("I imported dht")
from machine import Pin
from time import sleep
print("I imported pin")
dht22_sensor = dht.DHT22(Pin(12))
print("I set up the pin")

while True:
    try:
        dht22_sensor.measure()
        print("I measured")
        temp = dht22_sensor.temperature()
        print("I got the temp")
        hum = dht22_sensor.humidity()
        print("I got the hum")
        print(temp, hum)
    except OSError:
        print("Failed to read DH22")
    print("About to sleep")
    sleep(2)
    print("Slept")