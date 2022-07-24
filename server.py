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

app = Flask(__name__)
app_schedule = APScheduler()

app_schedule.api_enabled = True
app_schedule.init_app(app)

db = storage.Database()
sensors_active = True
environment_modification = True
bedroom_fan_minimum_temperature = 28
fan_state = False
app.secret_key = storage.security.hash_password(secrets.token_hex(16))

class MenusByPermissions:
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
        "User Management": "user_management",
        "Account Settings": "account_settings",
        "Logout": "logout"    
    }

ifft_key = "R9gQkI_I1PPMu-LSox_OQ"

def reset_sensors():
    global ifft_key
    global sensors_active
    
    if sensors_active == False:
        print("Sensors are currently turned off.")
        return
    

    base_url = "https://maker.ifttt.com/trigger/reset_sensors"
    token = f"/json/with/key/{ifft_key}"
    url_to_use = f"{base_url}{token}"
    
    try:
        server_requests.get(url_to_use)
    except TimeoutError:
        pass

def home_fan_control(state=False):
    global ifft_key
    global fan_state
    if not environment_modification:
        print("Environment modification is turned off currently.")
        return

    base_url = "https://maker.ifttt.com/trigger/bedroom_fan_"
    token = f"/json/with/key/{ifft_key}"
    url_to_use = ""
    if state == True:
        url_to_use = f"{base_url}on{token}"
        fan_state = True
        print("Turning on bedroom fan to correct room temperature.")
    elif state == False:
        print("Turning off bedroom fan.")
        url_to_use = f"{base_url}off{token}"
        fan_state = False
    if url_to_use != "":
        try:
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

environment_sensor_interaction = None

def add_environment_record(temperature=0.0, humidity=0.0):
    global fan_over_minimum_count
    global fan_under_minimum_count
    global fan_state
    global readings_required

    valid_temp = True
    valid_humidity = True
    
    if 80 > temperature < -40:
        valid_temp = False
        
    if 100 > humidity < 0:
        valid_humidity = False
    
    if fan_over_minimum_count > readings_required: 
        if fan_state == False:
            home_fan_control(True)
    elif fan_under_minimum_count > readings_required:
        if fan_state == True:
            home_fan_control(False)


    if temperature >= bedroom_fan_minimum_temperature:
        fan_over_minimum_count += 1
        fan_under_minimum_count = 0
    else:
        fan_over_minimum_count = 0
        fan_under_minimum_count += 1

    if valid_temp and valid_humidity:
        con = db.con
        
        cursor = con.cursor()
        cursor.execute('''
            INSERT INTO environment_record(
                temperature,
                humidity
            )
            VALUES(?, ?)
        ''', (temperature, humidity))

        con.commit()
        return True
    return False

def get_menu():
    set_defaults()
    try:
        if session["authorised"] == True:
            if session["level"] >= 5:
                return MenusByPermissions.super_user_menu
            else:
                return MenusByPermissions.authorised_menu
        else:
            return MenusByPermissions.guest_menu
    except KeyError:
        return MenusByPermissions.guest_menu

def set_defaults():
    try:
        if session["app_title"]:
            return
        
    except KeyError:
        session["authorised"] = None
        session["first_name"] = None
        session["last_name"] = None
        session["level"] = 0
        session["view_data"] = False
        session["app_title"] = "Home Environment Monitor"
        session["url"] = request.host_url
        session["id"] = None

@app.route("/", methods=["GET", "POST"])
def default():
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

    cursor = db.con.cursor()

    security_sensor_info = cursor.execute('''
        SELECT
            ID,
            nickname
        FROM
            security_sensors
    ''')

    

    return render_template("index.html", menu=get_menu(), desired_temperature=bedroom_fan_minimum_temperature, security_sensor=security_sensor_info)

@app.route("/change_account", methods=["GET", "POST"])
def change_account():
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

        print(user_id)

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

                    if str(level) == str(row[2]):
                        print("This is the other")
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
    print(manager_id, type(manager_id))
    
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
    return json.dumps(
        {
            "success": True,
            "active": sensors_active
        }
    )

@app.route("/report_security_change", methods=["GET", "POST"])
def security_report():

    if request.method == "POST":
        json_data = request.get_json()
        json_data = json.loads(json_data)
        # - status -
        # true: Open
        # false: Closed

        status = str(json_data["status"])
        sensor_id = int(json_data["sensor_id"])

        print(json_data)
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

    return json.dumps({
        "success": False    
    })
    

@app.route("/toggle_sensor")
def toggle_sensor():
    global sensors_active
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

    if sensors_active == True:
        sensors_active = False
    elif sensors_active == False:
        sensors_active = True

    return json.dumps({
            "success": True,
            "value": sensors_active
        })


