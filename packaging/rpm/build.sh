#!/bin/bash

VERSION=$1
PACKAGE_NAME="jottr"
PACKAGE_VERSION="${VERSION:-1.0.0}"

# Create RPM build structure
mkdir -p {BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Create spec file
cat > SPECS/jottr.spec << EOF
Name:           jottr
Version:        ${PACKAGE_VERSION}
Release:        1%{?dist}
Summary:        Modern text editor for writers

License:        MIT
URL:            https://github.com/mfat/jottr
BuildArch:      x86_64

%description
Jottr is a feature-rich text editor designed specifically
for writers and journalists, with features like smart
completion, snippets, and integrated web browsing.

%prep
# Nothing to prepare

%build
# Nothing to build

%install
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps

# Copy executable
cp ../../dist/jottr %{buildroot}/usr/bin/

# Create desktop entry
cat > %{buildroot}/usr/share/applications/jottr.desktop << EOL
[Desktop Entry]
Name=Jottr
Comment=Modern text editor for writers
Exec=jottr
Icon=jottr
Terminal=false
Type=Application
Categories=Office;TextEditor;
EOL

%files
/usr/bin/jottr
/usr/share/applications/jottr.desktop

%changelog
* $(date '+%a %b %d %Y') Package Builder <builder@example.com> - ${PACKAGE_VERSION}-1
- Initial package release
EOF

# Build RPM
rpmbuild --define "_topdir $(pwd)" -bb SPECS/jottr.spec 