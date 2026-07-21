import json
import os
import gspread
from google.oauth2.service_account import Credentials
import time
from ai_camera import IMX500Detector
import subprocess
import threading
from flask import Flask, render_template_string, jsonify
import queue
import shutil
from collections import deque
import uuid
import asyncio
from bleak import BleakClient, BleakScanner
import traceback

PICO_MAC_ADDRESS = "28:CD:C1:0F:29:36"
SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
CHAR_UUID = "abcdef01-1234-5678-1234-56789abcdef0"

current_scale_weight = 0
current_detected_food = "None"

# Global handles to manage remote BLE writes from sync threads
ble_client = None
ble_loop = None

def notification_handler(sender, data):
    global current_scale_weight
    weight = data.decode('utf-8')
    current_scale_weight = weight
    print(f"Weight received: {current_scale_weight}g")

async def ble_manager():
    """Handles the async BLE connection and exposes client globally."""
    global ble_client
    while True:
        try:
            print(f"Connecting directly to {PICO_MAC_ADDRESS}...")
            device = await BleakScanner.find_device_by_address(PICO_MAC_ADDRESS, timeout=5.0)

            if not device:
                print(f"Device {PICO_MAC_ADDRESS} not in range. Retrying...")
                await asyncio.sleep(2)
                continue

            async with BleakClient(PICO_MAC_ADDRESS) as client:
                ble_client = client
                print("Connected!")
                await client.start_notify(CHAR_UUID, notification_handler)
                
                while client.is_connected:
                    await asyncio.sleep(0.5)
            
            ble_client = None
            print("Disconnected. Retrying...")
            await asyncio.sleep(2)
            
        except Exception as e:
            ble_client = None
            print(f"BLE Error: Could not connect to {PICO_MAC_ADDRESS}. Retrying in 5s...")
            traceback.print_exc()
            await asyncio.sleep(3)

def start_ble_thread():
    """Runs the asyncio event loop inside a separate thread and captures loop reference."""
    global ble_loop
    print("Starting BLE thread...")
    ble_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ble_loop)
    ble_loop.run_until_complete(ble_manager())

print("Scale configured with BLE remote architecture. Ready!")

readings = deque(maxlen=3)

app = Flask(__name__)
action_queue = queue.Queue()

@app.route('/get-weight')
def get_weight():
    return jsonify(weight=current_scale_weight, food=current_detected_food)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<body style="text-align:center; padding-top:50px;">

    <!-- This displays the live weight -->
    <h1 id="weight-display" style="font-size: 60px; color: #333; margin-bottom: 10px;">0.00g</h1>
    <!-- This displays the detected food name -->
    <h2 id="food-display" style="font-size: 30px; color: #666; margin-top: 0;">Detected Food: None</h2>

    <br>
    <button onclick="sendAction('detection')" style="padding:20px; font-size:20px;">Button 1: detection</button>
    <button onclick="sendAction('image')" style="padding:20px; font-size:20px;">Button 2: image</button>
    <button onclick="sendAction('import_to_drive')" style="padding:20px; font-size:20px;">Button 3: import_to_drive</button>
    <button onclick="sendAction('download_model')" style="padding:20px; font-size:20px;">Button 4: download_model</button>
    <button onclick="sendAction('deleate_images')" style="padding:20px; font-size:20px;">Button 5: deleate_images</button>
    <button onclick="sendAction('power_off')" style="padding:20px; font-size:20px;">Button 6: power_off</button>
    <button onclick="sendAction('tare')" style="padding:30px; font-size:30px;">Button 7: tare</button>

    <script>
        function sendAction(val) {
            fetch('/trigger/' + val);
        }

        setInterval(function() {
            fetch('/get-weight')
            .then(response => response.json())
            .then(data => {
                document.getElementById('weight-display').innerText = data.weight + 'g';
                document.getElementById('food-display').innerText = 'Detected Food: ' + data.food;
            });
        }, 50);
    </script>
