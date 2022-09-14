import network
from time import sleep

wifi_ssid = ""
wifi_password = ""

def connect():
    """
        Used to ensure the micro-controller
        connects to the wifi.
    """
    wlan = network.WLAN(network.STA_IF)

    wlan.active(True)
    attempts = 3
    
    while True:
        if attempts <= 0:
            print("Failed to connect to wifi.")
            break
            
        if wlan.isconnected():
            print("Connected to wifi.")
            break
        else:
            wlan.connect(wifi_ssid, wifi_password)
            print("Attempting to connect to the Wifi")
        
        sleep(3)
        
        if wlan.isconnected():
            print("Connected to wifi.")
            break
        
        attempts -= 1
    

