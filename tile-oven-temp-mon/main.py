# =========================
# IMPORTS
# =========================
import machine, time, gc, ujson, _thread
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P8
import onewire
import secrets
from netmgr import NetManager

# =========================
# BOOT BUTTON SAFE MODE
# =========================
button_a = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
button_b = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
time.sleep(0.1)
if button_a.value() == 0 and button_b.value() == 0:
    display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_P8, rotate=270)
    display.set_backlight(1.0)
    display.set_font("serif")
    display.set_pen(0)
    display.clear()
    display.set_pen(255)
    display.text(f"SAFE MODE -> A:{button_a.value()} B:{button_b.value()}", 0, 100, 240, 0.4)
    display.update()
    print("SAFE MODE - boot halted")
    while True: time.sleep(1)

gc.collect()

# =========================
# CONFIG / SECRETS
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
# DISPLAY SETUP
# =========================
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_P8, rotate=270)
display.set_backlight(1.0)
display.set_font("serif")

black_pen = display.create_pen(0,0,0)
blue_pen  = display.create_pen(0,0,255)
red_pen   = display.create_pen(255,0,0)
green_pen = display.create_pen(0,255,0)

def display_clear(): display.set_pen(0); display.clear(); display.update()
def display_status_bar(pen,text): display.set_pen(63); display.rectangle(0,225,120,15); display.set_pen(pen); display.rectangle(121,225,135,15); display.set_pen(255); display.text(text,0,232,135,0.4); display.update()

display_clear()

# =========================
# NETMANAGER
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
# SENSOR CONFIG
# =========================
I2C_ID = [0,1,0,1,0]; SCL_PIN=[1,3,5,7,9]; SDA_PIN=[0,2,4,6,8]; I2C_ADDRESS=[0x40]*5
OW_DATA_PIN = [21,22,26,27,28]

temperature_hdc1080 = [0]*len(I2C_ID)
humidity_hdc1080 = [0]*len(I2C_ID)
temperature_max31850k = [0]*len(OW_DATA_PIN)
data_lock = _thread.allocate_lock()

# I2C INIT
i2c = [machine.I2C(I2C_ID[i], scl=machine.Pin(SCL_PIN[i]), sda=machine.Pin(SDA_PIN[i]), freq=400000) for i in range(len(I2C_ID))]

# ONEWIRE INIT
ow = [onewire.OneWire(machine.Pin(pin)) for pin in OW_DATA_PIN]

gc.collect()

# =========================
# SENSOR READ FUNCTIONS
# =========================
def read_temperature_and_humidity_hdc1080(i):
    try:
        i2c[i].writeto(I2C_ADDRESS[i],b'\x00'); time.sleep(0.05)
        temp = i2c[i].readfrom(I2C_ADDRESS[i],2)
        i2c[i].writeto(I2C_ADDRESS[i],b'\x01'); time.sleep(0.05)
        hum = i2c[i].readfrom(I2C_ADDRESS[i],2)
        t = ((temp[0]<<8)+temp[1])*175.72/65536.0-46.85
        h = ((hum[0]<<8)+hum[1])*125.0/65536.0-6
        return t,h
    except: return 0,0

def get_temperature_and_humidity_hdc1080():
    t,h = [],[]
    for i in range(len(I2C_ID)):
        temp,hum = read_temperature_and_humidity_hdc1080(i)
        t.append(temp); h.append(hum)
    return t,h

def get_temperature_max31850k():
    temps=[]
    for o in range(len(OW_DATA_PIN)):
        roms = ow[o].scan()
        if roms:
            rom=roms[0]; ow[o].reset(); ow[o].select_rom(rom); ow[o].writebyte(0x44); time.sleep(0.75)
            ow[o].reset(); ow[o].select_rom(rom); ow[o].writebyte(0xBE)
            data=[ow[o].readbyte() for _ in range(9)]
            temp=(data[1]<<8|data[0])*0.0625
            temps.append(temp)
        else: temps.append(0)
    return temps

