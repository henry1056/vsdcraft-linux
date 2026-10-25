"""
Headless background daemon for VSDCraft.
Runs silently, listening to hardware keys/knobs and executing configured actions.
"""

import time
import signal
import logging
from .hardware.device import StreamDockDevice
from .core.config import ConfigManager
from .core.actions import ActionRunner
from .core.image_engine import ImageEngine
from .core.plugin_host import PluginHost

logger = logging.getLogger("vsdcraft.daemon")

def run_daemon(is_mock: bool = False):
    logger.info("Starting VSDCraft Linux daemon...")

    config_manager = ConfigManager()
    image_engine = ImageEngine()
    device = StreamDockDevice(is_mock=is_mock)
    action_runner = ActionRunner(config_manager, device)
    plugin_host = PluginHost()

    def update_deck_display():
        page = config_manager.get_current_page()
        keys = page.get("keys", [])
        stats = action_runner.get_system_stats()

        for idx in range(6):
            if idx < len(keys):
                k = keys[idx]
                act_type = k.get("type", "none")
                title = k.get("title", "")
                icon_name = k.get("icon", "")
                stats_tuple = (stats["cpu"], stats["ram"]) if act_type == "system_stats" else None
                img = image_engine.render_key(icon_name=icon_name, title=title, stats_val=stats_tuple)
            else:
                img = image_engine.render_key(title=f"Key {idx+1}")

            if device.connected and not device.is_mock:
                device.set_key_image(idx, img)

    def on_key(idx: int, pressed: bool):
        if pressed:
            page = config_manager.get_current_page()
            keys = page.get("keys", [])
            if idx < len(keys):
                k = keys[idx]
                act_type = k.get("type", "none")
                action_runner.trigger_key(act_type, k.get("settings", {}))
                if act_type.startswith("page_"):
                    update_deck_display()

    def on_knob_rotate(knob_idx: int, delta: int):
        page = config_manager.get_current_page()
        knobs = page.get("knobs", [])
        if knob_idx < len(knobs):
            k = knobs[knob_idx]
            action_runner.trigger_knob_rotate(k.get("turn_type", "none"), delta, k.get("settings", {}))

    def on_knob_press(knob_idx: int, pressed: bool):
        if pressed:
            page = config_manager.get_current_page()
            knobs = page.get("knobs", [])
            if knob_idx < len(knobs):
                k = knobs[knob_idx]
                action_runner.trigger_knob_click(k.get("click_type", "none"), k.get("settings", {}))

    def on_side_button(btn_idx: int, pressed: bool):
        if pressed:
            page = config_manager.get_current_page()
            side_btns = page.get("side_buttons", [])
            if btn_idx < len(side_btns):
                b = side_btns[btn_idx]
                action_runner.trigger_key(b.get("type", "none"), {})
                update_deck_display()

    device.on_key_press = on_key
    device.on_knob_rotate = on_knob_rotate
    device.on_knob_press = on_knob_press
    device.on_side_button_press = on_side_button

    if not device.open():
        logger.error("Failed to initialize hardware.")
        return

    plugin_host.start()
    update_deck_display()

    running = True
    def shutdown(sig, frame):
        nonlocal running
        logger.info("Daemon received shutdown signal.")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("VSDCraft daemon running. Press Ctrl+C to terminate.")
    last_stats = time.time()
    while running:
        time.sleep(1.0)
        # Periodically refresh LCD keys if system stats is assigned
        if time.time() - last_stats > 2.0:
            last_stats = time.time()
            page = config_manager.get_current_page()
            keys = page.get("keys", [])
            if any(k.get("type") == "system_stats" for k in keys):
                update_deck_display()

    device.close()
    logger.info("Daemon exited cleanly.")
