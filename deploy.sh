#!/bin/bash

cd /home/ubuntu/syncnox-be

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Restarting FastAPI service..."
sudo systemctl restart syncnox
