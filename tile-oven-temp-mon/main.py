# =========================
# IMPORTS
# =========================
import machine, time, gc, ujson, _thread
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P8
import onewire
import secrets
from netmgr import NetManager
from machine import SoftI2C, Pin

# =========================
# FAILSAFE / RESET
# =========================
reset_pin = machine.Pin(22, machine.Pin.IN)

def fail_and_reset(msg, err):
    print("ERROR:", msg)
    print("DETAILS:", err)
    print("Sleeping 5s before reset...")
    time.sleep(5)

    try:
        reset_pin.init(machine.Pin.OUT)
        reset_pin.value(0)
    except:
        machine.reset()

def guard(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        fail_and_reset(func.__name__, e)

# =========================
# LAST VALID STORAGE
# =========================
I2C_ID = [0,1,0,1,0]
SCL_PIN = [1,3,5,7,9]
SDA_PIN = [0,2,4,6,8]
I2C_ADDRESS = [0x40]*5
OW_DATA_PIN = [21,22,26,27,28]

last_valid_temp_hdc = [0]*len(I2C_ID)
last_valid_hum_hdc  = [0]*len(I2C_ID)
last_valid_temp_max = [0]*len(OW_DATA_PIN)

# =========================
# ZERO READ COUNTERS FOR HDC
# =========================
hdc_zero_count_temp = [0]*len(I2C_ID)
hdc_zero_count_hum  = [0]*len(I2C_ID)

# =========================
# BOOT SAFE MODE
# =========================
button_a = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
button_b = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
time.sleep(0.1)
if button_a.value() == 0 and button_b.value() == 0:
    display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_P8, rotate=270)
    display.set_backlight(1.0)
    display.set_font("serif")
    display.set_pen(0); display.clear()
    display.set_pen(255)
    display.text("SAFE MODE", 0, 100, 240, 0.6)
    display.update()
    while True:
        time.sleep(1)

gc.collect()

# =========================
# CONFIG
# =========================
SSID = secrets.WIFI_SSID
PASSWORD = secrets.WIFI_PASS
MQTT_BROKER = secrets.MQTT_BROKER
MQTT_USER = secrets.MQTT_USER
MQTT_PASS = secrets.MQTT_PASS
MQTT_PORT = secrets.MQTT_PORT
MQTT_BASE_TOPIC = secrets.MQTT_BASE_TOPIC
DISCOVERY_PREFIX = secrets.DISCOVERY_PREFIX
BOARD_NAME = secrets.BOARD_NAME
BOARD_ID = secrets.BOARD_ID

# =========================
# DISPLAY
# =========================
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_P8, rotate=270)
display.set_backlight(1.0)
display.set_font("serif")

def display_clear():
    display.set_pen(0)
    display.clear()
    display.update()

def display_values(temp_h, hum_h, temp_k):
    try:
        display_clear()
        display.set_pen(255)
        y = 5
        for i in range(len(temp_h)):
            display.text(f"Sb{i} T:{round(temp_h[i],1)}",0,y,135,0.45); y += 15
        for i in range(len(hum_h)):
            display.text(f"Sb{i} H:{round(hum_h[i],1)}",0,y,135,0.45); y += 15
        for i in range(len(temp_k)):
            display.text(f"Ss{i} T:{round(temp_k[i],1)}",0,y,135,0.45); y += 15
        display.update()
    except Exception as e:
        fail_and_reset("display", e)

display_clear()

# =========================
# NET
# =========================
net = NetManager(
    wifi_ssid=SSID,
    wifi_pass=PASSWORD,
    mqtt_broker=MQTT_BROKER,
    mqtt_user=MQTT_USER,
    mqtt_pass=MQTT_PASS,
    mqtt_port=MQTT_PORT,
    base_topic=MQTT_BASE_TOPIC
)

# =========================
# SOFT I2C SETUP
# =========================
i2c = [
    SoftI2C(
        scl=Pin(SCL_PIN[i]),
        sda=Pin(SDA_PIN[i]),
        freq=100000  # SoftI2C for independent buses
    )
    for i in range(len(I2C_ID))
]

# =========================
# ONEWIRE
# =========================
ow = [onewire.OneWire(Pin(pin)) for pin in OW_DATA_PIN]

# =========================
# HDC1080
# =========================
def read_temperature_and_humidity_hdc1080(i):
    global hdc_zero_count_temp, hdc_zero_count_hum

    for attempt in range(3):
        try:
            # Temperature
            i2c[i].writeto(I2C_ADDRESS[i], b'\x00')
            time.sleep(0.05)
            temp = i2c[i].readfrom(I2C_ADDRESS[i], 2)
            # Humidity
            i2c[i].writeto(I2C_ADDRESS[i], b'\x01')
            time.sleep(0.05)
            hum = i2c[i].readfrom(I2C_ADDRESS[i], 2)

            t = ((temp[0]<<8)+temp[1])*175.72/65536.0-46.85
            h = ((hum[0]<<8)+hum[1])*125.0/65536.0-6

            # ✅ Valid ranges
            if -40 < t < 125 and 0 <= h <= 100:

                # Handle zero reads logic
                if t == 0:
                    hdc_zero_count_temp[i] += 1
                    if hdc_zero_count_temp[i] < 3:
                        t = last_valid_temp_hdc[i]
                else:
                    hdc_zero_count_temp[i] = 0

                if h == 0:
                    hdc_zero_count_hum[i] += 1
                    if hdc_zero_count_hum[i] < 3:
                        h = last_valid_hum_hdc[i]
                else:
                    hdc_zero_count_hum[i] = 0

                last_valid_temp_hdc[i] = t
                last_valid_hum_hdc[i] = h
                return t, h

        except Exception as e:
            print(f"HDC{i} error:", e)
            time.sleep(0.1)  # small delay before retry

    # If all retries failed, return last valid values
    return last_valid_temp_hdc[i], last_valid_hum_hdc[i]



