import network
import time
from umqtt.simple import MQTTClient
import ubinascii
import machine
import usocket as socket

class NetManager:
    def __init__(
        self,
        wifi_ssid,
        wifi_pass,
        mqtt_broker,
        mqtt_user=None,
        mqtt_pass=None,
        mqtt_port=1883,
        base_topic="atlas.net/db_el_tester/xx",
        client_id=None,
        wifi_timeout=5000,      # ms
        wifi_retry_interval=10000 # ms
    ):
        self.wifi_ssid = wifi_ssid
        self.wifi_pass = wifi_pass
        self.mqtt_broker = mqtt_broker
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass
        self.mqtt_port = mqtt_port
        self.base_topic = base_topic.encode()
        self.wifi_timeout = wifi_timeout
        self.wifi_retry_interval = wifi_retry_interval

        if client_id is None:
            client_id = b"pico-" + ubinascii.hexlify(machine.unique_id())
        self.client_id = client_id

        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.mqtt = None
        self.last_wifi_attempt = 0

    # ---------- Non-blocking WiFi connect ----------
    def connect_wifi(self):
        now = time.ticks_ms()
        # Only attempt reconnect if retry interval has passed
        if time.ticks_diff(now, self.last_wifi_attempt) < self.wifi_retry_interval:
            return self.wlan.isconnected()

        self.last_wifi_attempt = now

        if self.wlan.isconnected():
            return True

        try:
            self.wlan.connect(self.wifi_ssid, self.wifi_pass)
        except Exception:
            return False

        # Check connection but only up to wifi_timeout
        start = time.ticks_ms()
        while not self.wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start) < self.wifi_timeout:
            time.sleep(0.05)

        return self.wlan.isconnected()

    # ---------- Non-blocking MQTT connect ----------
    def connect_mqtt(self, timeout_ms=500):
        if not self.wlan.isconnected():
            return False
        if self.mqtt is not None:
            return True

        try:
            # Quick TCP check to broker
            sock = socket.socket()
            sock.settimeout(timeout_ms / 1000)
            sock.connect((self.mqtt_broker, self.mqtt_port))
            sock.close()

            # Only now create and connect MQTT client
            self.mqtt = MQTTClient(
                client_id=self.client_id,
                server=self.mqtt_broker,
                port=self.mqtt_port,
                user=self.mqtt_user,
                password=self.mqtt_pass,
                keepalive=60
            )
            self.mqtt.connect()
            return True

        except Exception as e:
            # print("[WARN] MQTT connect failed:", e)
            self.mqtt = None
            return False

    # ---------- Public API ----------
    def ensure_connected(self):
        self.connect_wifi()   # non-blocking
        self.connect_mqtt()   # non-blocking
        return self.mqtt is not None

    def publish(self, topic, payload, retain=True):
        if not self.ensure_connected():
            return False
        try:
            full_topic = b"%s/%s" % (self.base_topic, topic)
            self.mqtt.publish(full_topic, payload, retain=retain)
            return True
        except Exception:
            self.mqtt = None
            return False
    
    def publish_raw(self, topic, payload, retain=True):
        if not self.ensure_connected():
            return False
        try:
            self.mqtt.publish(topic, payload, retain=retain)
            return True
        except Exception:
            self.mqtt = None
            return False