# =========================
# DISPLAY
# =========================
def display_values(temp_h,hum_h,temp_k):
    display_clear()
    display.set_pen(255)
    y=5
    for i in range(len(temp_h)): display.text("Sb"+str(i)+" T:"+str(round(temp_h[i],1)),0,y,135,0.45); y+=15
    for i in range(len(hum_h)): display.text("Sb"+str(i)+" H:"+str(round(hum_h[i],1)),0,y,135,0.45); y+=15
    for i in range(len(temp_k)): display.text("Ss"+str(i)+" T:"+str(round(temp_k[i],1)),0,y,135,0.45); y+=15
    display.update()

# =========================
# HOME ASSISTANT DISCOVERY
# =========================
def send_discovery(net, hdc_count, max_count):
    device_id=f"{BOARD_NAME}_{BOARD_ID}"
    base=MQTT_BASE_TOPIC
    device={"identifiers":[device_id],"name":f"{BOARD_NAME} {BOARD_ID}","manufacturer":"Custom","model":"Pico Sensor Hub"}

    for i in range(hdc_count):
        # temp
        sensor_id=f"{device_id}_hdc1080_temp_{i}"
        topic=f"{DISCOVERY_PREFIX}/sensor/{sensor_id}/config"
        payload={"name":f"HDC1080 {i} Temperature","state_topic":f"{base}/temperature/hdc1080_{i}","unit_of_measurement":"°C","device_class":"temperature","state_class":"measurement","suggested_display_precision":1,"unique_id":sensor_id,"device":device}
        net.publish_raw(topic.encode(),ujson.dumps(payload).encode())
        # hum
        sensor_id=f"{device_id}_hdc1080_hum_{i}"
        topic=f"{DISCOVERY_PREFIX}/sensor/{sensor_id}/config"
        payload={"name":f"HDC1080 {i} Humidity","state_topic":f"{base}/humidity/hdc1080_{i}","unit_of_measurement":"%","device_class":"humidity","state_class":"measurement","suggested_display_precision":1,"unique_id":sensor_id,"device":device}
        net.publish_raw(topic.encode(),ujson.dumps(payload).encode())

    for i in range(max_count):
        sensor_id=f"{device_id}_max31850_{i}"
        topic=f"{DISCOVERY_PREFIX}/sensor/{sensor_id}/config"
        payload={"name":f"Thermocouple {i}","state_topic":f"{base}/temperature/max31850_{i}","unit_of_measurement":"°C","device_class":"temperature","state_class":"measurement","suggested_display_precision":1,"unique_id":sensor_id,"device":device}
        net.publish_raw(topic.encode(),ujson.dumps(payload).encode())

# =========================
# THREADS
# =========================
def sensor_display_thread():
    global temperature_hdc1080, humidity_hdc1080, temperature_max31850k
    while True:
        t,h = get_temperature_and_humidity_hdc1080()
        k = get_temperature_max31850k()
        data_lock.acquire()
        temperature_hdc1080 = t; humidity_hdc1080 = h; temperature_max31850k = k
        data_lock.release()
        display_values(t,h,k)
        gc.collect()
        time.sleep(1)

def network_thread():
    while True:
        if net.ensure_connected() and net.mqtt is not None:
            send_discovery(net,len(I2C_ID),len(OW_DATA_PIN))
            data_lock.acquire()
            t=temperature_hdc1080.copy(); h=humidity_hdc1080.copy(); k=temperature_max31850k.copy()
            data_lock.release()
            for i in range(len(t)): net.publish(f"temperature/hdc1080_{i}",str(t[i]))
            for i in range(len(h)): net.publish(f"humidity/hdc1080_{i}",str(h[i]))
            for i in range(len(k)): net.publish(f"temperature/max31850_{i}",str(k[i]))
        gc.collect()
        time.sleep(5)

# =========================
# START THREADS
# =========================
print("Starting threads")
_thread.start_new_thread(network_thread,())
sensor_display_thread()