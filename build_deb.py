#!/usr/bin/env python3
"""
Debian Package (.deb) Builder for VSDCraft Linux.
Creates a fully compliant Debian/Ubuntu .deb archive without requiring dpkg-deb.
"""

import os
import io
import time
import tarfile
import gzip
import shutil

PACKAGE_NAME = "vsdcraft"
VERSION = "1.0.0"
ARCH = "all"
OUTPUT_DEB = f"{PACKAGE_NAME}_{VERSION}_{ARCH}.deb"

SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))

def create_tar_gz_bytes(entries):
    """
    Creates tar.gz bytes from a list of dicts:
    [{'name': path_in_tar, 'content': bytes, 'mode': int, 'type': tarfile.REGTYPE or DIRTYPE}]
    """
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        for entry in entries:
            ti = tarfile.TarInfo(name=entry['name'])
            ti.mtime = entry.get('mtime', int(time.time()))
            ti.uid = 0
            ti.gid = 0
            ti.uname = "root"
            ti.gname = "root"
            ti.mode = entry.get('mode', 0o644)
            ti.type = entry.get('type', tarfile.REGTYPE)
            
            content = entry.get('content', b"")
            ti.size = len(content)
            
            if ti.isdir():
                tar.addfile(ti)
            else:
                tar.addfile(ti, io.BytesIO(content))
                
    return tar_buf.getvalue()

def make_ar_header(name: str, size: int, mtime: int = None, mode: int = 0o100644) -> bytes:
    """Creates a 60-byte Unix ar archive header."""
    if mtime is None:
        mtime = int(time.time())
    name_field = (name.ljust(16))[:16].encode('ascii')
    mtime_field = str(mtime).ljust(12)[:12].encode('ascii')
    uid_field = b'0'.ljust(6)
    gid_field = b'0'.ljust(6)
    mode_field = oct(mode)[2:].rjust(6, '0').ljust(8)[:8].encode('ascii')
    size_field = str(size).ljust(10)[:10].encode('ascii')
    trailer = b'\x60\n'
    hdr = name_field + mtime_field + uid_field + gid_field + mode_field + size_field + trailer
    assert len(hdr) == 60
    return hdr

