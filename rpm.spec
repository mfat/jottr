Name:           jottr
# x-release-please-start-version
Version:        2.2.1
# x-release-please-end
Release:        1%{?dist}
Summary:        A simple text editor for writers, journalists and researchers

License:        GPLv3
URL:            https://github.com/mfat/jottr
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  qt6-qtbase-devel
BuildRequires:  patchelf

Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-pyqt6-webengine
Requires:       python3-feedparser
Requires:       python3-enchant
Requires:       python3-pyqt6-sip
Requires:       qt6-qtsvg
Requires:       python3-pyxdg

%description
Jottr is a simple text editor designed specifically for writers, journalists,
and researchers.

%prep
%autosetup

%build
# Bundle Adwaita-Qt style plugin (no runtime dependency on adwaita-qt6).
%{__bash} scripts/build-adwaita-qt.sh

%install
# Install the importable package (includes qt_plugins/)
mkdir -p %{buildroot}%{python3_sitelib}
cp -a src/jottr %{buildroot}%{python3_sitelib}/jottr
rm -f %{buildroot}%{python3_sitelib}/jottr/jottr-mac.spec \
      %{buildroot}%{python3_sitelib}/jottr/jottr-windows.spec \
      %{buildroot}%{python3_sitelib}/jottr/jottr_icon.icns
find %{buildroot}%{python3_sitelib}/jottr -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Shared data looked up via jottr.paths
mkdir -p %{buildroot}%{_datadir}/%{name}
cp -a icons %{buildroot}%{_datadir}/%{name}/icons
cp -a translations %{buildroot}%{_datadir}/%{name}/translations

# Launcher
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} << 'EOF'
#!/bin/bash
args=()
for arg in "$@"; do
    if [ -f "$arg" ]; then
        args+=("$(readlink -f "$arg")")
    else
        args+=("$arg")
    fi
done
exec python3 -m jottr "${args[@]}"
EOF
chmod 755 %{buildroot}%{_bindir}/%{name}

# Desktop entry
mkdir -p %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/%{name}.desktop << EOF
[Desktop Entry]
Name=Jottr
Comment=Text editor for writers
Exec=jottr %F
Icon=jottr
Terminal=false
Type=Application
Categories=Utility;TextEditor;
MimeType=text/plain;text/markdown;text/x-markdown;
StartupNotify=true
EOF

# App icon
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/
install -p -m 644 icons/jottr.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/jottr
%{_datadir}/%{name}
%{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/256x256/apps/%{name}.png

%changelog
* Sat Mar 01 2025 mFat <newmfat@gmail.com> - 1.4.3-1
- Bug fixes and improvements
