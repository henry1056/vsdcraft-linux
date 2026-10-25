"""
Configuration management for VSDCraft Linux.
Manages profiles, pages, key bindings, and knob assignments.
"""

import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("vsdcraft.config")

CONFIG_DIR = os.path.expanduser("~/.config/vsdcraft")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def get_default_config() -> Dict[str, Any]:
    return {
        "active_profile": "Default",
        "brightness": 80,
        "profiles": {
            "Default": {
                "active_page_index": 0,
                "pages": [
                    {
                        "name": "Main",
                        "keys": [
                            # Row 1 (Keys 0, 1, 2)
                            {
                                "id": 0,
                                "type": "spicetify_playpause",
                                "title": "Play/Pause",
                                "icon": "spotify_play",
                                "settings": {}
                            },
                            {
                                "id": 1,
                                "type": "mpris_next",
                                "title": "Next Track",
                                "icon": "skip_next",
                                "settings": {}
                            },
                            {
                                "id": 2,
                                "type": "system_stats",
                                "title": "CPU / RAM",
                                "icon": "cpu",
                                "settings": {"metric": "both"}
                            },
                            # Row 2 (Keys 3, 4, 5)
                            {
                                "id": 3,
                                "type": "app_launcher",
                                "title": "Terminal",
                                "icon": "terminal",
                                "settings": {"command": "x-terminal-emulator || gnome-terminal || alacritty || kitty || xterm"}
                            },
                            {
                                "id": 4,
                                "type": "app_launcher",
                                "title": "Browser",
                                "icon": "web",
                                "settings": {"command": "xdg-open https://google.com"}
                            },
                            {
                                "id": 5,
                                "type": "system_mute",
                                "title": "Mute Audio",
                                "icon": "volume_mute",
                                "settings": {}
                            }
                        ],
                        "knobs": [
                            # Knob 0: Master Volume
                            {
                                "id": 0,
                                "title": "Master Volume",
                                "turn_type": "system_volume",
                                "click_type": "system_mute",
                                "settings": {"step": 5}
                            },
                            # Knob 1: Spotify / Spicetify Volume
                            {
                                "id": 1,
                                "title": "Spotify Volume",
                                "turn_type": "spicetify_volume",
                                "click_type": "spicetify_playpause",
                                "settings": {"step": 0.05}
                            },
                            # Knob 2: Screen Brightness or Media Scroll
                            {
                                "id": 2,
                                "title": "Brightness",
                                "turn_type": "deck_brightness",
                                "click_type": "deck_toggle_screen",
                                "settings": {"step": 10}
                            }
                        ],
                        "side_buttons": [
                            {"id": 0, "type": "page_prev", "title": "Prev Page"},
                            {"id": 1, "type": "page_next", "title": "Next Page"},
                            {"id": 2, "type": "page_home", "title": "Home Page"}
                        ]
                    }
                ]
            }
        }
    }

class ConfigManager:
    def __init__(self, path: str = CONFIG_FILE):
        self.path = path
        self.data: Dict[str, Any] = get_default_config()
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                logger.info(f"Loaded configuration from {self.path}")
                return
            except Exception as e:
                logger.error(f"Failed to load config from {self.path}: {e}. Creating new defaults.")
        
        self.data = get_default_config()
        self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            logger.info("Saved configuration successfully.")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def get_current_page(self) -> Dict[str, Any]:
        profile_name = self.data.get("active_profile", "Default")
        profile = self.data.get("profiles", {}).get(profile_name)
        if not profile:
            profile = get_default_config()["profiles"]["Default"]
            self.data.setdefault("profiles", {})[profile_name] = profile

        page_idx = profile.get("active_page_index", 0)
        pages = profile.get("pages", [])
        if not pages:
            pages = get_default_config()["profiles"]["Default"]["pages"]
            profile["pages"] = pages

        if page_idx < 0 or page_idx >= len(pages):
            page_idx = 0
            profile["active_page_index"] = 0

        return pages[page_idx]

    def set_key_action(self, key_id: int, action_type: str, title: str = "", icon: str = "", settings: Dict = None):
        page = self.get_current_page()
        keys = page.setdefault("keys", [])
        while len(keys) <= key_id:
            keys.append({"id": len(keys), "type": "none", "title": "", "icon": "", "settings": {}})
        
        keys[key_id] = {
            "id": key_id,
            "type": action_type,
            "title": title,
            "icon": icon,
            "settings": settings or {}
        }
        self.save()

    def set_knob_action(self, knob_id: int, turn_type: str, click_type: str = "none", title: str = "", settings: Dict = None):
        page = self.get_current_page()
        knobs = page.setdefault("knobs", [])
        while len(knobs) <= knob_id:
            knobs.append({"id": len(knobs), "title": f"Knob {len(knobs)+1}", "turn_type": "none", "click_type": "none", "settings": {}})
        
        knobs[knob_id] = {
            "id": knob_id,
            "title": title or knobs[knob_id].get("title", f"Knob {knob_id+1}"),
            "turn_type": turn_type,
            "click_type": click_type,
            "settings": settings or {}
        }
        self.save()
