import machine
import time
import onewire

from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, PEN_P8
#from pimoroni import RGBLED
# Reduced colours to save RAM
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, pen_type=PEN_P8, rotate=270)
display.set_backlight(1.0)
display.set_font("serif") # Lower case included

def colour(R,G,B): # Convert RGB888 to RGB332
    b = int(B/64)
    g = int(G/32)
    r = int(R/64)
    return b + g * 4 +r * 64
def display_clear():
    display.set_pen(0)
    display.clear()
    display.update()

def display_status_bar(status_pen, status_text):
    display.set_pen(63)
    display.rectangle(0,225,120, 15)
    display.set_pen(status_pen)
    display.rectangle(121,225,135, 15)
    display.set_pen(225)
    display.text(status_text, 0, 232, 135, 0.4)
    display.update()
    


# Initialize the display
black_pen=display.create_pen(0,0,0)
blue_pen=display.create_pen(0,0,255)
red_pen=display.create_pen(255,0,0)
green_pen=display.create_pen(0,255,0)
display_clear()



import network
import ubinascii
from umqtt.simple import MQTTClient

# WiFi configuration
SSID = "ATLAS.NET"
PASSWORD = "T1le-db-word!"

# Initialize the WiFi interface in station mode
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Function to scan for WiFi networks
def scan_wifi():
    networks = wlan.scan()  # Perform the scan
    for net in networks:
        ssid = net[0].decode('utf-8')  # Network name
        bssid = ':'.join(['%02x' % b for b in net[1]])  # MAC address
        channel = net[2]  # Channel
        RSSI = net[3]  # Signal strength
        authmode = net[4]  # Authentication mode
        #print(f"SSID: {ssid}, BSSID: {bssid}, Channel: {channel}, RSSI: {RSSI}, Authmode: {authmode}")
    return ssid, bssid, channel, RSSI, authmode

# Connect to WiFi
def connect_wifi(ssid, password, max_attempts):
    wlan.connect(ssid, password)
    
    attempts = 0
    
    while not wlan.isconnected() and attempts < max_attempts:
        print("Connecting to WiFi...")
        #display.clear()
        display_status_bar(red_pen,"Connect tries: " + str(attempts))
        time.sleep(1)
        attempts += 1
    
    if wlan.isconnected():
        print("Connected to WiFi")
        ip, subnet, gateway, dns = wlan.ifconfig()
        print("IP address:", ip)
        print("Subnet mask:", subnet)
        print("Gateway:", gateway)
        print("DNS server:", dns)
        display_status_bar(green_pen,"Connected!!!")
        time.sleep(1)
    else:
        print('Failed to connect to WiFi')
    
    #print('Network config:', wlan.ifconfig())
    

# MQTT configuration
MQTT_BROKER = "192.168.0.252"
MQTT_PORT = 1883
MQTT_TOPIC = "atlas.net/atlas-lab/picopi-oven/"
MQTT_USER = "tiledb"
MQTT_PASS = "T1le-db-word!"
CLIENT_ID = ubinascii.hexlify(machine.unique_id())

# Publish data to MQTT
def publish_mqtt(topic, message):
    client = MQTTClient(CLIENT_ID, MQTT_BROKER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PASS)
    try:
        client.connect()
        client.publish(topic, message)
        client.disconnect()
        #print("MQTT Publish Success")
        return "True"
        
    except Exception as e:
        #print("MQTT Publish Failed:"+ str(e))
        return "MQTT Publish Failed:"+ str(e)
        


#used by i2c now!
#led = RGBLED(6, 7, 8)
#led.set_rgb(0,0,0)     # Turn RGBLED OFF



# ==== Board now setup ====
#for i in range(8):
#    display.set_pen(2**i)
#    for z in range (40):
#        display.line(0,i*40 +z,135,i*40+z)
#display.update()
#time.sleep(1)



# I2C configuration
I2C_ID = [0,1,0,1,0]
SCL_PIN = [1,3,5,7,9]
SDA_PIN = [0,2,4,6,8]

# Sensor I2C address
I2C_ADDRESS = [0x40,0x40,0x40,0x40,0x40]

register_lut = [b'\x02',b'\x03',b'\xFE',b'\xFF']

