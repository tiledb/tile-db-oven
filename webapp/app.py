import json
from flask import Flask, render_template, request, jsonify
import serial
import serial.tools.list_ports
import threading
import time

app = Flask(__name__)

ser = None
serial_buffer = []

# Load config
with open("config.json", "r") as f:
    config = json.load(f)
default_port = config.get("default_port", "/dev/ttyACM0")
default_baudrate = config.get("default_baudrate", 115200)


def serial_reader():
    global ser, serial_buffer
    while True:
        if ser and ser.is_open:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if line:
                    serial_buffer.append(line)
                # keep buffer limited
                serial_buffer[:] = serial_buffer[-300:]
            except:
                pass
        time.sleep(0.05)


threading.Thread(target=serial_reader, daemon=True).start()


@app.route("/")
def index():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return render_template("index.html", ports=ports,
                           default_port=default_port,
                           default_baudrate=default_baudrate)


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


@app.route("/send", methods=["POST"])
def send():
    global ser
    cmd = request.json["cmd"]
    if ser and ser.is_open:
        ser.write((cmd + "\n").encode())
    return jsonify({"status": "ok"})


@app.route("/serial")
def serial_output():
    return jsonify(serial_buffer)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)