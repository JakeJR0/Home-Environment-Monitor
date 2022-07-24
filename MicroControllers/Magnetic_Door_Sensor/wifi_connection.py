import network

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def connect():
    if wlan.isconnected:
        print("Device already connected")
    else:
        wlan.connect("SSID", "Password")
    if not wlan.isconnected():
        print("Connecting to the network")
        wlan.connect("SSID", "Password")
        
        while not wlan.isconnected():
            pass
        
    print("Connected", wlan.ifconfig())
    