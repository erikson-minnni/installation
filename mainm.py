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

app = Flask(__name__)

# The HTML for your buttons
app = Flask(__name__)
# Create a queue to communicate between the web server and your main loop
action_queue = queue.Queue()

HTML_PAGE = """
<!DOCTYPE html>
<html>
<body style="text-align:center; padding-top:50px;">
    <button onclick="sendAction('detection')" style="padding:20px; font-size:20px;">Button 1: detection</button>
    <button onclick="sendAction('image')" style="padding:20px; font-size:20px;">Button 2: image</button>
    <button onclick="sendAction('import_to_drive')" style="padding:20px; font-size:20px;">Button 3: import_to_drive</button>
    <button onclick="sendAction('download_model')" style="padding:20px; font-size:20px;">Button 4: download_model</button>
    <button onclick="sendAction('deleate_images')" style="padding:20px; font-size:20px;">Button 5: deleate_images</button>
    <button onclick="sendAction('power_off')" style="padding:20px; font-size:20px;">Button 6: power_off</button>

    <script>
        function sendAction(val) {
            fetch('/trigger/' + val);
        }
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

#opening camera
if os.path.exists(model_path):
    camera = IMX500Detector(model_path)
    camera.start(show_preview=False)
    time.sleep(3)


def process():
    download_database()

 #   gc = gspread.service_account(filename='credentials.json')
  #  sh = gc.open('app_datasheet').worksheet('image_log')

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
            print(f"Processing command: {command_text}")
        time.sleep(0.1)



@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/trigger/<action>')
def trigger(action):
    # Put the button press into the queue
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
                os.unlink(file_path)  # Removes the file
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Removes sub-directories
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")




def update_model():





    folder_path = "/home/pi/food_scale/downloads/"
    """Deletes all files inside the specified folder."""
    if not os.path.exists(folder_path):
      #  print(f"Folder {folder_path_deleate} does not exist.")
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # Removes the file
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Removes sub-directories
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")


    remote_name = "gdrive"
    remote_path = "export_to_pi"
    local_destination = "/home/pi/food_scale/downloads"

    # Ensure the destination directory exists
    if not os.path.exists(local_destination):
        os.makedirs(local_destination)

    # Construct the rclone command
    # rclone copy remote:path local_path
    cmd = ["rclone", "copy", f"{remote_name}:{remote_path}", local_destination]

    try:
        print(f"Starting download from {remote_name}:{remote_path}...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Download successful!")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr}")   


# Configuration
    REMOTE = "gdrive"             # The name you gave in 'rclone config'
    REMOTE_FOLDER = "export_to_pi" # The folder on Google Drive
    LOCAL_PATH = "/home/pi/food_scale/downloads"

# Run the download
#    download_from_gdrive(REMOTE, REMOTE_FOLDER, LOCAL_PATH)


    cmd_final = ["imx500-package", "-i", "/home/pi/food_scale/downloads/packerOut.zip", "-o", "my_modelrpk"]
#final command...:)
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
    # Move the file
        shutil.move(source_file, destination_path)
        print(f"Successfully moved: {source_file} -> {destination_path}")
    except FileNotFoundError:
        print("Error: The source file does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")






def download_database():
    raw_data = database_sheet.get_all_records()

# 4. Transform the data into a nested dictionary
    transformed_data = {}

    for row in raw_data:
        food_name = row['Name']
    
    # Store the rest of the data in a new dictionary
        transformed_data[food_name] = {
            "protein": row['protein'],
            "carbs": row['carbs'],
            "fat": row['fat']
        }

    with open('food_database.json', 'w') as f:
        json.dump(transformed_data, f, indent=4)

    print("Database exported successfully in the new format!")


def upload_images():
    # Define the command as a list of strings
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



# --- Database Helper Functions ---
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


def detection():
    current_db = get_db()
    print("Capturing...")
    camera.capture_and_detect()
    detected_objects = camera.get_detected_names()
    if not detected_objects:
        print("Nothing detected.")
    else:
                    # Refresh to get latest data just in case
        db = get_db()
        for found_name in detected_objects:
            name = found_name.lower().strip()
            if name in db:
                weight = float(input(f"Enter weight in grams for {name}: "))
                multiplier = weight / 100.0
                item = db[name]
                sheet.append_row([
                    name,
                    item['protein'] * multiplier,
                    item['carbs'] * multiplier,
                    item['fat'] * multiplier
                ])
                print(f"Logged {name} to Google Sheets.")
            else:
                print(f"Food '{name}' not found in database. Add it first!")


if __name__ == "__main__":
# Start the process function in a background thread
    threading.Thread(target=process, daemon=True).start()
    
    # Run the web server
   # app.run(host='0.0.0.0', port=5000)
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
