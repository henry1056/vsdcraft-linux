"""
USB device discovery for VSDinside / Mirabox / Ajazz Stream Dock devices.
"""
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger("vsdcraft.discovery")

# Known Vendor & Product IDs for Stream Dock devices
SUPPORTED_DEVICES = [
    # (VID, PID, Model Name, Num Keys, Num Knobs, Num Side Buttons)
    (0x5548, 0x1001, "VSDinside / Mirabox Stream Dock N3", 6, 3, 3),
    (0x5548, 0x1002, "Stream Dock N3 Variant", 6, 3, 3),
    (0x5548, 0x1003, "Stream Dock N3-EN", 6, 3, 3),
    (0x6603, 0x1001, "Stream Dock N3 (Rev B)", 6, 3, 3),
    (0x6603, 0x1002, "Stream Dock N3 (Alt)", 6, 3, 3),
    (0x6603, 0x1003, "FHOOU / Mirabox Stream Dock N3", 6, 3, 3),
    (0x5548, 0x1000, "VSDinside Stream Dock M18 (15-Key)", 15, 0, 0),
    (0x5548, 0x1008, "Stream Dock N4 Pro", 6, 4, 4),
]

def find_streamdocks() -> List[Dict]:
    """
    Search connected USB devices for supported Stream Dock controllers via hidapi.
    Returns a list of device info dictionaries.
    """
    devices = []
    try:
        import hid
    except ImportError:
        logger.warning("hidapi library is not installed. Run 'pip install hidapi'.")
        return devices

    try:
        for dev in hid.enumerate():
            vid = dev.get("vendor_id", 0)
            pid = dev.get("product_id", 0)
            for s_vid, s_pid, name, keys, knobs, side_btns in SUPPORTED_DEVICES:
                if vid == s_vid and pid == s_pid:
                    dev_info = dict(dev)
                    dev_info["model_name"] = name
                    dev_info["key_count"] = keys
                    dev_info["knob_count"] = knobs
                    dev_info["side_button_count"] = side_btns
                    devices.append(dev_info)
                    break
    except Exception as e:
        logger.error(f"Error enumerating HID devices: {e}")

    return devices
