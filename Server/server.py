"""
    File Name: server.py
    Author: Jake JR
    Github: JakeJR0
"""

import json, os
from flask import Flask, session, render_template, redirect, request
import storage, secrets
import requests as server_requests
from time import sleep
import pandas as pd
from threading import Thread
from matplotlib import pyplot as plt
from datetime import datetime
from flask_apscheduler import APScheduler

# Creates the flask instance
app = Flask(__name__)
# Creates the instance scheduler
app_schedule = APScheduler()

# Configures the scheduler
app_schedule.api_enabled = True
app_schedule.init_app(app)

# Sets up the Database

db = storage.Database()

# Creates some global variables
# that are used within the site
# These are set with defaults.

sensors_active = True
environment_modification = True

# Initiates the wanted temperature
bedroom_fan_minimum_temperature = 28

# Sets as false as when the server starts
# the system will turn it off using
# IFFT webhook.

fan_state = False

# Creates a hashed random 1024 character secret
# key which changes every time the server reboots.

app.secret_key = storage.security.hash_password(secrets.token_hex(16))

class MenusByPermissions:
    """
        This class is used to store the available
        navigation options depending on the users 
        permission level.

        Menu by Levels:

            Guest Menu: The user has not logged in.
            Authorised Menu: The user has logged in and has a permission level of 4 or less.
            Super User Menu: The user has logged in and has a permission level of 5 or higher.
    """

    guest_menu = {
        "Graphs": "graphs",
        "Login": "login"
    }

    authorised_menu = {
        "Account Settings": "account_settings",
        "Graphs": "graphs",
        "Logout": "logout"    
    }
    
    super_user_menu = {
        "Graphs": "graphs",
        "Sensor Management": "sensor_management",
        "Security Management": "security_manager",
        "User Management": "user_management",
        "Account Settings": "account_settings",
        "Logout": "logout"    
    }


# This sets the ifft webhook key.
ifft_key = "R9gQkI_I1PPMu-LSox_OQ"

def reset_sensors():
    """
        This is used to reset the sensors using an IFFT
        webhook, please note the webhook will need to be configured
        on IFFT for this to function as intended.

        This will primarly be used to reboot the micro-controller when
        it does not respond within 30 second, this could be due to an error
        on the micro-controller side but it ensures that it continues to collect
        data for the server.

        Note:
            The setup, I am currently using is with a Tapo smart plug which powers the
            micro-controller.
    """

    global ifft_key
    global sensors_active
    
    if sensors_active == False:
        print("Sensors are currently turned off.")
        return
    
    # Builds the url to ping.
    base_url = "https://maker.ifttt.com/trigger/reset_sensors"
    token = f"/json/with/key/{ifft_key}"
    url_to_use = f"{base_url}{token}"
    
    try:
        # Attempts to send a GET request to the server.
        server_requests.get(url_to_use)
    except TimeoutError:
        pass

def home_fan_control(state=False):
    """
        This is used to change the state of the fan using an IFFT
        webhook, please note the webhook will need to be configured
        on IFFT for this to function as intended.

        This will primarly be used to help cool the environment if the
        temperature is above the requested temperature.

        Note:
            The setup, I am currently using is with a Tapo smart plug which powers the
            micro-controller.
    """
    global ifft_key
    global fan_state
    
    # Checks if the user has turned off
    # modification.
    
    if not environment_modification:
        print("Environment modification is turned off currently.")
        return

    # This is building the webhook
    # url with the needed parameters
    base_url = "https://maker.ifttt.com/trigger/bedroom_fan_"
    token = f"/json/with/key/{ifft_key}"
    url_to_use = ""

    if state == True:
        url_to_use = f"{base_url}on{token}"
        
        # Sets the fan state
        fan_state = True
        
        print("Turning on bedroom fan to correct room temperature.")
    elif state == False:
        print("Turning off bedroom fan.")
        url_to_use = f"{base_url}off{token}"
        # Sets the fan state
        fan_state = False
    if url_to_use != "":
        try:
            # Sends the get request to the
            # url.
            server_requests.get(url_to_use)
        except TimeoutError:
            pass

fan_over_minimum_count = 0
fan_under_minimum_count = 0
# Duration between occurences
# in seconds
sensor_readings = 2 
    
# Time with consistant readings 
# needed before the system can act.
minimum_time = 15
    
# Required number of readings
readings_required = minimum_time / sensor_readings

# This is used to create a heart beat
# check with the micro-controller

environment_sensor_interaction = None

def add_environment_record(temperature=0.0, humidity=0.0):
    """
        The micro-controller uses this to record the temperature and humidity
        of the environment.
    """
    
    global fan_over_minimum_count
    global fan_under_minimum_count
    global fan_state
    global readings_required

    # Initializes the variables
    valid_temp = True
    valid_humidity = True
    
    # Checks if the temperature
    # is within the range of the
    # sensor used for the project (DHT22)
    
    if 80 > temperature < -40:
        valid_temp = False
        
    # Checks if the humidity
    # is within the range of the
    # sensor used for the project (DHT22)
    
    if 100 > humidity < 0:
        valid_humidity = False
    
    # This ensures that the reading 
    # is consistent before the system
    # preforms an action.
     
    if fan_over_minimum_count > readings_required: 
        # Checks if the fan is in the wrong 
        # state for the situation
        if fan_state == False:
            # Turns on the home fan
            home_fan_control(True)
    elif fan_under_minimum_count > readings_required:
        # Checks if the fan is in the wrong 
        # state for the situation
        if fan_state == True:
            # Turns off the home fan
            home_fan_control(False)

    
    # Records the amount of times that
    # a reading is over or under 
    # the wanted temperature.
    
    if temperature >= bedroom_fan_minimum_temperature:
        # Adds one to the count
        fan_over_minimum_count += 1
        # Resets the count
        fan_under_minimum_count = 0
    else:
        # Resets the count
        fan_over_minimum_count = 0
        # Adds one to the count
        fan_under_minimum_count += 1

    # Checks if the temperature and humidity is valid
        
    if valid_temp and valid_humidity:
        # Gets the database connection
        
        con = db.con
        
        # Creates the cursor
        cursor = con.cursor()
        
        # Inserts the temperature and humidity into the database
        cursor.execute('''
            INSERT INTO environment_record(
                temperature,
                humidity
            )
            VALUES(?, ?)
        ''', (temperature, humidity))

        # Commits the changes to the database
        con.commit()
        
        return True
    return False

