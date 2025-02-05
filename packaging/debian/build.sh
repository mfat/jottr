#!/bin/bash

VERSION=$1
PACKAGE_NAME="jottr"
PACKAGE_VERSION="${VERSION:-1.0.0}"

# Create package structure
mkdir -p ${PACKAGE_NAME}-${PACKAGE_VERSION}
cp -r ../../setup.py ../../jottr ${PACKAGE_NAME}-${PACKAGE_VERSION}/

# Create debian directory
mkdir -p ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian

# Create control file
cat > ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian/control << EOF
Source: jottr
Section: editors
Priority: optional
Maintainer: mFat <newmfat@gmail.com>
Build-Depends: debhelper-compat (= 13), dh-python, python3-all, python3-setuptools

Package: python3-jottr
Architecture: all
Depends: \${python3:Depends}, \${misc:Depends}, python3-pyqt5, python3-pyqt5.qtwebengine
Description: Modern text editor for writers and journalists
 Jottr is a feature-rich text editor designed specifically
 for writers and journalists, with features like smart
 completion, snippets, and integrated web browsing.
EOF

# Create rules file
cat > ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian/rules << EOF
#!/usr/bin/make -f

%:
	dh \$@ --with python3 --buildsystem=pybuild
EOF
chmod +x ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian/rules

# Create changelog
cat > ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian/changelog << EOF
jottr (${PACKAGE_VERSION}) unstable; urgency=medium

  * Initial release.

 -- mFat <newmfat@gmail.com>  $(date -R)
EOF

# Create desktop entry
mkdir -p ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian/jottr.desktop
cat > ${PACKAGE_NAME}-${PACKAGE_VERSION}/debian/jottr.desktop << EOF
[Desktop Entry]
Name=Jottr
Comment=Modern text editor for journalists and writers
Exec=jottr
Icon=jottr
Terminal=false
Type=Application
Categories=Office;TextEditor;
EOF

# Build package
cd ${PACKAGE_NAME}-${PACKAGE_VERSION}
dpkg-buildpackage -us -uc
cd .. 