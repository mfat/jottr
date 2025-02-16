#!/bin/bash
set -e

# Change to project root directory
cd "$(dirname "$0")/../.."

# Clean up any previous builds or installations
rm -rf build/ dist/ *.egg-info/

# Install build dependencies
sudo apt-get update
sudo apt-get install -y devscripts debhelper python3-all python3-setuptools python3-enchant python3-pyqt5.qtsvg

# Create debian directory link
rm -rf debian
ln -s packaging/debian debian

# Update changelog with current date
sed -i "s/\$(LC_ALL=C date -R)/$(LC_ALL=C date -R)/" debian/changelog

# Build the package
dpkg-buildpackage -us -uc -b

# Clean up the symlink
rm debian

# Show the built package
ls -l ../jottr_*.deb
