@echo off
REM Fantasy Draft Assistant - Launch Script for Windows
REM This script runs the Streamlit app using the system Python

cd /d "%~dp0"
echo Launching Fantasy Draft Assistant...
echo.

REM Use system Python to avoid Anaconda conflicts
C:\Users\User\AppData\Local\Microsoft\WindowsApps\python3.11.exe -m streamlit run app.py

pause