</body>
</html>
"""

# --- Configuration ---
DB_FILE = "food_database.json"
CREDENTIALS_FILE = "credentials.json"
SHEET_ID = "1ovhwtE3Biuw7FV5g6-HF2aqYM2P2mRJ5aNetyZoj8YI"

# --- Setup Google Sheets ---
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1
database_sheet = client.open_by_key(SHEET_ID).worksheet("food_data")

model_path = "/home/pi/food_scale/my_modelrpk/network.rpk"

# Opening camera
if os.path.exists(model_path):
    camera = IMX500Detector(model_path)
    camera.start(show_preview=False)

def process():
    download_database()

    print("Monitoring...")
    while True:
        if not action_queue.empty():
            command_text = action_queue.get()
            if command_text == "detection":
                detection()
            if command_text == "image":
                camera.capture_image()
                print("image captured :)")
            if command_text == "import_to_drive":
                upload_images()
                print("driven :)")
            if command_text == "download_model":
                 update_model()
                 print("downloaded")
            if command_text == "deleate_images":
                 clear_images_folder()
                 print("deleated")
            if command_text == "power_off":
                 subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
            if command_text == "tare":
                 tare()
            print(f"Processing command: {command_text}")
        time.sleep(0.1)

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/trigger/<action>')
def trigger(action):
    action_queue.put(action)
    return jsonify(status="success", received=action)

def clear_images_folder(folder_path="/home/pi/food_scale/images/"):
    if not os.path.exists(folder_path):
        return
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def update_model():
    folder_path = "/home/pi/food_scale/downloads/"
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

    remote_name = "gdrive"
    remote_path = "export_to_pi"
    local_destination = "/home/pi/food_scale/downloads"

    if not os.path.exists(local_destination):
        os.makedirs(local_destination)

    cmd = ["rclone", "copy", f"{remote_name}:{remote_path}", local_destination]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr}")    

    cmd_final = ["imx500-package", "-i", "/home/pi/food_scale/downloads/packerOut.zip", "-o", "my_modelrpk"]
    try:
        subprocess.run(cmd_final, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")

def download_database():
    raw_data = database_sheet.get_all_records()
    transformed_data = {}
    for row in raw_data:
        food_name = row['Name']
        transformed_data[food_name] = {
            "protein": row['protein'],
            "carbs": row['carbs'],
            "fat": row['fat'],
            "kcal": row['kcal']
        }
    with open('food_database.json', 'w') as f:
        json.dump(transformed_data, f, indent=4)
    print("Database exported successfully!")

def upload_images():
    cmd = ["rclone", "copy", "/home/pi/food_scale/images/", "gdrive:/images_to_train"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Upload successful!")
    except Exception as e:
        print(f"Upload error: {e}")

def get_db():
    if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
        with open(DB_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

async def async_tare():
    """Sends the 'tare' command asynchronously to the Pico over BLE."""
    global ble_client
    if ble_client and ble_client.is_connected:
        try:
            await ble_client.write_gatt_char(CHAR_UUID, b"tare")
            print("Tare command sent successfully to Pico!")
        except Exception as e:
            print(f"Failed to write tare command: {e}")
    else:
        print("Cannot tare: Pico is not connected via BLE.")

def tare():
    """Thread-safe trigger bridge for taring the remote scale."""
    global ble_loop
    print("\nTaring scale remotely...")
    if ble_loop and ble_loop.is_running():
        asyncio.run_coroutine_threadsafe(async_tare(), ble_loop)
    else:
        print("BLE loop is not active.")

def detection():
    global current_detected_food
    print(current_scale_weight)
    print("Capturing...")
    camera.capture_and_detect()
    detected_objects = camera.get_detected_names()
    
    if not detected_objects:
        print("Nothing detected.")
        current_detected_food = "Nothing detected"
    else:
        db = get_db()
        for found_name in detected_objects:
            name = found_name.lower().strip()
            current_detected_food = name  
            print(f"Detected food: {name}")
            
            if name in db:
                weight = float(current_scale_weight) if current_scale_weight else 0.0
                unique_id = str(uuid.uuid4())
                multiplier = weight / 100.0
                item = db[name]
                sheet.append_row([
                    name,
                    item['protein'] * multiplier,
                    item['carbs'] * multiplier,
                    item['fat'] * multiplier,
                    weight,
                    unique_id,
                    item['kcal'] * multiplier
                ])
                print(f"Logged {name} to Google Sheets.")
            else:
                print(f"Food '{name}' not found in database.")

if __name__ == '__main__':
    threading.Thread(target=start_ble_thread, daemon=True).start()
    threading.Thread(target=process, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
