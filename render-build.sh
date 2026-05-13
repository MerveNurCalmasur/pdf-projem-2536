#!/usr/bin/env bash
set -o errexit

# Python paketlerini yükle
pip install -r requirements.txt

# LibreOffice'i kur (Linux sunucu için)
apt-get update && apt-get install -y libreoffice