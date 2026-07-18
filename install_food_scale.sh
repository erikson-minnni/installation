#!/bin/bash

sudo apt update
sudo apt upgrade

mkdir ~/food_scale
cd ~/food_scale

mkdir /home/pi/food_scale/downloads
mkdir /home/pi/food_scale/images

python3 -m venv --system-site-packages venv
source venv/bin/activate

pip install gspread google-auth flask

sudo apt install python3-opencv
sudo apt install imx500-all



sudo apt-get install -y git build-essential liblgpio-dev

git clone --depth=1 https://github.com/endail/hx711

sudo make install


sudo ldconfig

sudo -v ; curl https://rclone.org/install.sh | sudo bash

wget https://raw.githubusercontent.com/erikson-minnni/installation/main/ai_camera.py
wget https://raw.githubusercontent.com/erikson-minnni/installation/main/mainm.py
wget https://raw.githubusercontent.com/erikson-minnni/installation/main/main.py
