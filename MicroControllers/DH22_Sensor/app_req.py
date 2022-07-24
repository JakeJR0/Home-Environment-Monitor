import urequests as request
import ujson
from sensor_reader import read_dht
from time import sleep

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
    """
        This function is used to transfer data
        provided by the parameters to the assigned
        server ip address, this function converts the
        data into json which will be interpreted at
        the end point (server)
    """
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
    """
        This is used to make a 'GET' request from
        the server, this will return the data and will
        be used to decide how to proceed.
    """
    
    responce = request.get(f"{web_server}{route}")
    
    return responce

def server_available():
    """
        This allows the program to
        know if the server is available
        to get data from the micro-controller,
        this checks if the server is online and that
        within the current session that the sensors are
        meant to be online.
    """
    
    try:
        responce = get_from_server("/sensor_check").json()
        if responce["success"] == True:
            if responce["active"] == True:
                return True
        
        return False
    except OSError as e:
        print(f"Server Offline: \n{e}")
        return False

fail_safe_count = 0
success_count = 0
total_count = 0

def post_sensor_results():
    """
        This function formats the required
        data in a format that the server / end point
        will be able to interpret and it sends the formatted data
        to the server.
    """
    
    global fail_safe_count
    global success_count
    global total_count
    if fail_safe_count >= 5:
        return False
    
    available = server_available()
    
    # This stops the server from getting
    # 2 requests very quickly.
    
    sleep(0.5)
    
    if not available:
        return False
    
    
    temperature, humidity = read_dht(False)
    formatted_data = {
        "temperature": str(temperature),
        "humidity": str(humidity)
    }
    
    result = post_to_server(formatted_data, "/record")
    total_count += 1 
    
    if result["success"] == True:
        fail_safe_count = 0
        success_count += 1
        print(f"Successfully Transmitted Sensor Data. ({success_count}/{total_count})")
        return True
    else:
        print(f"Failed to upload Sensor Data to server ({success_count}/{total_count})")
        fail_safe_count += 1
        

