#!/bin/bash

# InferNode Setup Script
# This script sets up the development environment for InferNode

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==== InferNode Setup Script ====${NC}\n"

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if Python 3 is installed
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

echo "Found Python $PYTHON_VERSION"

# Check if Python version is >= 3.10 and <= 3.13 (Geti requirement)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    print_error "Python 3.10-3.13 is required for Geti compatibility. Found Python $PYTHON_VERSION"
    exit 1
fi

if [ "$PYTHON_MAJOR" -gt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -gt 13 ]); then
    print_error "Python 3.10-3.13 is required for Geti compatibility. Found Python $PYTHON_VERSION"
    exit 1
fi

print_status "Python version check passed (Python $PYTHON_VERSION is compatible with Geti requirements)"

# Detect OS and install system dependencies
echo -e "\nInstalling system dependencies..."

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        print_status "Detected Debian/Ubuntu system"
        echo "Installing PortAudio development libraries and Python development headers..."
        
        sudo apt-get update -qq
        sudo apt-get install -y portaudio19-dev python3-dev python3-venv gcc make
        
        print_status "System dependencies installed"
        
    elif command -v yum &> /dev/null; then
        # RedHat/CentOS/Fedora
        print_status "Detected RedHat/CentOS/Fedora system"
        echo "Installing PortAudio development libraries and Python development headers..."
        
        sudo yum install -y portaudio-devel python3-devel gcc make
        
        print_status "System dependencies installed"
        
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        print_status "Detected Arch Linux system"
        echo "Installing PortAudio development libraries and Python development headers..."
        
        sudo pacman -S --noconfirm portaudio python
        
        print_status "System dependencies installed"
        
    else
        print_warning "Could not detect package manager. Please install portaudio development libraries manually."
        print_warning "For your system, you need: portaudio headers, python3-dev, gcc, make"
    fi
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    print_status "Detected macOS system"
    
    if command -v brew &> /dev/null; then
        echo "Installing PortAudio via Homebrew..."
        brew install portaudio
        print_status "System dependencies installed"
    else
        print_error "Homebrew not found. Please install Homebrew first: https://brew.sh"
        exit 1
    fi
    
else
    print_warning "Unsupported OS: $OSTYPE"
    print_warning "Please install portaudio development libraries manually."
fi

# Create virtual environment
echo -e "\nCreating virtual environment..."
VENV_DIR=".venv"

if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment already exists at $VENV_DIR"
    read -p "Do you want to remove it and create a new one? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        print_status "Removed existing virtual environment"
    else
        print_status "Using existing virtual environment"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    print_status "Virtual environment created at $VENV_DIR"
fi

# Create .gitignore in .venv to exclude it from git
echo -e "\nCreating .gitignore in virtual environment..."
echo "*" > "$VENV_DIR/.gitignore"
print_status "Created .gitignore in $VENV_DIR (all contents excluded from git)"

# Activate virtual environment
echo -e "\nActivating virtual environment..."
source "$VENV_DIR/bin/activate"
print_status "Virtual environment activated"

# Upgrade pip, setuptools, and wheel
echo -e "\nUpgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel
print_status "pip, setuptools, and wheel upgraded"

# Install requirements
echo -e "\nInstalling Python dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_status "Python dependencies installed successfully"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Install Intel Geti SDK conditionally (only for Python 3.10-3.13)
echo -e "\nInstalling Intel Geti SDK (Python 3.10-3.13 only)..."
if [ "$PYTHON_MINOR" -le 13 ]; then
    if [ -f "requirements-geti.txt" ]; then
        if pip install -r requirements-geti.txt; then
            print_status "Geti SDK installed successfully"
        else
            print_warning "Geti SDK installation failed, continuing without it..."
        fi
    else
        print_warning "requirements-geti.txt not found, skipping Geti SDK installation"
    fi
else
    print_warning "Geti SDK not compatible with Python $PYTHON_VERSION (requires 3.10-3.13)"
fi

# Configure firewall to allow port 8888
echo -e "\nConfiguring firewall to allow port 8888..."

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Check if ufw is available
    if command -v ufw &> /dev/null; then
        print_status "Detected UFW firewall"
        if sudo ufw status | grep -q "Status: active"; then
            if sudo ufw allow 8888/tcp; then
                print_status "Port 8888 allowed through UFW firewall"
            else
                print_warning "Failed to configure UFW firewall"
            fi
        else
            print_warning "UFW is installed but not active, skipping firewall configuration"
        fi
    # Check if firewalld is available
    elif command -v firewall-cmd &> /dev/null; then
        print_status "Detected firewalld"
        if sudo systemctl is-active --quiet firewalld; then
            if sudo firewall-cmd --permanent --add-port=8888/tcp && sudo firewall-cmd --reload; then
                print_status "Port 8888 allowed through firewalld"
            else
                print_warning "Failed to configure firewalld"
            fi
        else
            print_warning "firewalld is installed but not active, skipping firewall configuration"
        fi
    else
        print_warning "No supported firewall detected (UFW or firewalld), skipping firewall configuration"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    print_warning "macOS detected - firewall configuration may require manual setup"
    print_warning "Port 8888 should be accessible by default on macOS"
fi

# Print success message
echo -e "\n${GREEN}==== Setup Complete! ====${NC}\n"
print_status "Virtual environment is ready and activated"
print_status "All dependencies have been installed"

echo -e "\n${YELLOW}To activate the virtual environment in the future, run:${NC}"
echo -e "  source .venv/bin/activate"

echo -e "\n${YELLOW}To start the InferNode application, run:${NC}"
echo -e "  python main.py"

echo -e "\n${YELLOW}NOTE:${NC} If Geti SDK was skipped due to Python version:"
echo -e "  - Install manually: pip install 'geti-sdk>=2.11.0' (requires Python 3.10-3.13)"
echo -e "  - Or use a compatible Python version and re-run setup"

echo -e "\n${YELLOW}To deactivate the virtual environment, run:${NC}"
echo -e "  deactivate"

echo -e "\n${GREEN}Happy coding!${NC}\n"
