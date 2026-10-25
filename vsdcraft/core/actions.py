"""
Execution engine for VSDCraft Linux actions.
Handles audio, media, desktop commands, hotkeys, Spicetify, and system monitoring.
"""

import os
import shutil
import subprocess
import urllib.request
import urllib.parse
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("vsdcraft.actions")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class ActionRunner:
    def __init__(self, config_manager=None, device=None):
        self.config_manager = config_manager
        self.device = device
        self._detect_audio_backend()

    def _detect_audio_backend(self):
        """Detect available Linux audio CLI tool: wpctl (PipeWire), pactl (PulseAudio), or amixer (ALSA)."""
        if shutil.which("wpctl"):
            self.audio_backend = "wpctl"
        elif shutil.which("pactl"):
            self.audio_backend = "pactl"
        elif shutil.which("amixer"):
            self.audio_backend = "amixer"
        else:
            self.audio_backend = "none"
        logger.info(f"Detected Linux audio backend: {self.audio_backend}")

    # =========================================================================
    # Audio Volume & Mute
    # =========================================================================
    def change_volume(self, delta_percent: int):
        """Change system master volume up or down by percentage."""
        try:
            if self.audio_backend == "wpctl":
                # wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+ or 5%-
                sign = "+" if delta_percent > 0 else "-"
                val = f"{abs(delta_percent)}%{sign}"
                subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", val, "--limit", "1.5"], check=False)
            elif self.audio_backend == "pactl":
                sign = "+" if delta_percent > 0 else "-"
                val = f"{sign}{abs(delta_percent)}%"
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", val], check=False)
            elif self.audio_backend == "amixer":
                sign = "+" if delta_percent > 0 else "-"
                val = f"{abs(delta_percent)}%{sign}"
                subprocess.run(["amixer", "sset", "Master", val], check=False)
        except Exception as e:
            logger.error(f"Error changing volume: {e}")

    def toggle_mute(self):
        """Toggle system audio mute."""
        try:
            if self.audio_backend == "wpctl":
                subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], check=False)
            elif self.audio_backend == "pactl":
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=False)
            elif self.audio_backend == "amixer":
                subprocess.run(["amixer", "sset", "Master", "toggle"], check=False)
        except Exception as e:
            logger.error(f"Error toggling mute: {e}")

    # =========================================================================
    # Media MPRIS & Playerctl
    # =========================================================================
    def media_play_pause(self):
        self._run_playerctl("play-pause")

    def media_next(self):
        self._run_playerctl("next")

    def media_previous(self):
        self._run_playerctl("previous")

    def _run_playerctl(self, command: str):
        if shutil.which("playerctl"):
            try:
                subprocess.run(["playerctl", command], check=False)
            except Exception as e:
                logger.error(f"playerctl {command} error: {e}")
        else:
            # Fallback to Spicetify local HTTP endpoint if available
            self.spicetify_command(command.replace("-", ""))

    # =========================================================================
    # Spicetify Bridge Integration (Port 8974)
    # =========================================================================
    def spicetify_command(self, endpoint: str, params: Optional[Dict] = None) -> bool:
        """Send command to Spicetify StreamDock Bridge HTTP server."""
        base_url = "http://127.0.0.1:8974"
        url = f"{base_url}/{endpoint.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def spicetify_volume(self, delta: float):
        self.spicetify_command("volume", {"delta": str(delta)})

    # =========================================================================
    # App Launcher & Custom Shell Script
    # =========================================================================
    def launch_command(self, cmd: str):
        """Launch shell command asynchronously without blocking."""
        if not cmd.strip():
            return
        try:
            logger.info(f"Executing command: {cmd}")
            subprocess.Popen(cmd, shell=True, start_new_session=True)
        except Exception as e:
            logger.error(f"Failed to execute command '{cmd}': {e}")

    def open_url(self, url: str):
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", url], start_new_session=True)
            else:
                import webbrowser
                webbrowser.open(url)
        except Exception as e:
            logger.error(f"Failed to open URL '{url}': {e}")

    # =========================================================================
    # Keyboard Macros & Hotkeys
    # =========================================================================
    def send_hotkey(self, combo: str):
        """Send key combination via xdotool (X11) or ydotool/wtype (Wayland)."""
        if not combo:
            return
        try:
            if shutil.which("xdotool"):
                subprocess.run(["xdotool", "key", combo], check=False)
            elif shutil.which("ydotool"):
                subprocess.run(["ydotool", "key", combo], check=False)
            elif shutil.which("wtype"):
                subprocess.run(["wtype", "-k", combo], check=False)
            else:
                logger.warning("No virtual keyboard utility (xdotool, ydotool, or wtype) found.")
        except Exception as e:
            logger.error(f"Hotkey dispatch error: {e}")

    # =========================================================================
    # System Stats
    # =========================================================================
    def get_system_stats(self) -> Dict[str, Any]:
        """Return current CPU and RAM usage percentages."""
        if not HAS_PSUTIL:
            return {"cpu": 0, "ram": 0}
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            return {"cpu": cpu, "ram": ram}
        except Exception:
            return {"cpu": 0, "ram": 0}

    # =========================================================================
    # Dispatch Entry Points
    # =========================================================================
    def trigger_key(self, action_type: str, settings: Dict[str, Any]):
        """Dispatch key action."""
        logger.info(f"Triggering action: {action_type} with settings: {settings}")
        if action_type == "spicetify_playpause":
            if not self.spicetify_command("playpause"):
                self.media_play_pause()
        elif action_type == "mpris_next":
            self.media_next()
        elif action_type == "mpris_prev":
            self.media_previous()
        elif action_type == "system_mute":
            self.toggle_mute()
        elif action_type == "app_launcher":
            cmd = settings.get("command", "")
            self.launch_command(cmd)
        elif action_type == "hotkey":
            combo = settings.get("hotkey", "")
            self.send_hotkey(combo)
        elif action_type == "open_url":
            url = settings.get("url", "")
            self.open_url(url)
        elif action_type == "page_next":
            self._switch_page(1)
        elif action_type == "page_prev":
            self._switch_page(-1)
        elif action_type == "page_home":
            self._set_page(0)

    def trigger_knob_rotate(self, turn_type: str, delta: int, settings: Dict[str, Any]):
        """Dispatch knob rotation action."""
        if turn_type == "system_volume":
            step = settings.get("step", 5)
            self.change_volume(step if delta > 0 else -step)
        elif turn_type == "spicetify_volume":
            step = settings.get("step", 0.05)
            self.spicetify_volume(step if delta > 0 else -step)
        elif turn_type == "deck_brightness":
            step = settings.get("step", 10)
            if self.config_manager and self.device:
                cur = self.config_manager.data.get("brightness", 80)
                new_val = max(10, min(100, cur + (step if delta > 0 else -step)))
                self.config_manager.data["brightness"] = new_val
                self.config_manager.save()
                self.device.set_brightness(new_val)

    def trigger_knob_click(self, click_type: str, settings: Dict[str, Any]):
        """Dispatch knob click action."""
        if click_type == "system_mute":
            self.toggle_mute()
        elif click_type == "spicetify_playpause":
            if not self.spicetify_command("playpause"):
                self.media_play_pause()
        elif click_type == "deck_toggle_screen":
            if self.device:
                self.device.set_brightness(0 if self.device.connected else 80)

    def _switch_page(self, delta: int):
        if not self.config_manager:
            return
        profile_name = self.config_manager.data.get("active_profile", "Default")
        profile = self.config_manager.data["profiles"][profile_name]
        cur = profile.get("active_page_index", 0)
        pages = profile.get("pages", [])
        new_idx = (cur + delta) % len(pages)
        profile["active_page_index"] = new_idx
        self.config_manager.save()

    def _set_page(self, idx: int):
        if not self.config_manager:
            return
        profile_name = self.config_manager.data.get("active_profile", "Default")
        profile = self.config_manager.data["profiles"][profile_name]
        profile["active_page_index"] = idx
        self.config_manager.save()
