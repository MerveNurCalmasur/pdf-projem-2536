#!/usr/bin/env bash
# exit on error
set -o errexit

# Python paketlerini kur
pip install -r requirements.txt

# LibreOffice'i sistemden değil, taşınabilir bir yolla kullanacağız veya 
# Render'ın kendi kütüphanelerine güveneceğiz.