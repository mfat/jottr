Name:           jottr
Version:        1.0.0
Release:        1%{?dist}
Summary:        A simple text editor for writers, journalists and researchers

License:        GPLv3
URL:            https://github.com/mfat/jottr
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel

Requires:       python3
Requires:       python3-qt5
Requires:       python3-qt5-webengine
Requires:       python3-feedparser
Requires:       python3-pyspellchecker

%description
Jottr is a simple text editor designed specifically for writers, journalists,
and researchers. It features a clean interface, distraction-free writing mode,
and integrated RSS feed reader.

%prep
%autosetup

%install
# Install application files
mkdir -p %{buildroot}%{_datadir}/%{name}
cp -r src/jottr/* %{buildroot}%{_datadir}/%{name}/

# Create executable script
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} << EOF
#!/bin/bash
exec python3 %{_datadir}/%{name}/main.py
EOF
chmod 755 %{buildroot}%{_bindir}/%{name}

# Create desktop entry
mkdir -p %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/%{name}.desktop << EOF
[Desktop Entry]
Name=Jottr
Comment=Text editor for writers
Exec=jottr
Icon=%{name}
Terminal=false
Type=Application
Categories=Utility;TextEditor;
EOF

# Add icons
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/
install -p -m 644 icons/jottr.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

%files
%license LICENSE
%doc README.md
%{_datadir}/%{name}
%{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

%changelog
* Wed Mar 20 2024 mFat <mfat@github.com> - 1.0.0-1
- Initial RPM release 