#!/bin/bash

echo "================================================"
echo "Altcoin Trading Bot - Setup Script"
echo "================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check PostgreSQL
echo ""
echo "Checking PostgreSQL..."
if command -v psql &> /dev/null; then
    echo "PostgreSQL is installed"
else
    echo "WARNING: PostgreSQL not found. Please install PostgreSQL 12+"
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
echo ""
echo "Creating logs directory..."
mkdir -p logs

# Copy environment file
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your database credentials"
else
    echo ".env file already exists, skipping..."
fi

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your database credentials"
echo "2. Create PostgreSQL database:"
echo "   CREATE DATABASE trading_bot;"
echo "   CREATE USER trading_bot_user WITH PASSWORD 'your_password';"
echo "   GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading_bot_user;"
echo ""
echo "3. Update config/config.yaml if needed"
echo ""
echo "4. Run the bot:"
echo "   python src/main.py"
echo ""
echo "5. Run the dashboard (in a separate terminal):"
echo "   python src/gui/app.py"
echo ""
echo "================================================"
