import json
import os
import time
import threading
import atexit
from datetime import datetime, UTC

import subprocess

from collections import deque

from flask import Flask, render_template, request, jsonify, send_file, make_response, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

import serial
import serial.tools.list_ports

from influxdb import InfluxDBClient
# ==========================================================
# INFLUXDB SETUP
# ==========================================================
host = "piro-atlas-lab.fysik.su.se"
port = 8086
username = "tiledb"
password = "T1le-db-word!"
database = "tiledb"

influxdb = InfluxDBClient(
    host=host,
    port=port,
    username=username,
    password=password,
    database=database
)


import struct
import requests
import numpy as np

# ---------------------------------------------------
# INFLUXDB THREAD
# ---------------------------------------------------

def influx_manager():
    global influxdb, oven_timestamp

    while True:
        try:
            # Copy oven_status safely
            with oven_status_lock:
                status = dict(oven_status)
                ts = oven_timestamp  # <- copy the timestamp here

            # Skip if no timestamp yet
            if ts is None:
                time.sleep(1)
                continue

            # Convert numeric fields
            fields = {}
            for key, value in status.items():
                if value == "":
                    continue
                try:
                    fields[key] = float(value)
                except:
                    fields[key] = value

            json_body = [
                {
                    "measurement": "Burnin_Oven",
                    "time": ts.isoformat(),  # <- use UTC-aware timestamp
                    "fields": fields
                }
            ]

            influxdb.write_points(json_body)

        except Exception as e:
            print(f"[INFLUX] Error: {e}")
            print("[INFLUX] Attempting reconnect...")
            try:
                influxdb = InfluxDBClient(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    database=database
                )
            except Exception as reconnect_error:
                print(f"[INFLUX] Reconnect failed: {reconnect_error}")

        time.sleep(5)
        


def start_influx_thread():

    t = threading.Thread(target=influx_manager, daemon=True)
    t.start()

LOG_FILE = "log/all.log"
os.makedirs("log", exist_ok=True)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

ser = None
serial_buffer = deque(maxlen=500)
serial_lock = threading.Lock()
serial_write_lock = threading.Lock()

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
    "Tinst": "",
    "RunHours": "",
    "RunMins": "",
    "RunTotalMins": "",
    "BurninAccruedMins": "",
    "BurninAccruedSecs": "",
    "RunningTime": "",
    "Debug": "",
    "State": "",
    "PreviousState": "",
    "EnableRun": "",
    "EnableHeater": "",
    "LV0": "",
    "LV1": "",
    "LV2": "",
    "LV3": "",
    "LVPower": "",
    "BurninDone": "",
    "BatchId": "",
    "ProccessorRunningTime": ""
}

oven_timestamp = None
oven_status_lock = threading.Lock()


# ==========================================================
# CAMERA GLOBAL STATE
# ==========================================================
camera_frame = None
camera_stats = {}
camera_lock = threading.Lock()

CAMERA_URL = "http://192.168.0.90/byte_array"


# ==========================================================
# CAMERA FUNCTIONS
# ==========================================================

def fetch_camera_frame():
    r = requests.get(CAMERA_URL, timeout=2)
    return struct.unpack('<768f', r.content)


def compute_camera_stats(frame):
    arr = np.array(frame, dtype=np.float32)

    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    avg = float(np.mean(arr))
    median = float(np.median(arr))
    stdev = float(np.std(arr))

    range_val = max_val - min_val
    hotspot_strength = max_val - median

    burn_in_low = 65.0
    burn_in_high = 70.0
    overtemp_threshold = 70.0

    burn_in_pixels = int(np.sum((arr >= burn_in_low) & (arr <= burn_in_high)))
    overtemp_pixels = int(np.sum(arr > overtemp_threshold))

    max_idx = int(np.argmax(arr))
    min_idx = int(np.argmin(arr))

    h_y, h_x = divmod(max_idx, 32)
    c_y, c_x = divmod(min_idx, 32)

    center = arr[12 * 32 + 16]

    p10 = float(np.percentile(arr, 10))
    p90 = float(np.percentile(arr, 90))

    hot_area = int(np.sum(arr > (max_val - 2.0)))

    return {
        "min": round(min_val, 2),
        "max": round(max_val, 2),
        "avg": round(avg, 2),
        "median": round(median, 2),
        "stdev": round(stdev, 2),
        "range": round(range_val, 2),
        "hotspot_strength": round(hotspot_strength, 2),
        "burn_in_pixels": burn_in_pixels,
        "overtemp_pixels": overtemp_pixels,
        "center": round(float(center), 2),
        "hotspot_x": h_x,
        "hotspot_y": h_y,
        "coldspot_x": c_x,
        "coldspot_y": c_y,
        "p10": round(p10, 2),
        "p90": round(p90, 2),
        "hot_area": hot_area,
        "overheat": int(overtemp_pixels > 0),
        "burn_in_risk": int(burn_in_pixels > 0),
    }

# ==========================================================
# CAMERA THREAD
# ==========================================================