def get_temperature_and_humidity_hdc1080():
    t, h = [], []
    for i in range(len(I2C_ID)):
        temp, hum = read_temperature_and_humidity_hdc1080(i)
        t.append(temp)
        h.append(hum)
    return t, h

# =========================
# THERMOCOUPLE
# =========================
def get_temperature_max31850k():
    temps = []
    for o in range(len(OW_DATA_PIN)):
        value = None
        for attempt in range(3):
            try:
                roms = ow[o].scan()
                if not roms:
                    value = last_valid_temp_max[o]
                    break
                rom = roms[0]
                ow[o].reset(); ow[o].select_rom(rom); ow[o].writebyte(0x44)
                time.sleep(0.75)
                ow[o].reset(); ow[o].select_rom(rom); ow[o].writebyte(0xBE)
                data = [ow[o].readbyte() for _ in range(9)]
                temp = (data[1]<<8 | data[0]) * 0.0625
                if temp != 0:
                    last_valid_temp_max[o] = temp
                    value = temp
                    break
            except Exception as e:
                print(f"TC{o} error:", e)
            time.sleep(0.1)
        if value is None:
            value = last_valid_temp_max[o]
        temps.append(value)
    return temps

# =========================
# MQTT DISCOVERY
# =========================
def send_discovery(net, hdc_count, max_count):
    device_id = f"{BOARD_NAME}_{BOARD_ID}"
    base = MQTT_BASE_TOPIC
    device = {
        "identifiers":[device_id],
        "name":f"{BOARD_NAME} {BOARD_ID}",
        "manufacturer":"Custom",
        "model":"Pico Sensor Hub"
    }

    for i in range(hdc_count):
        # Temperature
        payload = {
            "name":f"HDC1080 {i} Temperature",
            "state_topic":f"{base}/temperature/hdc1080_{i}",
            "unit_of_measurement":"°C",
            "device_class":"temperature",
            "state_class":"measurement",
            "force_update": True,
            "unique_id":f"{device_id}_hdc1080_temp_{i}",
            "device":device
        }
        guard(net.publish_raw,
            f"{DISCOVERY_PREFIX}/sensor/{device_id}_hdc1080_temp_{i}/config".encode(),
            ujson.dumps(payload).encode()
        )

        # Humidity
        payload = {
            "name":f"HDC1080 {i} Humidity",
            "state_topic":f"{base}/humidity/hdc1080_{i}",
            "unit_of_measurement":"%",
            "device_class":"humidity",
            "state_class":"measurement",
            "force_update": True,
            "unique_id":f"{device_id}_hdc1080_hum_{i}",
            "device":device
        }
        guard(net.publish_raw,
            f"{DISCOVERY_PREFIX}/sensor/{device_id}_hdc1080_hum_{i}/config".encode(),
            ujson.dumps(payload).encode()
        )

    for i in range(max_count):
        payload = {
            "name":f"Thermocouple {i}",
            "state_topic":f"{base}/temperature/max31850_{i}",
            "unit_of_measurement":"°C",
            "device_class":"temperature",
            "state_class":"measurement",
            "force_update": True,
            "unique_id":f"{device_id}_max31850_{i}",
            "device":device
        }
        guard(net.publish_raw,
            f"{DISCOVERY_PREFIX}/sensor/{device_id}_max31850_{i}/config".encode(),
            ujson.dumps(payload).encode()
        )

# =========================
# THREADS
# =========================
temperature_hdc1080 = [0]*len(I2C_ID)
humidity_hdc1080 = [0]*len(I2C_ID)
temperature_max31850k = [0]*len(OW_DATA_PIN)
data_lock = _thread.allocate_lock()

def sensor_display_thread():
    global temperature_hdc1080, humidity_hdc1080, temperature_max31850k
    while True:
        try:
            t,h = get_temperature_and_humidity_hdc1080()
            k = get_temperature_max31850k()
            data_lock.acquire()
            temperature_hdc1080 = t
            humidity_hdc1080 = h
            temperature_max31850k = k
            data_lock.release()
            display_values(t,h,k)
            gc.collect()
            time.sleep(1)
        except Exception as e:
            fail_and_reset("sensor_thread", e)

def network_thread():
    while True:
        try:
            if net.ensure_connected() and net.mqtt is not None:
                send_discovery(net, len(I2C_ID), len(OW_DATA_PIN))
                data_lock.acquire()
                t = temperature_hdc1080.copy()
                h = humidity_hdc1080.copy()
                k = temperature_max31850k.copy()
                data_lock.release()
                for i in range(len(t)):
                    guard(net.publish, f"temperature/hdc1080_{i}", str(t[i]))
                for i in range(len(h)):
                    guard(net.publish, f"humidity/hdc1080_{i}", str(h[i]))
                for i in range(len(k)):
                    guard(net.publish, f"temperature/max31850_{i}", str(k[i]))
            gc.collect()
            time.sleep(5)
        except Exception as e:
            fail_and_reset("network_thread", e)

# =========================
# START
# =========================
print("Starting threads")
_thread.start_new_thread(network_thread, ())
sensor_display_thread()