@app.route("/toggle_environment_modification")
def toggle_environment():
    global environment_modification
    set_defaults()
    try:
        if session["authorised"] != True or session["level"] < 5:
            return render_template("access_denied.html", menu=get_menu())
    except KeyError:
        return render_template("access_denied.html", menu=get_menu())

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
            END AS sensor_status
        FROM
            security_sensors,
            security_record
        ORDER BY 
            security_record.ID DESC
        LIMIT
            (
                SELECT
                    COUNT(DISTINCT ID)
                FROM
                    security_sensors
            )
    ''')

    result = {
        "success": True,
        "value": {}
    }

    for i in sensor_data:
        result["value"][str(i[0])] = {
            "nickname": str(i[1]),
            "state": str(i[2])
        }


    return json.dumps(result)

@app.route("/recent_sensor_information")
def recent_sensor():
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

    print(required_data)

    return render_template("account_settings.html", menu=get_menu(), user_details=data)

@app.route("/active_keycard", methods=["GET", "POST"])
def is_active_keycard():
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
        
        print(keycard)
        
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
        
        print(keycard)
        
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
    return render_template("graphs.html", menu=get_menu())

def remove_export(file_name=""):
    if os.path.exists(file_name):
        sleep(30)
        os.remove(file_name)

@app.route("/get_downloadable_sensor_data")
def download_csv():
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
    file_name = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
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
    


@app.route("/logout")
def logout():
    set_defaults()
    session.pop("authorised", None)
    session.pop("level", 0)
    session.pop("first_name", None)
    session.pop("last_name", None)
    session.pop("id", None)

    if session["view_data"] == True:
        return json.dumps({"success": True})
    return redirect("/")

def get_record_count():
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
        
    plt.title("Average Conditions by hour")
    plt.plot(hours, temp, label="Temperature (°C)")
    plt.plot(hours, hum, label="Humidity (%)")
    plt.legend()
    plt.xlabel("Hours")
    plt.ylabel("Environment Condition")
    plt.xticks(rotation=45)
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
        
        
    plt.title(f"Humidity by hour within the environment")
    plt.plot(hours, humidity_avg, label="Average Humidity (°C)")
    plt.plot(hours, humidity_min, label="Minimum Humidity (°C)")
    plt.plot(hours, humidity_max, label="Maximum Humidity (°C)")
    plt.legend()
    plt.xlabel("Hours")
    plt.ylabel("Humidity (%)")
    plt.xticks(rotation=45)
    if show:
        plt.show()
    else:
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
            
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
        
    plt.title(f"Temperature by hour within the environment")
    plt.plot(hours, temp_avg, label="Average Temperature (°C)")
    plt.plot(hours, temp_min, label="Minimum Temperature (°C)")
    plt.plot(hours, temp_max, label="Maximum Temperature (°C)")
    plt.legend()
    plt.xlabel("Hours")
    plt.ylabel("Temperature (°C)")
    plt.xticks(rotation=45)
    if show:
        plt.show()
    else:        
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
            
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
        
    plt.title("Average Temperature in the environment by the day of the month")
    plt.plot(days, temp_ave, label="Average Temperature (°C)", color="red")
    plt.plot(days, temp_min, label="Minimum Temperature (°C)", color="blue")
    plt.plot(days, temp_max, label="Maximum Temperature (°C)", color="green")
    plt.legend()
    plt.xlabel("Days")
    plt.ylabel("Temperature (°C)")
    plt.xticks(rotation=45)
    
    if show == True:
        plt.show()
    else:
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
            
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
        
    plt.title("Average Humidity in the environment by the day of the month")
    plt.plot(days, humidity_ave, label="Average Humidity (°C)", color="red")
    plt.plot(days, humidity_min, label="Minimum Humidity (°C)", color="blue")
    plt.plot(days, humidity_max, label="Maximum Humidity (°C)", color="green")
    plt.legend()
    plt.xlabel("Days")
    plt.ylabel("Humidity (%)")
    plt.xticks(rotation=45)
    
    if show == True:
        plt.show()
    else:
        file_name = f"static/graphs/{export_file_name}.png"
        if os.path.exists(file_name):
            os.remove(file_name)
            
        plt.savefig(file_name)
        plt.close()

@app_schedule.task("interval", id="Daily_Graph", hours=24)
def daily_graph():
    average_stat_by_week_temperature(False)
    average_stat_by_week_humidity(False)
    print("Updated Daily Graphs")

@app_schedule.task("interval", id="Hourly_Graph", hours=1)
def hour_graph():
    average_stat_by_day_temperature(False)
    average_stat_by_day_humidity(False)
    print("Updated Hourly Graph")

@app_schedule.task("interval", id="Sensor Check", seconds=30)
def sensor_message_check():
    global environment_sensor_interaction
    if environment_sensor_interaction:
        print("Sensor Interacted with server.")
        environment_sensor_interaction = False
    else:
        environment_sensor_interaction = False
        print("Sensor not interacted with server.")
        reset_sensors()
    

def generate_graphs():
    daily_graph()
    hour_graph()

    print("\nUpdated Graphs\n\n")
    
def empty_directory(path=""):
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

def setup_server():
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
    app_schedule.start()
    app.run(host="0.0.0.0", port=8080)

def clean_up_server():
    home_fan_control(False)
    get_record_count()
    sleep(5)


if __name__ == "__main__":
    setup_server()
    run_server()
    clean_up_server()