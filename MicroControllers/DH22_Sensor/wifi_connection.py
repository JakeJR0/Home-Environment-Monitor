import network

wlan = network.WLAN(network.STA_IF)

wlan.active(True)
if wlan.isconnected:
    print("Device already connected")
else:
    wlan.connect("SSID", "Password")

if wlan.isconnected:
    print("Connected to wifi.")
else:
    print("Failed to connect to wifi.")