# Initialize I2C
i2c = []
for i in range(len(I2C_ID)):
    print("Initializing HDC1080 I2C: ", i)
    i2c.append(machine.I2C(I2C_ID[i], scl=machine.Pin(SCL_PIN[i]), sda=machine.Pin(SDA_PIN[i]), freq=400000))


OW_DATA_PIN = [21,22,26,27,28]
ow =[]
# Initialize 1-Wire bus
for o in range(len(OW_DATA_PIN)):
    print("Initializing MAX31850K I2C: ", o)
    ow.append(onewire.OneWire(machine.Pin(OW_DATA_PIN[o])))


def to_binary(data):
    return ' '.join('{:08b}'.format(byte) for byte in data)

def read_temperature_and_humidity_hdc1080(i2c_id):
    try:
        # Read 4 bytes of data from the sensor
        i2c[i2c_id].writeto(I2C_ADDRESS[i2c_id], b'\x00') # command to read temperature
        time.sleep(0.1)
        temp_data = i2c[i2c_id].readfrom(I2C_ADDRESS[i2c_id], 2)
        #time.sleep(0.1)
        
        i2c[i2c_id].writeto(I2C_ADDRESS[i2c_id], b'\x01') # command to read humidity
        time.sleep(0.1)
        hum_data = i2c[i2c_id].readfrom(I2C_ADDRESS[i2c_id], 2)
        #time.sleep(0.1)
        
        # Convert the data to temperature and humidity
        temperature = ((temp_data[0] << 8) + temp_data[1]) * 175.72 / 65536.0 - 46.85
        humidity = ((hum_data[0] << 8) + hum_data[1]) * 125.0 / 65536.0 - 6.0
        
        return temperature, humidity
    except Exception as e:
        #print("Error reading from sensor:", e)
        return 0, 0

def get_temperature_and_humidity_hdc1080():
    temperature_array=[]
    humidity_array=[]
    for s in range(len(I2C_ID)):
        #print("Sensor on I2C chain: ",I2C_ID[s])
        temperature, humidity = read_temperature_and_humidity_hdc1080(s)
        temperature_array.append(temperature)
        humidity_array.append(humidity)
    return temperature_array, humidity_array

def print_temperature_and_humidity_hdc1080(temperature, humidity):
    for s in range(len(I2C_ID)):
        print("Sensor ", s," -> Temperature: {:.2f} C".format(temperature[s])," -> Humidity: {:.2f} %".format(humidity[s]))

def get_temperature_max31850k():
    temperature_array=[]
    for o in range(len(OW_DATA_PIN)):
        roms = ow[o].scan()
        #print("Found devices:", roms)

        if len(roms)>0:
            #print("1-Wire devices detected:", roms)

            for rom in roms:
                ow[o].reset()
                ow[o].select_rom(rom)
                ow[o].writebyte(0x44)  # Start temperature conversion
                time.sleep(1)  # Wait for conversion to complete

                ow[o].reset()
                ow[o].select_rom(rom)
                ow[o].writebyte(0xBE)  # Read scratchpad
                data = bytearray(9)
                for i in range(9):
                    data[i] = ow[o].readbyte()

                # Convert the data to temperature
                temp_lsb = data[0]
                temp_msb = data[1]
                temp = (temp_msb << 8 | temp_lsb) * 0.0625
                temperature_array.append(temp)
                #print("Sensor MAX31850K: ", str(o) ,"-> Temperature: {:.2f} °C".format(temp))


        else:
            temp=0
            temperature_array.append(temp)
            #print("Sensor MAX31850K: ", str(o) ,"-> Temperature: {:.2f} °C".format(temp))
    return temperature_array

def print_temperature_max31850k(temperature):
    for o in range(len(OW_DATA_PIN)):
        print("Sensor MAX31850K: ", str(o) ,"-> Temperature: {:.2f} °C".format(temperature[o]))

