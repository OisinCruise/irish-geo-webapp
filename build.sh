#!/usr/bin/env bash
# Render Build Script for Irish Historical Sites GIS
# This script runs during the build phase on Render

set -o errexit  # Exit on error

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Build complete ==="
