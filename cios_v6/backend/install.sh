#!/bin/bash
# ─────────────────────────────────────────────────────────
#  CIOS Backend — Mac/Linux Install Script
# ─────────────────────────────────────────────────────────
set -e

echo ""
echo " ======================================"
echo "  CIOS Backend — Installing..."
echo " ======================================"
echo ""

# Upgrade pip first
echo "[1/4] Upgrading pip..."
python3 -m pip install --upgrade pip --quiet

# Create venv
echo "[2/4] Creating virtual environment..."
python3 -m venv venv

# Activate
echo "[3/4] Activating..."
source venv/bin/activate

# Install
echo "[4/4] Installing packages..."
pip install -r requirements.txt --quiet

cp .env.example .env 2>/dev/null || true

echo ""
echo " ======================================"
echo "  Done! Now run:"
echo "  source venv/bin/activate"
echo "  python -m uvicorn app.main:app --reload --port 8000"
echo " ======================================"