def display_values(temperature_hdc1080, humidity_hdc1080, temperature_max31850k):
    display_clear()
    display.set_pen(255)
    y_coordinate=5
    for s in range(len(temperature_hdc1080)):
        text="Sb"+str(s)+"-> T: "+str(temperature_hdc1080[s]) +"C"# + " - H: "+str(humidity_hdc1080[s])+"%"
        display.text(text, 0, y_coordinate, 135, 0.45)
        y_coordinate=y_coordinate+15
    for s in range(len(humidity_hdc1080)):
        text="Sb"+str(s)+"-> H: "+str(humidity_hdc1080[s])+"%"
        display.text(text, 0, y_coordinate, 135, 0.45)
        y_coordinate=y_coordinate+15
    for s in range(len(temperature_max31850k)):
        text="Ss"+str(s)+"-> T: "+str(temperature_max31850k[s])+"C"
        display.text(text, 0, y_coordinate, 135, 0.45)
        y_coordinate=y_coordinate+15
    display.update()
    
def publish_mqtt_values(temperature_hdc1080, humidity_hdc1080, temperature_max31850k):
    mqtt_status="True"
    for s in range(len(temperature_hdc1080)):
        topic=MQTT_TOPIC+"temperature/hdc1080_"+str(s)
        value=str(temperature_hdc1080[s])
        mqtt_status_buffer=publish_mqtt(topic,value)
        if not (mqtt_status_buffer=="True"):
            mqtt_status=mqtt_status_buffer
    for s in range(len(humidity_hdc1080)):
        topic=MQTT_TOPIC+"humidity/hdc1080_"+str(s)
        value=str(humidity_hdc1080[s])
        mqtt_status_buffer=publish_mqtt(topic,value)
        if not (mqtt_status_buffer=="True"):
            mqtt_status=mqtt_status_buffer

    for s in range(len(temperature_max31850k)):
        topic=MQTT_TOPIC+"temperature/max31850_"+str(s)
        value=str(temperature_max31850k[s])
        mqtt_status_buffer=publish_mqtt(topic,value)
        if not (mqtt_status_buffer=="True"):
            mqtt_status=mqtt_status_buffer
    return mqtt_status

# Main loop
ssid_find_attempts = 0
found_ssid, found_bssid, found_channel, found_RSSI, found_authmode = scan_wifi()
print("Found SSIDs...")
print(found_ssid)
#print("Found BSSIDs...")
#print(found_bssid)


while (ssid_find_attempts<5):
    found_ssid, found_bssid, found_channel, found_RSSI, found_authmode = scan_wifi()
    print(SSID + " not found... " + "Retrying " + str(ssid_find_attempts) + " times...")
    print("Found SSIDs...")
    print(found_ssid)
    if SSID in found_ssid:
        break
    ssid_find_attempts=ssid_find_attempts+1

connect_wifi(SSID, PASSWORD, 10)
wlan_ip, wlan_subnet, wlan_gateway, wlan_dns = wlan.ifconfig()

ssid_find_attempts=0
    
status_pen=green_pen
reconnect_wait_time=0
while True:
    temperature_hdc1080, humidity_hdc1080 = get_temperature_and_humidity_hdc1080()
    print_temperature_and_humidity_hdc1080(temperature_hdc1080, humidity_hdc1080)
    
    temperature_max31850k=get_temperature_max31850k()
    print_temperature_max31850k(temperature_max31850k)

    if(wlan.isconnected()):
        mqtt_status=publish_mqtt_values(temperature_hdc1080, humidity_hdc1080, temperature_max31850k)
        if (mqtt_status=="True"):
            status_pen=green_pen
        else:
            print(mqtt_status)
            status_pen=blue_pen
    else:
        print("Wifi disconnected!!!!")
        status_pen=red_pen
    
    display_values(temperature_hdc1080, humidity_hdc1080, temperature_max31850k)
        
    if wlan.isconnected():
        wait_time = 0
        status_text=wlan_ip
    else:
        status_text="Retry in: "+str(reconnect_wait_time)+ " cycles"
        if reconnect_wait_time<60:
            reconnect_wait_time=reconnect_wait_time+1
        else:
            reconnect_wait_time=0
            if SSID in found_ssid:
                connect_wifi(SSID, PASSWORD, 10)
                wlan_ip, wlan_subnet, wlan_gateway, wlan_dns = wlan.ifconfig()

        
    
    display_status_bar(status_pen,status_text)
    
    
    time.sleep(0.5)
        #for reg in register_lut:
        #    i2c[s].writeto(I2C_ADDRESS[s], reg)
        #    data = i2c[s].readfrom(I2C_ADDRESS[s], 2)
        #    print("Reg: " ,str(reg), " -> Data: ", str(to_binary(data)))
    







