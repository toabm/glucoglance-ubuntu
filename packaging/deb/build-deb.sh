#!/usr/bin/env bash
# Builds an installable .deb for Ubuntu from an already-built wheel:
#
#     packaging/deb/build-deb.sh dist/glucoglance-X.Y.Z-py3-none-any.whl [OUT_DIR]
#
# Why from the wheel, rather than a normal debian/ + dh-python source build:
# pyproject.toml needs setuptools >= 77 (PEP 639 `license = "MIT"`), but
# Ubuntu 24.04 ships setuptools 68, so the Debian toolchain can't build this
# project from source there. The wheel is pure Python (py3-none-any), so
# unpacking it into dist-packages gives exactly what a pip install would -
# including the .dist-info metadata the About dialog reads its version from.
# It also means the version comes from the wheel, i.e. from pyproject.toml,
# so there's no second version number (like debian/changelog) to bump.
#
# Runtime dependencies are declared as apt packages, so `sudo apt install
# ./glucoglance_X.Y.Z_all.deb` pulls in GTK/AppIndicator bindings itself.

set -euo pipefail

wheel=${1:?usage: $0 path/to/glucoglance-X.Y.Z-py3-none-any.whl [OUT_DIR]}
out_dir=${2:-dist}
here=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$here/../.." && pwd)

# glucoglance-0.3.2-py3-none-any.whl -> 0.3.2
version=$(basename "$wheel" | cut -d- -f2)
package=glucoglance

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

# Python package + its .dist-info, where Ubuntu's python3 looks for
# apt-installed modules regardless of the exact 3.x version.
site_packages="$stage/usr/lib/python3/dist-packages"
mkdir -p "$site_packages"
python3 -m zipfile -e "$wheel" "$site_packages"
echo dpkg > "$site_packages/$package-$version.dist-info/INSTALLER"

# Console script (the wheel only records it as an entry point; pip would
# normally generate this file). Mirrors [project.scripts] in pyproject.toml.
install -d "$stage/usr/bin"
cat > "$stage/usr/bin/glucoglance" <<'EOF'
#!/usr/bin/python3
import sys

from glucoglance.main import main

sys.exit(main())
EOF
chmod 755 "$stage/usr/bin/glucoglance"

# Applications-menu entry + icon, so it shows up in GNOME's app search.
install -Dm644 "$here/glucoglance.desktop" "$stage/usr/share/applications/glucoglance.desktop"
install -Dm644 "$repo_root/src/glucoglance/assets/icon.png" "$stage/usr/share/icons/hicolor/256x256/apps/glucoglance.png"
install -Dm644 "$repo_root/LICENSE" "$stage/usr/share/doc/$package/copyright"

install -d "$stage/DEBIAN"
installed_size=$(du -sk --exclude=DEBIAN "$stage" | cut -f1)
cat > "$stage/DEBIAN/control" <<EOF
Package: $package
Version: $version
Architecture: all
Maintainer: Angel Blanco <toabm@yahoo.es>
Installed-Size: $installed_size
Depends: python3 (>= 3.11), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1, python3-requests, python3-keyring (>= 24), python3-tomli-w
Recommends: gnome-shell-extension-appindicator
Section: utils
Priority: optional
Homepage: https://github.com/toabm/glucoglance-ubuntu
Description: Tray widget showing live FreeStyle Libre glucose readings
 Shows the current glucose reading and trend arrow from a FreeStyle Libre
 sensor, via a LibreLinkUp follower account, in the Ubuntu top bar.
 .
 Not a medical device and not affiliated with Abbott. Do not use it to
 make treatment decisions.
EOF

# Byte-compile on install and clean up on removal, as dh_python3 would.
cat > "$stage/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e
if [ "\$1" = configure ] && command -v py3compile >/dev/null 2>&1; then
    py3compile -p $package
fi
EOF
cat > "$stage/DEBIAN/prerm" <<EOF
#!/bin/sh
set -e
if command -v py3clean >/dev/null 2>&1; then
    py3clean -p $package
fi
EOF
chmod 755 "$stage/DEBIAN/postinst" "$stage/DEBIAN/prerm"

mkdir -p "$out_dir"
dpkg-deb --root-owner-group --build "$stage" "$out_dir/${package}_${version}_all.deb"