def camera_manager():
    global camera_frame, camera_stats

    while True:
        try:
            frame = fetch_camera_frame()
            stats = compute_camera_stats(frame)

            with camera_lock:
                camera_frame = frame
                camera_stats = stats

        except Exception as e:
            print(f"[CAMERA] Error: {e}")

        time.sleep(2)


def start_camera_thread():
    t = threading.Thread(target=camera_manager, daemon=True)
    t.start()





# ---------------------------------------------------
# SERIAL MANAGER THREAD
# ---------------------------------------------------

def serial_manager():
    global ser, oven_status

    last_status_request = 0

    # Open log file once for performance
    log_file = open(LOG_FILE, "a", buffering=1)

    while True:

        # Connect if needed
        if ser is None or not ser.is_open:
            try:
                print(f"[SERIAL] Attempting connection to {default_port}")
                ser = serial.Serial(default_port, default_baudrate, timeout=0.2)
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
                    with serial_write_lock:
                        ser.write(b"11,2\n")
                last_status_request = now

            line = None

            if ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()

            if line:

                timestamp_dt = datetime.now(UTC)
                timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S ->")
                full_line = f"{timestamp} {line}"

                # ---------------------------------------------------
                # STATUS LINE PARSER
                # ---------------------------------------------------
                if "Tmin=" in line:

                    parts = line.split("->")[-1].strip().split(" | ")

                    with oven_status_lock:
                        global oven_timestamp
                        oven_timestamp = timestamp_dt

                        for part in parts:

                            if "=" not in part:
                                continue

                            try:
                                key, value = part.split("=", 1)
                            except ValueError:
                                continue

                            key = key.strip()
                            value = value.strip()

                            if key in oven_status:
                                oven_status[key] = value

                    log_file.write(full_line + "\n")
                    continue

                # Skip poll response
                if "11/2" in line:
                    log_file.write(full_line + "\n")
                    continue

                # ---------------------------------------------------
                # NORMAL SERIAL LINE
                # ---------------------------------------------------
                with serial_lock:
                    serial_buffer.append(full_line)

                log_file.write(full_line + "\n")

        except Exception as e:

            print(f"[SERIAL] Connection lost: {e}")

            try:
                ser.close()
            except:
                pass

            ser = None
            time.sleep(2)

        time.sleep(0.01)


def start_serial_thread():
    t = threading.Thread(target=serial_manager, daemon=True)
    t.start()


# ---------------------------------------------------
# WEB ROUTES
# ---------------------------------------------------
@app.route("/")
def index_redirect():
    ts = int(datetime.now().timestamp())
    if 'ts' not in request.args:
        return redirect(url_for('index_redirect', ts=ts))
    
    # Now the real page render
    ports = [p.device for p in serial.tools.list_ports.comports()]
    prefix = request.script_root
    rendered = render_template(
        "index.html",
        ports=ports,
        prefix=prefix,
        ts=ts,
        default_port=default_port,
        default_baudrate=default_baudrate,
        default_min_temp=default_min_temp,
        default_max_temp=default_max_temp,
        default_target_temp=default_target_temp,
        default_run_hours=default_run_hours,
        default_run_minutes=default_run_minutes
    )
    response = make_response(rendered)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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

    with oven_status_lock:
        return jsonify(dict(oven_status))


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


@app.route("/clear", methods=["POST"])
def clear():
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
            with serial_write_lock:
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


@app.route("/set_batchid", methods=["POST"])
def set_batchid():
    global oven_status
    data = request.json
    batch_id = data.get("batch_id", 0)
    oven_status["BatchId"] = batch_id
    # print(f"Batch ID set to: {batch_id}")
    return {"status": "ok", "BatchId": batch_id}


@app.route("/restart_service", methods=["POST"])
def restart_service():
    try:
        # Run the systemctl command as root
        subprocess.run(
            ["sudo", "systemctl", "restart", "tile-oven-control.service"],
            check=True
        )
        return jsonify({"success": True, "message": "Oven service restarted."})
    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/observer")
def observer():

    ts = int(datetime.now().timestamp())

    prefix = request.script_root

    rendered = render_template(
        "observer.html",
        prefix=prefix,
        ts=ts
    )

    response = make_response(rendered)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

# ==========================================================
# CAMERA API
# ==========================================================

@app.route("/camera/frame")
def camera_frame_route():
    with camera_lock:
        if camera_frame is None:
            return "No frame", 503

        if len(camera_frame) != 768:
            return f"Bad frame size: {len(camera_frame)}", 500

        packed = struct.pack('<768f', *camera_frame)

    return packed, 200, {'Content-Type': 'application/octet-stream'}


@app.route("/camera/stats")
def camera_stats_route():
    with camera_lock:
        return jsonify(camera_stats)

# ---------------------------------------------------
# CLEANUP
# ---------------------------------------------------

def cleanup():

    global ser

    try:
        if ser and ser.is_open:
            ser.close()
            print("[SERIAL] Port closed")
    except:
        pass


atexit.register(cleanup)


# ---------------------------------------------------
# START SERVER
# ---------------------------------------------------

if __name__ == "__main__":

    start_serial_thread()
    start_influx_thread()
    start_camera_thread() 

    app.run(
        host="0.0.0.0",
        port=8888,
        debug=True,
        threaded=True,
        use_reloader=False
    )