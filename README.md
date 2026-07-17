wget https://raw.githubusercontent.com/erikson-minnni/installation/refs/heads/main/install_food_scale.sh

chmod +x install_food_scale.sh

./install_food_scale.sh


......................
then your gonna hve to enable the google drive and google sheets API
download the json file and rename it to credentials.json

connect to rclone by downloading rclone on windows, pasting the rclone.exe in the command prompt window and typing:

"C:\Path\To\Your\Folder\rclone.exe" authorize "drive"  "eyJzY29wZSI6ImRyaXZlIn0"


than run:

rclone config
