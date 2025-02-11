#!/bin/bash
set -e

# Change to project root directory
cd "$(dirname "$0")/../.."

# Install build dependencies
sudo apt-get update
sudo apt-get install -y devscripts debhelper python3-all python3-setuptools

# Build the package
dpkg-buildpackage -us -uc -b

# Show the built package
ls -l ../jottr_*.deb
