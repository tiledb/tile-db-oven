import json
import os
import time
import threading
from datetime import datetime
from collections import deque

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

import serial
import serial.tools.list_ports


LOG_FILE = "log/all.log"
os.makedirs("log", exist_ok=True)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

ser = None
serial_buffer = deque(maxlen=300)
serial_lock = threading.Lock()

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

default_port = config.get("default_port", "/dev/ttyACM0")
default_baudrate = config.get("default_baudrate", 115200)
default_min_temp = config.get("default_min_temp", 20)
default_max_temp = config.get("default_max_temp", 30)
default_target_temp = config.get("default_target_temp", 25)
default_run_hours = config.get("default_run_hours", 0)
default_run_minutes = config.get("default_run_minutes", 30)


# ---------------------------------------------------
# Oven Status dictionary
# ---------------------------------------------------
oven_status = {
    "Tmin": "",
    "Tmax": "",
    "Ttarget": "",
    "Toven": "",
    "RunHours": "",
    "RunMins": "",
    "RunTotalMins": "",
    "BurninAccruedMins": "",
    "RunningTime": "",
    "Debug": "",
    "State": "",
    "EnableRun": "",
    "EnableHeater": "",
    "LV0": "",
    "LV1": "",
    "LV2": "",
    "LV3": "",
    "BurninDone": ""
}

oven_status_lock = threading.Lock()



# ---------------------------------------------------
# SERIAL MANAGER THREAD
# ---------------------------------------------------

def serial_manager():
    global ser, oven_status

    last_status_request = 0

    while True:
        # Connect if needed
        if ser is None or not ser.is_open:
            try:
                print(f"[SERIAL] Attempting connection to {default_port}")
                ser = serial.Serial(default_port, default_baudrate, timeout=1)
                print(f"[SERIAL] Connected to {default_port}")
            except Exception as e:
                print(f"[SERIAL] Connect failed: {e}")
                time.sleep(2)
                continue

        try:
            now = time.time()
            # Poll status every 1 second
            if now - last_status_request >= 1:
                if ser and ser.is_open:
                    ser.write(b"11,2\n")  # request status
                last_status_request = now

            # Read serial line
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S ->")
                full_line = f"{timestamp} {line}"

                # Check if line is a status line
                if "Tmin=" in line:
                    # Parse and update oven_status
                    parts = line.split("->")[-1].strip().split(" | ")
                    for part in parts:
                        if "=" in part:
                            key, value = part.split("=")
                            key = key.strip()
                            value = value.strip()
                            if key in oven_status:
                                oven_status[key] = value
                    # STATUS LINES ARE NOT APPENDED TO SERIAL BUFFER
                    with open(LOG_FILE, "a") as f:
                        f.write(full_line + "\n")
                    continue
                if "11/2" in line:
                    with open(LOG_FILE, "a") as f:
                        f.write(full_line + "\n")
                    continue
                # Otherwise, normal serial line → console + log
                with serial_lock:
                    serial_buffer.append(full_line)
                with open(LOG_FILE, "a") as f:
                    f.write(full_line + "\n")

        except Exception as e:
            print(f"[SERIAL] Connection lost: {e}")
            try:
                ser.close()
            except:
                pass
            ser = None
            time.sleep(2)

def start_serial_thread():
    t = threading.Thread(target=serial_manager, daemon=True)
    t.start()


# ---------------------------------------------------
# WEB ROUTES
# ---------------------------------------------------

@app.route("/")
def index():

    ports = [p.device for p in serial.tools.list_ports.comports()]
    prefix = request.script_root

    return render_template(
        "index.html",
        ports=ports,
        prefix=prefix,
        default_port=default_port,
        default_baudrate=default_baudrate,
        default_min_temp=default_min_temp,
        default_max_temp=default_max_temp,
        default_target_temp=default_target_temp,
        default_run_hours=default_run_hours,
        default_run_minutes=default_run_minutes
    )


# ---------------------------------------------------
# SERIAL API
# ---------------------------------------------------

@app.route("/connection_status", methods=["GET"])
def connection_status():
    """
    Kept for frontend compatibility.
    Does NOT open the hardware port anymore.
    """
    if ser and ser.is_open:
        return jsonify({"status": "connected"})
    else:
        return jsonify({"status": "waiting_for_device"})

@app.route("/oven_status", methods=["GET"])
def get_oven_status():
    """
    Returns the current oven status as JSON.
    """
    return jsonify(oven_status)

@app.route("/connect", methods=["POST"])
def connect():
    """
    Kept for frontend compatibility.
    Does NOT open the hardware port anymore.
    """
    if ser and ser.is_open:
        return jsonify({"status": "connected"})
    else:
        return jsonify({"status": "waiting_for_device"})


@app.route("/disconnect", methods=["POST"])
def disconnect():
    """
    Frontend terminal reset only.
    Does not close serial port.
    """
    with serial_lock:
        serial_buffer.clear()

    return jsonify({"status": "terminal_cleared"})


@app.route("/send", methods=["POST"])
def send():

    global ser

    cmd = request.json["cmd"]

    if ser and ser.is_open:
        try:
            ser.write((cmd + "\n").encode())
        except Exception as e:
            return jsonify({"status": "error", "msg": str(e)})
    else:
        return jsonify({"status": "error", "msg": "serial not connected"})

    return jsonify({"status": "ok"})


@app.route("/serial")
def serial_output():

    with serial_lock:
        data = list(serial_buffer)

    return jsonify(data)


# ---------------------------------------------------
# LOG DOWNLOAD
# ---------------------------------------------------

@app.route("/download_log")
def download_log():

    try:
        return send_file(LOG_FILE, as_attachment=True)
    except Exception as e:
        return f"Error downloading log: {e}", 500


# ---------------------------------------------------
# START SERVER
# ---------------------------------------------------

if __name__ == "__main__":

    start_serial_thread()

    app.run(
        host="0.0.0.0",
        port=8888,
        debug=True,
        threaded=True,
        use_reloader=False
    )