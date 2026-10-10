@echo off
chcp 65001 > nul
title JARVIS - Shaxsiy O'zbek Yordamchisi

echo ===================================================
echo     JARVIS TIZIMI ISHGA TUSHIRILMOQDA...
echo ===================================================

echo Kerakli kutubxonalar tekshirilmoqda...
pip install -r requirements.txt

echo.
echo Server ishga tushmoqda...
python app.py

pause
