import urequests as request
import ujson
from time import sleep

# This is the sensor ID

"""
    -[ Registered Sensors ]-
    
	(My current Layout)

    - 1: Door
    - 2: Window
    - 3: Bathroom
    
"""

# Set sensor ID according to server
sensor_id = 1 

local_mode = False

# Initialises the variable
web_server = ""

if local_mode:
    # Sets the the local IP of the usual workstation (Used for testing)
    web_server = "http://192.168.0.22:8080"
else:
    # Sets to the main server IP address
    web_server = "http://188.34.166.212:8080/"

def post_to_server(data=None, route="/"):
    data = ujson.dumps(data)
    headers = {
        "content-type": "application/json"
    }
    
    server = f"{web_server}{route}"
    result = request.post(server, headers=headers, json=data)
    try:
        converted = result.json()
        result = converted
    except ValueError:
        converted = result.text
        result = converted
    except TypeError:
        pass
    
    return result

def get_from_server(route="/"):
    url = f"{web_server}{route}"
    print(url)
    responce = request.get(url)
    print(responce)
    return responce

def server_available():
    try:
        responce = get_from_server("/sensor_check").json()
        if responce["success"] == True:
            if responce["active"] == True:
                return True
        
        return False
    except OSError as e:
        print("Server Offline with error: ", e)
        return False

fail_safe_count = 0
success_count = 0
total_count = 0

def post_sensor_results(status):
    global fail_safe_count
    global success_count
    global total_count
    global sensor_id
    
    if fail_safe_count >= 5:
        return False
    
    available = server_available()
    print("Available: ", available)
    # This stops the server from getting
    # 2 requests very quickly.
    
    sleep(0.5)
    
    if not available:
        return False
    
    formatted_data = {
        "sensor_id": str(sensor_id),
        "status": str(status)
    }
    
    result = post_to_server(formatted_data, "/report_security_change")
    total_count += 1 
    print(result)
    if result["success"] == True:
        fail_safe_count = 0
        success_count += 1
        print(f"Successfully Transmitted Sensor Data. ({success_count}/{total_count})")
        return True
    else:
        print(f"Failed to upload Sensor Data to server ({success_count}/{total_count})")
        fail_safe_count += 1
