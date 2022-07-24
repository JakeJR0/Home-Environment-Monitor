import dht
from machine import Pin

# This creates the sensor object
# that reads the 12th Pin on the board
dht22_sensor = dht.DHT22(Pin(12))

def read_dht(format_data=True):
    """
        This function retrives a reading from
        the DHT-22 Sensor Connected and returns
        the data back to the caller of the function.
    """
    
    # This tells the sensor
    # to get a new measurement of the values.
    dht22_sensor.measure()
    
    # This assigns the variable to the temperature value of the sensor
    temp = dht22_sensor.temperature()
    
    # This assigns the variable to the humidity value of the sensor
    hum = dht22_sensor.humidity()


    # This checks if the data should be formatted
    if format_data:
        temp = f"{temp}°C"
        hum = f"{hum}%"
    
    # Returns the values to the caller.
    return temp, hum

