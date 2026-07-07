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

wget https://github.com/erikson-minnni/installation/blob/main/mainm.py
wget https://github.com/erikson-minnni/installation/blob/main/ai_camera.py
