#!/bin/bash

sudo apt update
sudo apt upgrade

mkdir ~/food_scale
cd ~/food_scale


mkdir ~/downloads
mkdir ~/images

python3 -m venv --system-site-packages venv
source venv/bin/activate

pip install gspread google-auth flask

sudo apt install python3-opencv

wget https://raw.githubusercontent.com/erikson-minnni/installation/main/ai_camera.py
wget https://raw.githubusercontent.com/erikson-minnni/installation/main/mainm.py