def get_menu():
    """
        This is used to get the correct menu for the user depending
        on the users permission level.
    """

    set_defaults()
    try:
        # Checks if the user is logged in
        
        if session["authorised"] == True:
            # Checks the user's level
            if session["level"] >= 5:
                return MenusByPermissions.super_user_menu
            else:
                return MenusByPermissions.authorised_menu
        else:
            return MenusByPermissions.guest_menu
    except KeyError:
        return MenusByPermissions.guest_menu

def set_defaults():
    """
        This is used to set the default values for the session.
    """
    try:
        # Checks if the app title exists within
        # the session
        if session["app_title"]:
            return
        
    except KeyError:
        # Adds the app data to the session.
        
        session["authorised"] = None
        session["first_name"] = None
        session["last_name"] = None
        session["level"] = 0
        session["view_data"] = False
        session["app_title"] = "Home Environment Monitor"
        session["app_icon"] = "static/app_icon.svg"
        session["app_logo"] = "static/app_logo_black.svg"
        session["mode"] = "light"
        session["url"] = request.host_url
        session["id"] = None

@app.route("/", methods=["GET", "POST"])
def default():
    """
        This is the default page for the application.
    """
    
    set_defaults()

    if request.method == "POST":
        json_data = request.json
        
        try:
            if json_data["data_view"] == True:
                session["view_data"] = json_data["data_view"]
                return json.dumps({
                        "success": True
                    })
        except:
            return json.dumps({
                "success": False
                })

    if session["view_data"] == True:
        authorised = session["authorised"]
        if authorised is None:
            authorised = False

        return json.dumps({
                "authorised": authorised
            })

    # Creates the cursor
    
    cursor = db.con.cursor()

    # Gets the needed security data for the page.
    
    security_sensor_info = cursor.execute('''
        SELECT
            ID,
            nickname
        FROM
            security_sensors
    ''')

    
    
    return render_template("index.html", menu=get_menu(), desired_temperature=bedroom_fan_minimum_temperature, security_sensor=security_sensor_info)

@app.route("/toggle_page_mode")
def toggle_page_mode():
    """
        This is used to toggle the page between light mode
        and dark mode. 
        
        This is then stored within the session so the user's choice
        will be remembered.
    """

    try:
        mode = session["mode"]
        
        if mode.lower() == "dark":
            session["mode"] = "light"
        elif mode.lower() == "light":
            session["mode"] = "dark"
        else:
            set_defaults()
            return json.dumps({"success": False})

        return json.dumps({
                "success": True,
                "mode": session["mode"]
            })
    except KeyError as key_error:
        return json.dumps({
                "success": False,
                "message": key_error,
                "error_type": "Key Error"
            })
    except Exception as e:
        return json.dumps({
                "success": False,
                "error_message": e
            })
    
