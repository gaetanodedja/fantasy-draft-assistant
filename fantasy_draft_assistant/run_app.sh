#!/bin/bash
# Fantasy Draft Assistant - Launch Script for macOS/Linux

cd "$(dirname "$0")"
echo "Launching Fantasy Draft Assistant..."
echo ""

python -m streamlit run app.py
