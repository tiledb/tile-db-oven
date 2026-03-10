import json
from flask import Flask, render_template, request, jsonify, send_file
import serial
import serial.tools.list_ports
import threading
import time
import os
from datetime import datetime

LOG_FILE = "log/all.log"
os.makedirs("log", exist_ok=True)  # make sure folder exists


app = Flask(__name__)

ser = None
serial_buffer = []

# Load config
with open("config.json", "r") as f:
    config = json.load(f)
default_port = config.get("default_port", "/dev/ttyACM0")
default_baudrate = config.get("default_baudrate", 115200)
default_min_temp = config.get("default_min_temp", 19)
default_max_temp = config.get("default_max_temp", 27)
default_run_hours = config.get("default_run_hours", 0)
default_run_minutes = config.get("default_run_minutes", 30)



def serial_reader():
    global ser, serial_buffer
    while True:
        if ser and ser.is_open:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                # print(line)  # debug print
                if line:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S ->")
                    full_line = f"{timestamp} {line}"
                    serial_buffer.append(full_line)
                    serial_buffer[:] = serial_buffer[-300:]  # keep buffer limited

                    # Append to log file
                    # print(full_line)  # also print to console
                    with open(LOG_FILE, "a") as f:
                        f.write(full_line + "\n")

            except Exception as e:
                print(f"Serial read error: {e}")
        time.sleep(0.05)

threading.Thread(target=serial_reader, daemon=True).start()


@app.route("/")
def index():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return render_template("index.html", ports=ports,
                           default_port=default_port,
                           default_baudrate=default_baudrate,
                           default_min_temp=default_min_temp,
                           default_max_temp=default_max_temp,
                           default_run_hours=default_run_hours,
                           default_run_minutes=default_run_minutes
                           )


@app.route("/connect", methods=["POST"])
def connect():
    global ser
    port = request.json["port"]
    baudrate = int(request.json["baudrate"])

    try:
        if ser and ser.is_open:
            ser.close()
        ser = serial.Serial(port, baudrate, timeout=1)
        return jsonify({"status": "connected"})
    except Exception as e:
        import traceback
        print("Serial connection failed:", traceback.format_exc())
        return jsonify({"status": "error", "msg": str(e)})


@app.route("/disconnect", methods=["POST"])
def disconnect():
    global ser, serial_buffer
    try:
        if ser and ser.is_open:
            ser.close()
            # ser = None
        serial_buffer.clear()  # clear buffer on disconnect
        return jsonify({"status": "disconnected"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route("/send", methods=["POST"])
def send():
    global ser
    cmd = request.json["cmd"]
    if ser and ser.is_open:
        ser.write((cmd + "\n").encode())
    return jsonify({"status": "ok"})


@app.route("/download_log")
def download_log():
    try:
        return send_file(LOG_FILE, as_attachment=True)
    except Exception as e:
        return f"Error downloading log: {e}", 500

@app.route("/serial")
def serial_output():
    return jsonify(serial_buffer)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)