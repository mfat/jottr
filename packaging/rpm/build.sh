#!/bin/bash

VERSION=$1
PACKAGE_NAME="jottr"
PACKAGE_VERSION="${VERSION:-1.0.0}"

# Create RPM build structure
mkdir -p {BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Create source distribution
cd ../..
python -m build --sdist
cd packaging/rpm
cp ../../dist/${PACKAGE_NAME}-${PACKAGE_VERSION}.tar.gz SOURCES/

# Create spec file
cat > SPECS/jottr.spec << EOF
%global __python %{__python3}

Name:           python3-jottr
Version:        ${PACKAGE_VERSION}
Release:        1%{?dist}
Summary:        Modern text editor for writers

License:        MIT
URL:            https://github.com/yourusername/jottr
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-qt5
Requires:       python3-qt5-webengine

%description
Jottr is a feature-rich text editor designed specifically
for writers and journalists, with features like smart
completion, snippets, and integrated web browsing.

%prep
%autosetup -n jottr-%{version}

%build
%py3_build

%install
%py3_install

# Install desktop file
mkdir -p %{buildroot}%{_datadir}/applications/
cat > %{buildroot}%{_datadir}/applications/jottr.desktop << EOL
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
%{python3_sitelib}/jottr/
%{python3_sitelib}/jottr-%{version}*
%{_bindir}/jottr
%{_datadir}/applications/jottr.desktop

%changelog
* $(date '+%a %b %d %Y') Package Builder <builder@example.com> - ${PACKAGE_VERSION}-1
- Initial package release
EOF

# Build RPM
rpmbuild --define "_topdir $(pwd)" -bb SPECS/jottr.spec 