from app_req import post_sensor_results
from time import sleep
from machine import Pin

# Set Sensor Pin here.
sensor = Pin(12, Pin.IN)

def run():
    """
        This handles the main aspects of the
        device function.
        
        Features:
            Checks for changes in switch state,
            Uses Post function to send data to server.
    """
    
    while True:
        print("Awaiting Sensor Change")
        
        first = sensor.value()
        
        sleep(0.01)
        
        second = 1 #sensor.value()
        
        status = ""
        
        if first and not second:
            status = 1
        elif not first and second:
            status = 0
        
        if status != "":
            result = post_sensor_results(status)
            
            if not result:
                break
    
if __name__ == "__main__":
    run()
