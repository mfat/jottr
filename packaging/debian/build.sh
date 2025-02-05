#!/bin/bash

VERSION=$1
PACKAGE_NAME="jottr"
PACKAGE_VERSION="${VERSION:-1.0.0}"

# Create package structure
mkdir -p ${PACKAGE_NAME}_${PACKAGE_VERSION}/usr/bin
mkdir -p ${PACKAGE_NAME}_${PACKAGE_VERSION}/usr/share/applications
mkdir -p ${PACKAGE_NAME}_${PACKAGE_VERSION}/usr/share/icons/hicolor/256x256/apps

# Copy executable
cp ../../dist/jottr ${PACKAGE_NAME}_${PACKAGE_VERSION}/usr/bin/

# Create desktop entry
cat > ${PACKAGE_NAME}_${PACKAGE_VERSION}/usr/share/applications/jottr.desktop << EOF
[Desktop Entry]
Name=Jottr
Comment=Modern text editor for writers
Exec=jottr
Icon=jottr
Terminal=false
Type=Application
Categories=Office;TextEditor;
EOF

# Create control file
mkdir -p ${PACKAGE_NAME}_${PACKAGE_VERSION}/DEBIAN
cat > ${PACKAGE_NAME}_${PACKAGE_VERSION}/DEBIAN/control << EOF
Package: jottr
Version: ${PACKAGE_VERSION}
Section: editors
Priority: optional
Architecture: amd64
Depends: libc6
Maintainer: Your Name <your.email@example.com>
Description: Modern text editor for writers and journalists
 Jottr is a feature-rich text editor designed specifically
 for writers and journalists, with features like smart
 completion, snippets, and integrated web browsing.
EOF

# Build package
dpkg-deb --build ${PACKAGE_NAME}_${PACKAGE_VERSION} 