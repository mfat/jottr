Name:           python3-jottr
Version:        0.0.0
Release:        1%{?dist}
Summary:        Modern text editor for writers

License:        MIT
URL:            https://github.com/mfat/jottr
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
%autosetup -n %{name}-%{version}

%build
%py3_build

%install
%py3_install

# Create desktop entry
mkdir -p %{buildroot}%{_datadir}/applications/
cat > %{buildroot}%{_datadir}/applications/jottr.desktop << EOF
[Desktop Entry]
Name=Jottr
Comment=Modern text editor for writers
Exec=jottr
Icon=jottr
Terminal=false
Type=Application
Categories=Office;TextEditor;
EOF

%files
%{python3_sitelib}/jottr/
%{python3_sitelib}/jottr-%{version}*
%{_bindir}/jottr
%{_datadir}/applications/jottr.desktop

%changelog
* %(date '+%a %b %d %Y') Package Builder <builder@example.com> - %{version}-%{release}
- Initial package release