def build_deb(output_path: str = OUTPUT_DEB):
    print(f"[*] Building Debian package: {output_path}...")

    # 1. debian-binary
    debian_binary = b"2.0\n"

    # 2. Control files
    control_content = f"""Package: {PACKAGE_NAME}
Version: {VERSION}
Section: utils
Priority: optional
Architecture: {ARCH}
Depends: python3 (>= 3.10), python3-pip, python3-pil, python3-tk, libhidapi-hidraw0
Recommends: playerctl, xdotool
Maintainer: henry1056 <henry1056@users.noreply.github.com>
Homepage: https://github.com/henry1056/vsdcraft-linux
Description: Controller and VSD Craft alternative for VSDinside Stream Dock N3
 VSDCraft Linux is an open-source graphical macro pad controller designed
 specifically for the VSDinside Stream Dock N3, Mirabox Stream Dock N3,
 and Ajazz AKP03 controllers on Linux desktops.
 Features include LCD key rendering, rotary knob support, PipeWire / PulseAudio
 volume control, MPRIS media player control, application launchers, hotkey macros,
 and native StreamDock plugin compatibility.
""".encode("utf-8")

    postinst_content = b"""#!/bin/sh
set -e

# Reload udev rules
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger || true
fi

# Ensure python dependencies are installed
python3 -m pip install --quiet --upgrade customtkinter websockets psutil hidapi >/dev/null 2>&1 || true

# Update desktop menu database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

exit 0
"""

    postrm_content = b"""#!/bin/sh
set -e

if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

exit 0
"""

    control_entries = [
        {'name': './control', 'content': control_content, 'mode': 0o644},
        {'name': './postinst', 'content': postinst_content, 'mode': 0o755},
        {'name': './postrm', 'content': postrm_content, 'mode': 0o755},
    ]
    control_tar_gz = create_tar_gz_bytes(control_entries)

    # 3. Data files (Filesystem payload)
    data_entries = []

    # Directories
    dirs = [
        './usr',
        './usr/bin',
        './usr/lib',
        './usr/lib/python3',
        './usr/lib/python3/dist-packages',
        './usr/lib/python3/dist-packages/vsdcraft',
        './usr/share',
        './usr/share/applications',
        './usr/share/icons',
        './usr/share/icons/hicolor',
        './usr/share/icons/hicolor/scalable',
        './usr/share/icons/hicolor/scalable/apps',
        './lib',
        './lib/udev',
        './lib/udev/rules.d',
        './usr/lib/systemd',
        './usr/lib/systemd/user'
    ]
    for d in dirs:
        data_entries.append({'name': d, 'type': tarfile.DIRTYPE, 'mode': 0o755})

    # Executable binary in /usr/bin/vsdcraft
    launcher_script = b"""#!/usr/bin/env python3
import sys
from vsdcraft.__main__ import main
if __name__ == '__main__':
    main()
"""
    data_entries.append({'name': './usr/bin/vsdcraft', 'content': launcher_script, 'mode': 0o755})

    # Package code files into /usr/lib/python3/dist-packages/vsdcraft/
    pkg_root = os.path.join(SOURCE_ROOT, "vsdcraft")
    for dirpath, dirnames, filenames in os.walk(pkg_root):
        if "__pycache__" in dirpath:
            continue
        rel_dir = os.path.relpath(dirpath, pkg_root).replace('\\', '/')
        tar_dir = './usr/lib/python3/dist-packages/vsdcraft'
        if rel_dir != '.':
            tar_dir += '/' + rel_dir
            data_entries.append({'name': tar_dir, 'type': tarfile.DIRTYPE, 'mode': 0o755})

        for f in filenames:
            if f.endswith('.pyc') or f.endswith('.pyo'):
                continue
            full_path = os.path.join(dirpath, f)
            with open(full_path, 'rb') as fp:
                file_content = fp.read()
            tar_file = tar_dir + '/' + f
            data_entries.append({'name': tar_file, 'content': file_content, 'mode': 0o644})

    # Udev rule in /lib/udev/rules.d/99-streamdock.rules
    udev_src = os.path.join(SOURCE_ROOT, "99-streamdock.rules")
    if os.path.exists(udev_src):
        with open(udev_src, 'rb') as fp:
            data_entries.append({'name': './lib/udev/rules.d/99-streamdock.rules', 'content': fp.read(), 'mode': 0o644})

    # Desktop entry in /usr/share/applications/vsdcraft.desktop
    desktop_src = os.path.join(SOURCE_ROOT, "vsdcraft.desktop")
    if os.path.exists(desktop_src):
        with open(desktop_src, 'rb') as fp:
            data_entries.append({'name': './usr/share/applications/vsdcraft.desktop', 'content': fp.read(), 'mode': 0o644})

    # Systemd service in /usr/lib/systemd/user/vsdcraft.service
    service_src = os.path.join(SOURCE_ROOT, "vsdcraft.service")
    if os.path.exists(service_src):
        with open(service_src, 'rb') as fp:
            data_entries.append({'name': './usr/lib/systemd/user/vsdcraft.service', 'content': fp.read(), 'mode': 0o644})

    # Vector Icon in /usr/share/icons/hicolor/scalable/apps/vsdcraft.svg
    icon_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <rect width="128" height="128" rx="24" fill="#18181b"/>
  <rect x="8" y="8" width="112" height="112" rx="18" fill="#27272a" stroke="#3b82f6" stroke-width="4"/>
  <circle cx="36" cy="36" r="16" fill="#38bdf8"/>
  <circle cx="92" cy="36" r="16" fill="#10b981"/>
  <circle cx="36" cy="92" r="16" fill="#f59e0b"/>
  <circle cx="92" cy="92" r="16" fill="#ec4899"/>
  <polygon points="64,24 74,54 54,64 74,64 48,104 58,74 78,74" fill="#ffffff"/>
</svg>"""
    data_entries.append({'name': './usr/share/icons/hicolor/scalable/apps/vsdcraft.svg', 'content': icon_svg, 'mode': 0o644})

    data_tar_gz = create_tar_gz_bytes(data_entries)

    # 4. Assemble the .deb (Unix ar archive)
    ar_magic = b"!<arch>\n"
    
    with open(output_path, "wb") as out:
        out.write(ar_magic)
        
        # 1. debian-binary
        out.write(make_ar_header("debian-binary", len(debian_binary)))
        out.write(debian_binary)
        if len(debian_binary) % 2 != 0:
            out.write(b"\n")
            
        # 2. control.tar.gz
        out.write(make_ar_header("control.tar.gz", len(control_tar_gz)))
        out.write(control_tar_gz)
        if len(control_tar_gz) % 2 != 0:
            out.write(b"\n")
            
        # 3. data.tar.gz
        out.write(make_ar_header("data.tar.gz", len(data_tar_gz)))
        out.write(data_tar_gz)
        if len(data_tar_gz) % 2 != 0:
            out.write(b"\n")

    size_kb = os.path.getsize(output_path) / 1024
    print(f"[+] Successfully built {output_path} ({size_kb:.1f} KB)")

if __name__ == "__main__":
    build_deb()
