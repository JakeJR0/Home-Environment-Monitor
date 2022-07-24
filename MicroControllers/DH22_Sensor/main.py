from app_req import post_sensor_results
from sensor_reader import read_dht
from time import sleep

def run():
    """
        This function is used to run the desired functionality
        of the micro-controller, this function reads the sensor
        attached and sends the data to the server.
        
        Additionally this function ensures that the micro-controller does not
        just turn off without trying a few times to connect to the server, this
        is used to ensure that the server is down and not just having connection
        issues.
    """
    
    
    max_attempts = 5
    attempts = 0
    
    while True:
        try:
            server_online = post_sensor_results()
            while server_online == True:
                server_online = post_sensor_results()
                sleep(1.5)
                attempts = 0
        except OSError:
            print("\nThe server seems to be presenting issues. Once this has been fixed, please restart the ESP8266")
        
        attempts += 1
        sleep(3)
        
        if attempts >= max_attempts:
            break
        
        
    
if __name__ == "__main__":
    run()