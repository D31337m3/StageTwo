# === code.py (CircuitPython - ESP32-S3 TOTP Auth Client) ===

import time
import board
import displayio
import terminalio
import binascii
import microcontroller
import rtc
import wifi
import socketpool
import adafruit_ntp
import ssl
import adafruit_requests
import json
import ubinascii
from adafruit_display_text import label
import adafruit_hotp
import adafruit_hashlib as hashlib
import adafruit_miniqr
from adafruit_display_shapes.rect import Rect

# === Configuration ===
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
TIME_STEP = 30  # seconds for TOTP code rotation

# === Display Setup ===
display = board.DISPLAY
main_group = displayio.Group()
display.show(main_group)
text_area = label.Label(terminalio.FONT, text="Booting...", scale=2, x=10, y=20)
main_group.append(text_area)

# === NVM Storage ===
NVM_KEY = b"TOTP_KEY:"
KEY_LENGTH = 16
URL_MAX_LENGTH = 48

def get_or_generate_secret_and_url():
    nvm_data = microcontroller.nvm[:64]
    if nvm_data.startswith(NVM_KEY):
        key = nvm_data[len(NVM_KEY):len(NVM_KEY)+KEY_LENGTH]
        url_bytes = nvm_data[len(NVM_KEY)+KEY_LENGTH:]
        server_url = url_bytes.decode("utf-8").strip("\x00")
        return key, server_url
    else:
        import os
        key = os.urandom(KEY_LENGTH)
        server_url = "https://yourserver.com/devmode/post"
        encoded_url = server_url.encode("utf-8").ljust(URL_MAX_LENGTH, b"\x00")
        nvm_write = NVM_KEY + key + encoded_url
        microcontroller.nvm[:len(nvm_write)] = nvm_write
        return key, server_url

def base32_encode(b):
    return ubinascii.b2a_base64(b).decode("utf-8").strip().replace("=", "").replace("\n", "")

def generate_totp(secret, interval=30):
    current_time = int(time.time())
    counter = current_time // interval
    hotp = adafruit_hotp.HOTP(secret, hashes=hashlib.sha1)
    return hotp.at(counter)

def sync_time():
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    pool = socketpool.SocketPool(wifi.rad