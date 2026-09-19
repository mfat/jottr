Name:           jottr
# x-release-please-start-version
Version:        2.7.3
# x-release-please-end
Release:        1%{?dist}
Summary:        A simple text editor for writers, journalists and researchers

License:        GPL-3.0-or-later
URL:            https://github.com/mfat/jottr
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel

Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-pyqt6-webengine
Requires:       python3-feedparser
Requires:       python3-enchant
Requires:       python3-pyqt6-sip
Requires:       qt6-qtsvg
Requires:       python3-pyxdg
Requires:       python3-requests
Recommends:     python3-markdown
Recommends:     python3-langdetect
Recommends:     python3-pyspellchecker

%description
Jottr is a simple text editor designed specifically for writers, journalists,
and researchers.

%prep
%autosetup

%build
# Pure Python package; nothing to compile.

%install
# Install the importable package
mkdir -p %{buildroot}%{python3_sitelib}
cp -a src/jottr %{buildroot}%{python3_sitelib}/jottr
rm -f %{buildroot}%{python3_sitelib}/jottr/jottr_icon.icns
rm -f %{buildroot}%{python3_sitelib}/jottr/jottr_icon.ico
find %{buildroot}%{python3_sitelib}/jottr -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Shared data looked up via jottr.paths
mkdir -p %{buildroot}%{_datadir}/%{name}
cp -a icons %{buildroot}%{_datadir}/%{name}/icons
cp -a translations %{buildroot}%{_datadir}/%{name}/translations

# Launcher
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} << 'EOF'
#!/bin/sh
exec %{python3} -m jottr "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/%{name}

# Desktop entry basename must match QGuiApplication.setDesktopFileName
install -p -D -m 644 io.github.mfat.jottr.desktop %{buildroot}%{_datadir}/applications/io.github.mfat.jottr.desktop

# App icon (Freedesktop scalable SVG; basename matches Icon=)
install -p -D -m 644 icons/jottr.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.mfat.jottr.svg
install -p -D -m 644 icons/jottr-symbolic.svg %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps/io.github.mfat.jottr-symbolic.svg

# AppStream metadata for software centers
install -p -D -m 644 io.github.mfat.jottr.metainfo.xml %{buildroot}%{_metainfodir}/io.github.mfat.jottr.metainfo.xml

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/jottr
%{_datadir}/%{name}
%{_bindir}/%{name}
%{_datadir}/applications/io.github.mfat.jottr.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.mfat.jottr.svg
%{_datadir}/icons/hicolor/symbolic/apps/io.github.mfat.jottr-symbolic.svg
%{_metainfodir}/io.github.mfat.jottr.metainfo.xml

%changelog
* Sat Mar 01 2025 mFat <newmfat@gmail.com> - 1.4.3-1
- Bug fixes and improvements
