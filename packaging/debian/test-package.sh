#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "Testing Jottr package..."

# Find the latest built package
DEB_PACKAGE=$(ls -t deb_dist/python3-jottr*.deb | head -n1)
if [ ! -f "$DEB_PACKAGE" ]; then
    echo -e "${RED}Error: No .deb package found in deb_dist/${NC}"
    exit 1
fi

# Install the package
echo "Installing package: $DEB_PACKAGE"
sudo dpkg -i "$DEB_PACKAGE" || sudo apt-get install -f -y

# Check if binary is installed
if ! which jottr > /dev/null; then
    echo -e "${RED}Error: jottr binary not found in PATH${NC}"
    exit 1
fi

# Check if desktop file is installed
if [ ! -f "/usr/share/applications/jottr.desktop" ]; then
    echo -e "${RED}Error: Desktop file not installed${NC}"
    exit 1
fi

# Check if icon is installed
if [ ! -f "/usr/share/icons/hicolor/128x128/apps/jottr.png" ]; then
    echo -e "${RED}Error: Application icon not installed${NC}"
    exit 1
fi

# Try to import the module
if ! python3 -c "import jottr" 2>/dev/null; then
    echo -e "${RED}Error: Cannot import jottr module${NC}"
    exit 1
fi

echo -e "${GREEN}All tests passed successfully!${NC}"

# Optional: Remove the package
read -p "Do you want to remove the test package? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo apt-get remove -y python3-jottr
fi
