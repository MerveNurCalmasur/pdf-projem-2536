#!/usr/bin/env bash
# exit on error
set -o errexit

# Python paketlerini kur
pip install -r requirements.txt

# LibreOffice'i sistemden değil, taşınabilir bir yolla kullanacağız veya 
# Render'ın kendi kütüphanelerine güveneceğiz.

# LibreOffice kurulumu (Daha hızlı ve stabil bir repo kullanıyoruz)
mkdir -p /opt/render/project/src/libreoffice
cd /opt/render/project/src/libreoffice

# Eğer daha önce indirilmediyse LibreOffice'i çek
if [ ! -d "libreoffice" ]; then
  curl -L https://github.com/vsls-contrib/libreoffice-bin/raw/master/libreoffice.tar.gz | tar xz
fi