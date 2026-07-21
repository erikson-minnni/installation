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
from HX711 import SimpleHX711
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

def notification_handler(sender, data):
    global current_scale_weight
    weight = data.decode('utf-8')
    current_scale_weight = weight
    print(f"Weight received: {current_scale_weight}g")

async def ble_manager():
    """Handles the async BLE connection using hardcoded MAC."""
    while True:
        try:
            print(f"Connecting directly to {PICO_MAC_ADDRESS}...")
            device = await BleakScanner.find_device_by_address(PICO_MAC_ADDRESS, timeout=5.0)

            if not device:
                print(f"Device {PICO_MAC_ADDRESS} not in range. Retrying...")
                await asyncio.sleep(2)
                continue

            async with BleakClient(PICO_MAC_ADDRESS) as client:
                print("Connected!")
                await client.start_notify(CHAR_UUID, notification_handler)
                
                while client.is_connected:
                    await asyncio.sleep(0.5)
            
            print("Disconnected. Retrying...")
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"BLE Error: Could not connect to {PICO_MAC_ADDRESS}. Retrying in 5s...")
            traceback.print_exc()
            await asyncio.sleep(3)

def start_ble_thread():
    print("ok")
    """Runs the asyncio event loop inside a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ble_manager())

REF_UNIT = -290
OFFSET_VAL = -152560

print("Scale configured with a 3g noise gate. Ready to weigh!")

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

        // Update weight and detected food every 50ms
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
    """Deletes all files inside the specified folder."""
    if not os.path.exists(folder_path):
        print(f"Folder {folder_path} does not exist.")
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def update_model():
    folder_path = "/home/pi/food_scale/downloads/"
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

    remote_name = "gdrive"
    remote_path = "export_to_pi"
    local_destination = "/home/pi/food_scale/downloads"

    if not os.path.exists(local_destination):
        os.makedirs(local_destination)

    cmd = ["rclone", "copy", f"{remote_name}:{remote_path}", local_destination]

    try:
        print(f"Starting download from {remote_name}:{remote_path}...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Download successful!")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr}")    

    cmd_final = ["imx500-package", "-i", "/home/pi/food_scale/downloads/packerOut.zip", "-o", "my_modelrpk"]
    try:
        subprocess.run(cmd_final, check=True)
        print("Command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")

    source_file = "/home/pi/food_scale/downloads/classes.txt"
    destination_folder = "/home/pi/food_scale/my_modelrpk"
    destination_path = os.path.join(destination_folder, "classes.txt")

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    try:
        shutil.move(source_file, destination_path)
        print(f"Successfully moved: {source_file} -> {destination_path}")
    except FileNotFoundError:
        print("Error: The source file does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

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

    print("Database exported successfully in the new format!")

def upload_images():
    cmd = [
        "rclone", 
        "copy", 
        "/home/pi/food_scale/images/", 
        "gdrive:/images_to_train"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Upload successful!")
        print("Output:", result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while uploading: {e}")
        print("Error output:", e.stderr)
    except FileNotFoundError:
        print("Error: rclone is not installed or not found in the system PATH.")

def get_db():
    """Reads the file and returns the current database dictionary."""
    if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
        with open(DB_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def update_db(name, nutrition_data):
    """Reads, updates, and saves the database immediately."""
    db = get_db()
    db[name] = nutrition_data
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

def tare():
    global readings
    print("\nTaring... clearing scale baseline.")
    hx.zero()
    readings.clear()
    print("Tare complete!\n")

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
            current_detected_food = name  # Update global state to display on web
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
                print(f"Food '{name}' not found in database. Add it first!")

if __name__ == '__main__':
    threading.Thread(target=start_ble_thread, daemon=True).start()
    threading.Thread(target=process, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