@app.route("/change_account", methods=["GET", "POST"])
def change_account():
    """
        This is used to change information 
        about an account.
    """

    set_defaults()
    
    try:
        if session["authorised"] is None:
            return json.dumps({
                "success": False,
                "message": "Account not authorised."
            })
    except KeyError:
        pass

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        user_id = request.form.get("user_id")

        requires_auth = True

        if user_id == "current_account":
            user_id = session["id"]
            requires_auth = False

        cur = db.con.cursor()
        result = cur.execute('''
            SELECT
                first_name,
                last_name,
                permission_level
            FROM
                managers
            WHERE
                ID = ?
        ''', (str(user_id)))

        authorised = False

        for row in result:
            if requires_auth:
                if session["level"] >= row[2]:
                    authorised = True
                else:
                    return json.dumps({
                            "success": False,
                            "message": "Not Authorised to change the account."
                        })
            else:
                authorised = True

            if row[0] == first_name and row[1] == last_name and str(user_id) == str(session["id"]):
                return json.dumps({
                    "success": False,
                    "message": "No change will happen."
                })
            
            else:
                if str(user_id) == str(session["id"]):
                    cur.execute('''
                        UPDATE 
                            managers
                        SET 
                            first_name = ?, 
                            last_name = ?
                        WHERE 
                            ID = ?
                    ''', (str(first_name), str(last_name), str(user_id)))
                
                    db.save()

                    session["first_name"] = first_name
                    session["last_name"] = last_name

                    return json.dumps({
                            "success": True
                        })
                else:
                    level = request.form.get("level")

                    try:
                        int(level)
                    except:
                        return json.dumps({
                                "success": False,
                                "message": "Please send a valid level"
                            })

                    changes = False
                    if str(level) != str(row[2]):
                        changes = True

                    if str(first_name) != str(row[0]):
                        changes = True

                    if str(last_name) != str(row[1]):
                        changes = True

                    if changes == False:
                        return json.dumps({
                                "success": False,
                                "message": "No change will happen."
                            })

                    if int(level) >= session["level"]:
                        return json.dumps({
                                "success": False,
                                "message": "You are not authorised to set the user's level to either the same or higher than your own."
                            })
                    
                    cur.execute('''
                        UPDATE
                            managers
                        SET
                            first_name = ?,
                            last_name = ?,
                            permission_level = ?
                        WHERE
                            ID = ?
                    ''', (str(first_name), str(last_name), str(level), str(user_id)))

                    db.save()

                    return json.dumps({
                            "success": True
                        })


    return json.dumps({
        "success": False    
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    """
        This is used to log in to the application.
    """
    warn_user = False
    warning_message = ""
    
    set_defaults()

    try:
        if session["authorised"] is not None:
            return redirect("/")
    except KeyError:
        pass

    if request.method == "POST":

        keycard = None
       
        if session["view_data"] == True:
            json_data = request.json
            keycard = json_data["keycard"]
        else:
            keycard = request.form.get("keycard")
            

        if keycard is None or keycard == "":
            warn_user = True
            warning_message = "Please use a valid id card."

        login_accepted, account_details = db.valid_login(str(keycard))
        if not login_accepted:
            warn_user = True
            warning_message = "The id card presented was not valid, please try again."
        else:
            session["authorised"] = True
            session["first_name"] = account_details[0]
            session["last_name"] = account_details[1]
            session["level"] = account_details[2]
            session["id"] = account_details[3]
            
            
        if not warn_user:
            if session["view_data"] == True:
                return json.dumps({
                    "success": True
                    })
            return redirect("/")
    
    return render_template("login.html", display_warning=warn_user, warning_message=warning_message, menu=get_menu())

@app.route("/sensor_management", methods=["GET", "POST"])
def sensor_management():
    """
        This is used to manage sensors.
    """
    global bedroom_fan_minimum_temperature
    global fan_over_minimum_count
    global fan_under_minimum_count

    set_defaults()
    if session["authorised"] is None:
        return redirect("/login")
    if session["level"] < 5:
        return redirect("/")
    
    if request.method == "POST":
        requested_temp = request.form.get("temperature");

        if requested_temp is not None:
            try:
                requested_temp = float(requested_temp)
            except:
                return json.dumps({"success": False})
            
            bedroom_fan_minimum_temperature = requested_temp
            cursor = db.con.cursor()

            result = cursor.execute('''
                SELECT
                    round(AVG(temperature), 2) AS average_temperature_rounded
                FROM
                    environment_record
                ORDER BY
                    ID DESC
                LIMIT 5
            ''')
            
            fan_over_minimum_count = 0
            fan_under_minimum_count = 0

            for i in result:
                if i[0] >= bedroom_fan_minimum_temperature:
                    if fan_state == False:
                        home_fan_control(True)
                    else:
                        print("Fan already in correct state, to deal with the new temperature requirements.")
                else:
                    if fan_state == True:
                        home_fan_control(False)
                    else:
                        print("Fan already in correct state, to deal with the new temperature requirements.")


    return render_template("sensor_management.html", menu=get_menu(), sensor_state=sensors_active, temperature=bedroom_fan_minimum_temperature, environment_state=environment_modification)
    

@app.route("/user_management")
def admin():
    """
        This is the page that allows the admin to manage users.
    """
    try:
        if session["level"] < 5:
            if session["authorised"] == None:
                return redirect("/login")
            else:
                return redirect("/")
    except KeyError:
        set_defaults()
        return redirect("/login")
    manager_id = session["id"]
    
    users = db.con.execute('''
        SELECT 
            ID, first_name, last_name, permission_level,
            (
                SELECT COUNT(*) AS keycards FROM keycards WHERE keycards.account_id = managers.ID 
            )
        FROM
            managers
        WHERE
            ID != ? AND permission_level < ?
    ''', (str(manager_id), str(session["level"])))
    
    return render_template("admin.html", menu=get_menu(), user_details = users)

@app.route("/modify_user")
def change():
    """
        This function is used to change the user's details.
    """
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    account_id = request.args.get("account_id")
    
    if account_id is None:
        return render_template("access_denied.html", menu=get_menu())
    
    for i in db.con.execute("SELECT permission_level FROM managers WHERE ID=?", account_id):
        if session["level"] < i[0]:
            return render_template("access_denied.html", menu=get_menu())
    
    user_details = None 
    
    for i in db.con.execute("SELECT ID, first_name, last_name, permission_level FROM managers WHERE ID=?", account_id):
        user_details = i
        
    if user_details is None:
        return render_template("access_denied.html", menu=get_menu())

    return render_template("modify_user.html", menu=get_menu(), user_details = user_details)

@app.route("/record", methods=["GET", "POST"])
def temperature():
    """
        This function is used to record the temperature of the room.
    """
    global environment_sensor_interaction
    
    if request.method == "POST":
        
        json_data = request.get_json()
        json_data = json.loads(json_data)
        temperature = float(json_data["temperature"])
        humidity = float(json_data["humidity"])
        
        result = add_environment_record(temperature, humidity)
        environment_sensor_interaction = True
        if result == True:
            return json.dumps({
                "success": True
            })
        else:
            return json.dumps({
                "success": False
            })
        
    return redirect("/")

@app.route("/sensor_check")
def sensor():
    """
        This function is used to check the state of the environment sensors.
    """
    return json.dumps(
        {
            "success": True,
            "active": sensors_active
        }
    )

@app.route("/report_security_change", methods=["GET", "POST"])
def security_report():
    """
        This function is used to report a security change to the system.
    """

    if request.method == "POST":
        json_data = request.get_json()
        json_data = json.loads(json_data)
        # - status -
        # true: Open
        # false: Closed

        status = str(json_data["status"])
        sensor_id = int(json_data["sensor_id"])

        cur = db.con.cursor()
        valid_sensor = cur.execute('''
            SELECT
                ID
            FROM
                security_sensors
            WHERE
                ID=?
        ''', (str(sensor_id)))
        
        valid = False
        status = status.lower()

        for i in valid_sensor:
            valid = True

        if status != "1" and status != "0":
            valid = False

        if valid:
            cur.execute('''
                INSERT INTO security_record(
                    status,
                    security_sensor
                ) 
                
                VALUES(
                    ?,
                    ?
                )
            ''', (status, str(sensor_id)))

            return json.dumps({
                "success": True
            })
        
    try:
        state = request.args.get("state")
        sensor_id = request.args.get("sensor_id")
        
        if state is None or sensor_id is None:
            return json.dumps({
                "success": False
            })
        
        cur = db.con.cursor()
        
        valid_sensor = cur.execute('''
            SELECT
                ID
            FROM
                security_sensors
            WHERE
                ID=?
        ''', (str(sensor_id)))
        
        valid = False

        for i in valid_sensor:
            valid = True

        if valid == False:
            return json.dumps({
                "success": False
            })

        if state == "1" or state == "0":
            cur.execute('''
                INSERT INTO security_record(
                    status,
                    security_sensor
                )
                VALUES(?, ?)
            ''', (state, sensor_id))
            
            db.save()
            
            return json.dumps({
                "success": True
            })
        
    except Exception as e:
        print(e)

    return json.dumps({
        "success": False    
    })
    

@app.route("/toggle_sensor")
def toggle_sensor():
    """
        Toggle the state of the sensors.
    """
    global sensors_active
    set_defaults()

    if sensors_active == True:
        sensors_active = False
    elif sensors_active == False:
        sensors_active = True

    return json.dumps({
            "success": True,
            "value": sensors_active
        })

@app.route("/set_sensor", methods=["GET", "POST"]) # SET UP
def set_sensor_state():
    """
        Sets the state of the sensor.
    """
    global sensors_active
    set_defaults()
    if request.method == "POST":
        json_data = request.get_json()
        json_data = json.loads(json_data)
        state = bool(json_data["state"])
    
        sensors_active = state
        return json.dumps({
                "success": True,
                "value": sensors_active
            })

    return json.dumps({
            "success": False
        })

@app.route("/server_information")
def server_info():
    """
        Returns the server information
    """
    global sensors_active
    global environment_modification
    global bedroom_fan_minimum_temperature
    
    set_defaults()

    data = {
            "success": True,
            "sensor_state": sensors_active,
            "modification_state": environment_modification
        }
    
    data = json.dumps(data)
    
    return data

@app.route("/set_environment_modification", methods=["GET", "POST"])
def set_environment_state():
    """
        Sets the state of the environment modification system.
    """
    global environment_modification
    set_defaults()

    if request.method == "POST":
        json_data = request.get_json()
        json_data = json.loads(json_data)
        state = bool(json_data["state"])
        if state == False:
            if fan_state == True:
                home_fan_control(False)
        
            environment_modification = False

        elif state == True:
            environment_modification = True

            cursor = db.con.cursor()
            result = cursor.execute('''
                SELECT
                    round(AVG(temperature), 2) AS average_temperature_rounded
                FROM
                    environment_record
                ORDER BY
                    ID DESC
                LIMIT 5
            ''')

            for i in result:
                if i[0] > bedroom_fan_minimum_temperature:
                    home_fan_control(True)
                else:
                    home_fan_control(False)
        

        return json.dumps({
                "success": True,
                "value": environment_modification
            })
    return json.dumps({
        "success": False
        })

@app.route("/toggle_environment_modification")
def toggle_environment():
    """ 
        Toggle the environment modification state.
    """
    global environment_modification
    set_defaults()

    if environment_modification == True:
        if fan_state == True:
            home_fan_control(False)
        
        environment_modification = False

    elif environment_modification == False:
        environment_modification = True

        cursor = db.con.cursor()
        result = cursor.execute('''
            SELECT
                round(AVG(temperature), 2) AS average_temperature_rounded
            FROM
                environment_record
            ORDER BY
                ID DESC
            LIMIT 5
        ''')

        for i in result:
            if i[0] > bedroom_fan_minimum_temperature:
                home_fan_control(True)
            else:
                home_fan_control(False)
        

    return json.dumps({
            "success": True,
            "value": environment_modification
        })

@app.route("/recent_security_information")
def recent_security_sensor():
    """
        Returns the last security records.
    """
    cursor = db.con.cursor()

    sensor_data = cursor.execute('''
        SELECT
            security_sensors.ID,
            security_sensors.nickname,
            CASE 
                WHEN security_record.status = 0 THEN
                    'Open'
                WHEN security_record.status = 1 THEN
                    'Closed'
                ELSE
                    'Unknown'
            END AS sensor_status,
            security_record.ID
       FROM
            security_record
       INNER JOIN
            security_sensors
                ON
            security_record.security_sensor = security_sensors.ID
       ORDER BY
            security_record.ID ASC
    ''')
    

    registered_sensors = {}

    for i in sensor_data:
        if i[0] not in registered_sensors:
            registered_sensors[str(i[0])] = {
                "nickname": str(i[1]),
                "status": str(i[2])
            }
        
    result = {
        "success": True,
        "value": registered_sensors
    }
    
    return json.dumps(result)


@app.route("/recent_sensor_information")
def recent_sensor():
    """
        Returns the last temperature and humidity readings from the environment_record table.
    """
    
    cursor = db.con.cursor()

    result = cursor.execute('''
        SELECT 
            temperature,
            humidity
        FROM 
            environment_record
        WHERE
            ID = (
                SELECT
                    MAX(ID)
                FROM
                    environment_record
            )
    ''')
    
    for i in result:
        return json.dumps({
            "success": True,
            "temperature": i[0],
            "humidity": i[1]
        })    
    
@app.route("/account_settings")
def account_settings():
    """
        Returns the account settings page for the user.
    """
    set_defaults()
    try:
        if session["authorised"] != True:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    cursor = db.con.cursor()
    required_data = cursor.execute('''
        SELECT
            ID,
            (
                SELECT 
                    COUNT(*) AS keycards 
                FROM 
                    keycards 
                WHERE 
                    keycards.account_id = managers.ID 
            )
        FROM
            managers
        WHERE
            ID=?
    ''', (str(session["id"])))
    
    data = []

    for i in required_data:
        data.append(i[0])
        data.append(i[1])

    return render_template("account_settings.html", menu=get_menu(), user_details=data)

@app.route("/active_keycard", methods=["GET", "POST"])
def is_active_keycard():
    """
        Checks if the keycard is active / in-use
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    cursor = db.con.cursor()
        
    keycard = request.args.get("keycard");
    if keycard is None:
        return json.dumps({
            "success": False
        })

    cards = cursor.execute('''
        SELECT
            ID
        FROM
            keycards
        WHERE
            account_id=?
    ''', (str(session["id"]),))

    valid = False

    for i in cards:
        if storage.check_password_hash(i[0], keycard):
            valid = True

    return json.dumps({
        "success": True,
        "value": valid
    })


@app.route("/delete_keycards", methods=["GET", "POST"])
def delete_all_keycards():
    """
        Delete all keycards for the current user
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

    if request.method == "POST":
        cursor = db.con.cursor()
    
        cursor.execute('''
            DELETE
        
            FROM
                keycards
            WHERE
                account_id = ?
        ''', str(session["id"]))
    
        db.save()
    
        return json.dumps({
            "success": True
        })
    return json.dumps({
        "success": False
    })

@app.route("/add_keycard", methods=["GET", "POST"])
def add_keycard():
    """
        Add a keycard to the database
    """

    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    if request.method == "POST":
        cursor = db.con.cursor()
        
        keycard = request.args.get("new_keycard");
        if keycard is None:
            return json.dumps({
                "success": False
            })
        
        if len(str(keycard)) == 10:
            existing_card = cursor.execute('''
                SELECT 
                    ID
                FROM
                    keycards
            ''')

            for i in existing_card:
                if storage.check_password_hash(i[0], keycard):
                    return json.dumps({
                            "success": False
                        })
                
            keycard = storage.security.hash_password(keycard)
            cursor.execute('''
                INSERT INTO keycards (ID, account_id)
                VALUES (?, ?)
            ''', (keycard, str(session["id"])))
            
            db.save()
    
            return json.dumps({
                "success": True
            })

    return json.dumps({
        "success": False
    })

@app.route("/keycard_count")
def keycard_count():
    """
        Returns the number of keycards associated with the current account.
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

    cur = db.con.cursor()
    row = cur.execute('''
        SELECT
            COUNT(ID) AS keycard_count
        FROM
            keycards
        WHERE
            account_id = ?
    ''', (str(session["id"]),))
    
    for i in row:
        return json.dumps({
            "success": True,
            "value": i[0]
        })
    
    return json.dumps({
        "success": False
    })

@app.route("/delete_keycard", methods=["GET", "POST"])
def delete_keycard():
    """
        Delete a keycard from the database.
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    if request.method == "POST":
        cursor = db.con.cursor()
        
        keycard = request.args.get("keycard");
        if keycard is None:
            return json.dumps({
                "success": False
            })
                
        rows = cursor.execute('''
            SELECT
                ID
            FROM
                keycards
            WHERE
                account_id = ?
        ''', (session["id"],))
        
        for i in rows:
            if storage.check_password_hash(i[0], keycard):
                cursor.execute('''
                    DELETE
                    
                    FROM
                        keycards
                    WHERE
                        ID = ?
                ''', (i[0],))
                
                db.save()
                
                return json.dumps({
                    "success": True
                })

    return json.dumps({
        "success": False
    })

@app.route("/graphs")
def graph_page():
    """
        Graphs page, this page allows users to view the graphs.
    """
    return render_template("graphs.html", menu=get_menu())

def remove_export(file_name=""):
    """
        Removes the export file from the server.
    """

    if os.path.exists(file_name):
        sleep(30)
        os.remove(file_name)

@app.route("/get_downloadable_environment_data")
def download_csv():
    """
        Downloads the environment data as a csv file.
    """
    
    set_defaults()
    failed_data = json.dumps({
            "success": False
        })
    try:
        if session["authorised"] != True or session["level"] < 5:
            return failed_data
    except KeyError:
        return failed_data
    
    data_query = '''
        SELECT
            ID,
            temperature,
            humidity,
            strftime("%d/%m/%Y %H:%M:%S", occured_on) AS recorded_on
       FROM
            environment_record
    '''
    
    frame = pd.read_sql_query(data_query, db.con)
    file_name = "environment_data-" + datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    file_name += ".csv"
    frame.set_index("ID")
    file_name = f"static/data_exports/{file_name}"
    frame.to_csv(file_name, index=False)

    thr = Thread(target=remove_export, args=(file_name,))
    thr.daemon = True
    thr.start()

    return json.dumps({
            "success": True,
            "download": file_name
        })

@app.route("/get_downloadable_security_data")
def download_security_csv():
    """
        Downloads a CSV of all security data.
    """

    set_defaults()
    failed_data = json.dumps({
            "success": False
        })
    try:
        if session["authorised"] != True or session["level"] < 5:
            return failed_data
    except KeyError:
        return failed_data

    data_query = '''
       SELECT
            security_record.ID AS record_id,
            security_sensors.ID AS sensor_id,
            security_sensors.nickname AS sensor_name,
            CASE 
                WHEN security_record.status = 0 THEN
                    'Open'
                WHEN security_record.status = 1 THEN
                    'Closed'
                ELSE
                    'Unknown'
            END AS sensor_status,
            strftime('%d/%m/%Y %H:%M:%S', security_sensors.registered_on) AS sensor_created_on,
            strftime('%d/%m/%Y %H:%M:%S', security_record.occured_on) AS recorded_on
       FROM
            security_record
       INNER JOIN
            security_sensors
                ON
            security_record.security_sensor = security_sensors.ID
    '''

    frame = pd.read_sql_query(data_query, db.con)
    file_name = "security_data-" + datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    file_name += ".csv"
    frame.set_index("record_id")
    file_name = f"static/data_exports/{file_name}"
    frame.to_csv(file_name, index=False)

    thr = Thread(target=remove_export, args=(file_name,))
    thr.daemon = True
    thr.start()

    return json.dumps({
            "success": True,
            "download": file_name
        })

@app.route("/set_temperature", methods=["GET", "POST"])
def set_temperature():
    """
        Set the wanted temperature for the environment.
    """
    global bedroom_fan_minimum_temperature

    set_defaults()
    if request.method == "POST":
        json_data = request.get_json()
        json_data = json.loads(json_data)
        temperature = float(json_data["temperature"])
        
        if temperature > 80:
            return json.dumps({
                "success": False
            })
        elif temperature < -40:
            return json.dumps({
                "success": False
            })
        else:
            bedroom_fan_minimum_temperature = temperature
            return json.dumps({
                "success": True
            })
        
    return json.dumps({
                    "success": False
                })

@app.route("/security_manager")
def security_manager():
    """
        Security manager page, this allows the
        user to manage the security sensors.
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    cur = db.con.cursor()

    data = cur.execute('''
        SELECT
            ID,
            nickname,
            strftime("%d/%m/%Y", registered_on) AS registered_on
        FROM
            security_sensors
    ''')    

    return render_template("security_sensors.html", menu=get_menu(), security_sensor=data)

@app.route("/add_security_sensor")
def add_security_sensor():
    """
        Add a new security sensor to the system.
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

    nickname = request.args.get("name")
    
    if nickname == None or len(nickname) <= 2:
        return json.dumps({
                "success": False,
                "messsage": "Invalid nickname"
            })
        
    cur = db.con.cursor()
    cur.execute('''
        INSERT INTO security_sensors(nickname)
        VALUES (?)
    ''', (nickname,))
    db.con.commit()
    
    return json.dumps({
        "success": True
        })

@app.route("/remove_security_sensor")
def remove_security_sensor():
    """
        Remove a security sensor from the database
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

    sensor_id = request.args.get("sensor_id")

    if sensor_id == None:
        return json.dumps({
                "success": False,
                "message": "Invalid sensor id"
            })
    
    cur = db.con.cursor()
    
    cur.execute('''
        DELETE FROM security_sensors
        WHERE 
            ID = ?
    ''', (sensor_id,))
    
    cur.execute('''
        DELETE FROM security_record
        WHERE 
            security_sensor = ?
    ''', (sensor_id,))

    db.con.commit()
    
    return json.dumps({
        "success": True
        })

@app.route("/delete_user")
def delete_active_user():
    """
        Delete an active user from the database
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

    user_id = request.args.get("account_id")

    if user_id == None:
        return json.dumps({
                "success": False,
                "message": "Invalid user id"
            })
    
    
    cur = db.con.cursor()
    
    user_details = cur.execute('''
        SELECT
            ID,
            permission_level
        FROM
            managers
        WHERE
            ID = ?
    ''', (user_id,))
    
    for i in user_details:
        if i[1] == 10:
            return json.dumps({
                "success": False,
                "message": "Cannot delete super user"
            })
        elif i[1] > session["level"]:
            return json.dumps({
                "success": False,
                "message": "Insufficient permissions"
            })
    
    cur.execute('''
        DELETE 
        FROM 
            managers
        WHERE 
            ID = ?
    ''', (user_id,))
    
    db.save()
    
    return json.dumps({
        "success": True
        })

@app.route("/set_security_sensor_name")
def edit_security_sensor():
    """
        Edit the name of a security sensor
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    sensor_id = request.args.get("id")
    sensor_name = request.args.get("name")
    
    if sensor_id == None or sensor_name == None or len(sensor_name) <= 2:
        return json.dumps({
                "success": False,
                "message": "Invalid sensor id or name"
            })
    
    cur = db.con.cursor()
    cur.execute('''
        UPDATE 
            security_sensors
        SET 
            nickname = ?
        WHERE 
            ID = ?
    ''', (sensor_name, sensor_id))
    
    db.save()
    return json.dumps({
        "success": True
        })

@app.route("/add_user", methods=["GET", "POST"])
def add_new_user():
    """
        Add a new user to the system
    """
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())
    
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        level = request.form.get("level")
        keycard = request.form.get("keycard")
        
        if len(first_name) <= 2:
            return json.dumps({
                "success": False,
                "message": "Invalid first name"
            })
        
        if len(last_name) <= 5:
            return json.dumps({
                "success": False,
                "message": "Invalid last name"
            })
        
        if level == None or int(level) < 1 or int(level) > 10:
            return json.dumps({
                "success": False,
                "message": "Invalid level"
            })
        
        if keycard == None or len(keycard) != 10:
            return json.dumps({
                "success": False,
                "message": "Invalid keycard"
            })
        
        if int(level) >= session["level"]:
            return json.dumps({
                "success": False,
                "message": "Insufficient permissions"
            })

        cur = db.con.cursor()

        valid_keycard = True

        keycards = cur.execute('''
            SELECT
                ID
            FROM
                keycards
        ''')

        for i in keycards:
            if storage.check_password_hash(i[0], keycard):
                valid_keycard = False
                break

        if not valid_keycard:
            return json.dumps({
                "success": False,
                "message": "Keycard already in use"
            })
            
        keycard = storage.security.hash_password(keycard)
        
        cur.execute('''
            INSERT INTO managers(first_name, last_name, permission_level)
            VALUES (?, ?, ?)
        ''', (first_name, last_name, level))

        cur.execute('''
            INSERT INTO keycards(ID, account_id)
            VALUES (?, ?)
        ''', (keycard, cur.lastrowid))
        
        db.save()
        
        return json.dumps({
            "success": True
            })
        
    return json.dumps({
        "success": False
        })

@app.route("/logout")
def logout():
    """
        Logs the user out of the system
    """
    
    set_defaults()

    # Removes data from session
    session.pop("authorised", None)
    session.pop("level", 0)
    session.pop("first_name", None)
    session.pop("last_name", None)
    session.pop("id", None)

    if session["view_data"] == True:
        return json.dumps({"success": True})
    return redirect("/")

def get_record_count():
    """
        Gets the number of rows
        within the environment record
        table.
    """
    con = db.con

    cursor = con.cursor()
    stats = cursor.execute('''
        SELECT
            COUNT(ID) AS entry_count,
            round(AVG(temperature), 2) AS avg_temperature,
            round(AVG(humidity), 2) as avg_humidity
        FROM 
            environment_record

    ''')

    for i in stats:
        print(f"\nCurrently we have {i[0]} rows in the database.\nThe average the temperature and humidity is {i[1]}°C and {i[2]}%\n")

def average_stat_by_day():
    """
        Displays the average stats by day.
    """

    cursor = db.con.cursor()

    rows = cursor.execute('''
        SELECT
            round(AVG(temperature), 2),
            round(AVG(humidity), 2),
            strftime('%H', occured_on)
        FROM 
            environment_record
        GROUP BY
            strftime('%H', occured_on)
    ''')
    
    hum, temp = [], []
    hours = []

    for i in rows:
        temp.append(i[0])
        hum.append(i[1])
        hours.append(i[2])
        
    # Sets the graphs title
    plt.title("Average Conditions by hour")
    # Plots the temperature
    plt.plot(hours, temp, label="Temperature (°C)")
    # Plots the humidty
    plt.plot(hours, hum, label="Humidity (%)")
    # Adds the legend to the graph
    plt.legend()
    # Adds x-axis label
    plt.xlabel("Hours")
    # Adds y-axis label
    plt.ylabel("Environment Condition")
    # Rotates x-axis labels by 45 degrees
    plt.xticks(rotation=45)
    # Displays the graph
    plt.show()

def average_stat_by_day_humidity(show=True, export_file_name="hourly_hum"):
    cursor = db.con.cursor()
    date_today = datetime.strftime(datetime.now(), "%d/%m/%Y")

    rows = cursor.execute('''
        SELECT
            round(AVG(humidity), 2),
            round(MIN(humidity), 2),
            round(MAX(humidity), 2),
            strftime('%H', occured_on)
        FROM 
            environment_record
        WHERE
            strftime('%d/%m/%Y', occured_on) = strftime('%d/%m/%Y', CURRENT_TIMESTAMP)
        GROUP BY
            strftime('%H', occured_on)

    ''')
    
    humidity_avg = []
    humidity_min = []
    humidity_max = []
    hours = []

    for i in rows:
        humidity_avg.append(i[0])
        humidity_min.append(i[1])
        humidity_max.append(i[2])
        hours.append(i[3])
        
    # Sets the graph title
    plt.title(f"Humidity by hour within the environment")
    # Plots the average humidity
    plt.plot(hours, humidity_avg, label="Average Humidity (°C)")
    # Plots the minimum humidity
    plt.plot(hours, humidity_min, label="Minimum Humidity (°C)")
    # Plots the maximum humidity
    plt.plot(hours, humidity_max, label="Maximum Humidity (°C)")
    # Sets the legend
    plt.legend()
    # Sets the x-axis label
    plt.xlabel("Hours")
    # Sets the y-axis label
    plt.ylabel("Humidity (%)")
    # Rotates the x-axis labels
    plt.xticks(rotation=45)
    
    if show:
        plt.show()
    else:
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
        # Shows the graph
        plt.savefig(file_name)
        plt.close()

def average_stat_by_day_temperature(show=True, export_file_name="hourly_temp"):
    cursor = db.con.cursor()
    date_today = datetime.strftime(datetime.now(), "%d/%m/%Y")

    rows = cursor.execute('''
        SELECT
            round(AVG(temperature), 2),
            round(MIN(temperature), 2),
            round(MAX(temperature), 2),
            strftime('%H', occured_on)
        FROM 
            environment_record
        WHERE
            strftime('%d/%m/%Y', occured_on) = strftime('%d/%m/%Y', CURRENT_TIMESTAMP)
        GROUP BY
            strftime('%H', occured_on)

    ''')
    
    temp_avg = []
    temp_min = []
    temp_max = []
    hours = []

    for i in rows:
        temp_avg.append(i[0])
        temp_min.append(i[1])
        temp_max.append(i[2])
        hours.append(i[3])
        
    # Sets the graph title
    plt.title(f"Temperature by hour within the environment")
    # Plots the average temperature
    plt.plot(hours, temp_avg, label="Average Temperature (°C)")
    # Plots the minimum temperature
    plt.plot(hours, temp_min, label="Minimum Temperature (°C)")
    # Plots the maximum temperature
    plt.plot(hours, temp_max, label="Maximum Temperature (°C)")
    # Sets the legend
    plt.legend()
    # Sets the x-axis label
    plt.xlabel("Hours")
    # Sets the y-axis label
    plt.ylabel("Temperature (°C)")
    # Rotates the x-axis labels
    plt.xticks(rotation=45)
    # Shows the graph if show is True
    if show:
        plt.show()
    else:        
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
            
        # Saves the graph
        plt.savefig(file_name)
        plt.close()

def average_stat_by_week_temperature(show=True, export_file_name="monthly_temp"):
    """
        This will display a graph which
        shows the temperature change
        by each day.
    """
    
    cur = db.con.cursor()
    rows = cur.execute('''
        SELECT
            round(AVG(temperature), 2),
            round(MIN(temperature), 2),
            round(MAX(temperature), 2),
            strftime('%d', occured_on) as recorded_on
        FROM
            environment_record
        WHERE
            strftime('%m/%Y', occured_on) = strftime('%m/%Y', CURRENT_TIMESTAMP)
        GROUP BY
            strftime('%d', occured_on)
        LIMIT
            30
    ''')

    temp_ave = []
    temp_min = []
    temp_max = []
    days = []

    for row in rows:
        temp_ave.append(row[0])
        temp_min.append(row[1])
        temp_max.append(row[2])
        days.append(row[3])
        
    # Sets the graph title
    plt.title("Average Temperature in the environment by the day of the month")
    # Plots the average temperature
    plt.plot(days, temp_ave, label="Average Temperature (°C)", color="red")
    # Plots the minimum temperature
    plt.plot(days, temp_min, label="Minimum Temperature (°C)", color="blue")
    # Plots the maximum temperature
    plt.plot(days, temp_max, label="Maximum Temperature (°C)", color="green")
    # Adds the legend to the graph
    plt.legend()
    # Sets the x-axis label
    plt.xlabel("Days")
    # Sets the y-axis label
    plt.ylabel("Temperature (°C)")
    # Rotates the x-axis labels
    plt.xticks(rotation=45)
    
    if show == True:
        # Displays the graph
        plt.show()
    else:
        
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)

        # Saves the graph to the file
        plt.savefig(file_name)
        plt.close()


def average_stat_by_week_humidity(show=True, export_file_name="monthly_hum"):
    """
        This will display a graph which
        shows the humidity change
        by each day.
    """
    
    cur = db.con.cursor()
    
    rows = cur.execute('''
        SELECT
            round(AVG(humidity), 2),
            round(MIN(humidity), 2),
            round(MAX(humidity), 2),
            strftime('%d', occured_on) as recorded_on
        FROM
            environment_record
        WHERE
            strftime('%m/%Y', occured_on) = strftime('%m/%Y', CURRENT_TIMESTAMP)
        GROUP BY
            strftime('%d', occured_on)
        LIMIT
            30
    ''')

    humidity_ave = []
    humidity_min = []
    humidity_max = []
    days = []

    for row in rows:
        humidity_ave.append(row[0])
        humidity_min.append(row[1])
        humidity_max.append(row[2])
        days.append(row[3])
        
    # Sets the graph title
    plt.title("Average Humidity in the environment by the day of the month")
    # Plots the average humidity
    plt.plot(days, humidity_ave, label="Average Humidity (°C)", color="red")
    # Plots the minimum humidity
    plt.plot(days, humidity_min, label="Minimum Humidity (°C)", color="blue")
    # Plots the maximum humidity
    plt.plot(days, humidity_max, label="Maximum Humidity (°C)", color="green")
    # Adds the legend to the graph
    plt.legend()
    # Sets the XLabel of the graph
    plt.xlabel("Days")
    # Sets the YLabel of the graph
    plt.ylabel("Humidity (%)")
    
    # Rotates the days by 45 degrees
    plt.xticks(rotation=45)
    
    if show == True:
        # Displays the graph.
        plt.show()
    else:
        # Gets file name and location
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
            
        # Saves the graph.
        plt.savefig(file_name)
        plt.close()
    
@app_schedule.task("interval", id="Daily_Graph", hours=24)
def daily_graph():
    """
        This will update the daily graphs,
        this ensures that it is active.
    """

    average_stat_by_week_temperature(False)
    average_stat_by_week_humidity(False)
    print("Updated Daily Graphs")
    
@app_schedule.task("interval", id="Hourly_Graph", hours=1)
def hour_graph():
    """
        This will update the hourly graphs,
        this ensures that it is active.
    """

    average_stat_by_day_temperature(False)
    average_stat_by_day_humidity(False)
    print("Updated Hourly Graph")

@app_schedule.task("interval", id="Sensor Check", seconds=30)
def sensor_message_check():
    """
        This will check that the micro-controller
        has interacted with the server. 
    """
    
    global environment_sensor_interaction
    if environment_sensor_interaction:
        print("Sensor Interacted with server.")
        environment_sensor_interaction = False
    else:
        environment_sensor_interaction = False
        print("Sensor not interacted with server.")
        reset_sensors()
    

def generate_graphs():
    """
        This will generate all the graphs needed
        for the website.
    """
    
    daily_graph()
    hour_graph()

    print("\nUpdated Graphs\n\n")
    
def empty_directory(path=""):
    """
        This searches a path for any files and
        deletes them.
    """

    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

def setup_server():
    """
        This will setup the server, by ensuring that
        the server environment is correct.
    """
    
    if not os.path.exists("static/data_exports"):
        os.mkdir("static/data_exports")

    if not os.path.exists("static/graphs"):
        os.mkdir("static/graphs")
        
    empty_directory("static/data_exports")
    empty_directory("static/graphs")

    sensor_message_check()
    get_record_count()
    home_fan_control(False)
    generate_graphs()

def run_server():
    """
        This starts up the program,
        and runs the server.
    """

    # Starts the app scheduler
    app_schedule.start()
    # Starts the flask instance
    app.run(host="0.0.0.0", port=8080)

def clean_up_server():
    """
        This ensures that the system is turned
        before the program ends.
    """

    # Turns off the home fan
    home_fan_control(False)
    # Reports the amount of rows within
    # the environment data table.
    get_record_count()
    sleep(5)

if __name__ == "__main__":
    setup_server()
    run_server()
    clean_up_server()
