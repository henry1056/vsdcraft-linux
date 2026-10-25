"""
VSDCraft Linux - Graphical User Interface
Built with CustomTkinter for a sleek, modern, dark-mode VSD Craft experience.
"""

import os
import sys
import threading
import time
from typing import Optional, Dict, Any
from PIL import Image, ImageTk

import customtkinter as ctk
from ..hardware.device import StreamDockDevice
from ..hardware.discovery import find_streamdocks
from ..core.config import ConfigManager
from ..core.actions import ActionRunner
from ..core.image_engine import ImageEngine
from ..core.plugin_host import PluginHost

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VSDCraftApp(ctk.CTk):
    def __init__(self, is_mock: bool = False):
        super().__init__()

        self.title("VSDCraft - Stream Dock N3 (Linux Edition)")
        self.geometry("1180x720")
        self.minsize(980, 640)

        # Core subsystems
        self.config_manager = ConfigManager()
        self.image_engine = ImageEngine()
        self.device = StreamDockDevice(is_mock=is_mock)
        self.action_runner = ActionRunner(self.config_manager, self.device)
        self.plugin_host = PluginHost()

        # Selection state
        self.selected_target_type = "key" # "key", "knob", "side"
        self.selected_target_id = 0

        # UI Element references
        self.key_widgets = []
        self.knob_widgets = []
        self.side_widgets = []
        self.key_images = {} # key_id -> CTkImage

        # Setup GUI layout
        self._build_top_bar()
        self._build_main_layout()

        # Connect hardware & start threads
        self._init_hardware()
        self._init_plugins()
        self._start_stats_loop()

        # Initial UI refresh
        self.refresh_deck_display()
        self._select_key(0)

    # =========================================================================
    # Hardware & Subsystem Initialization
    # =========================================================================
    def _init_hardware(self):
        # Setup device callbacks
        self.device.on_key_press = self._on_device_key_press
        self.device.on_knob_rotate = self._on_device_knob_rotate
        self.device.on_knob_press = self._on_device_knob_press
        self.device.on_side_button_press = self._on_device_side_button_press

        # Open device
        self.device.open()
        if self.device.is_mock:
            self.status_label.configure(text="🟡 Simulation Mode (Virtual Deck)", text_color="#f59e0b")
        else:
            self.status_label.configure(text="🟢 Connected: Stream Dock N3 (USB HID)", text_color="#10b981")

    def _init_plugins(self):
        """Starts WebSocket plugin host and looks for local .sdPlugin bundles."""
        try:
            self.plugin_host.start()
            # Look for local Spicetify plugin in parent workspace
            possible_paths = [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "streamdock-plugin", "com.vsdinside.spicetify.sdPlugin")),
                os.path.expanduser("~/.config/vsdcraft/plugins/com.vsdinside.spicetify.sdPlugin")
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    self.plugin_host.launch_plugin_bundle(p)
                    break
        except Exception as e:
            print(f"[VSDCraft] Plugin init notice: {e}")

    # =========================================================================
    # Top Bar
    # =========================================================================
    def _build_top_bar(self):
        self.top_bar = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color="#18181b")
        self.top_bar.pack(side="top", fill="x")

        # Brand Title
        self.title_label = ctk.CTkLabel(
            self.top_bar,
            text="⚡ VSDCraft",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#38bdf8"
        )
        self.title_label.pack(side="left", padx=(20, 10))

        # Model Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.top_bar,
            text="Stream Dock N3 Controller",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        self.subtitle_label.pack(side="left", padx=(0, 20))

        # Hardware Status
        self.status_label = ctk.CTkLabel(
            self.top_bar,
            text="Detecting Device...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#94a3b8"
        )
        self.status_label.pack(side="left", padx=10)

        # Profile Dropdown
        self.profile_var = ctk.StringVar(value="Default")
        self.profile_menu = ctk.CTkOptionMenu(
            self.top_bar,
            values=["Default", "Streaming", "Gaming", "+ New Profile"],
            variable=self.profile_var,
            width=140,
            command=self._on_profile_change
        )
        self.profile_menu.pack(side="right", padx=(10, 20))

        # Brightness Slider
        self.brightness_label = ctk.CTkLabel(self.top_bar, text="Brightness", font=ctk.CTkFont(size=12))
        self.brightness_label.pack(side="right", padx=(10, 5))
        self.brightness_slider = ctk.CTkSlider(
            self.top_bar,
            from_=10,
            to=100,
            number_of_steps=9,
            width=120,
            command=self._on_brightness_change
        )
        self.brightness_slider.set(self.config_manager.data.get("brightness", 80))
        self.brightness_slider.pack(side="right", padx=10)

    # =========================================================================
    # Main Body Layout
    # =========================================================================
    def _build_main_layout(self):
        self.body_frame = ctk.CTkFrame(self, fg_color="#09090b", corner_radius=0)
        self.body_frame.pack(side="top", fill="both", expand=True)

        # Left / Center: Virtual Stream Dock Hardware Deck
        self.deck_panel = ctk.CTkFrame(self.body_frame, fg_color="#121215", corner_radius=12)
        self.deck_panel.pack(side="left", fill="both", expand=True, padx=16, pady=16)

        self._build_deck_panel()

        # Right: Action Palette & Property Inspector
        self.sidebar_panel = ctk.CTkFrame(self.body_frame, width=380, fg_color="#18181b", corner_radius=12)
        self.sidebar_panel.pack(side="right", fill="both", padx=(0, 16), pady=16)
        self.sidebar_panel.pack_propagate(False)

        self._build_sidebar_panel()

    # =========================================================================
    # Virtual Stream Dock Chassis & Controls
    # =========================================================================
    def _build_deck_panel(self):
        deck_header = ctk.CTkFrame(self.deck_panel, fg_color="transparent")
        deck_header.pack(fill="x", padx=20, pady=(15, 5))

        deck_title = ctk.CTkLabel(deck_header, text="Virtual Device Preview", font=ctk.CTkFont(size=16, weight="bold"))
        deck_title.pack(side="left")

        # Chassis Outer Container (resembling physical N3 console)
        chassis = ctk.CTkFrame(self.deck_panel, fg_color="#1c1d22", corner_radius=20, border_width=3, border_color="#2e313b")
        chassis.pack(expand=True, padx=30, pady=20)

        # Inside Chassis: [ 3 Knobs on Left ] [ 6 Keys 2x3 Center ] [ 3 Side Buttons Right ]
        content_box = ctk.CTkFrame(chassis, fg_color="transparent")
        content_box.pack(padx=24, pady=24)

        # --- Column 1: Knobs ---
        knobs_box = ctk.CTkFrame(content_box, fg_color="#141519", corner_radius=14, border_width=1, border_color="#2b2d35")
        knobs_box.pack(side="left", padx=12, pady=10, fill="y")

        knob_header = ctk.CTkLabel(knobs_box, text="KNOBS", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b")
        knob_header.pack(pady=(10, 5))

        for k in range(3):
            k_frame = ctk.CTkFrame(knobs_box, fg_color="#1e2026", corner_radius=10, width=130, height=85)
            k_frame.pack(padx=10, pady=6)
            k_frame.pack_propagate(False)

            k_title = ctk.CTkLabel(k_frame, text=f"Knob {k+1}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8")
            k_title.pack(pady=(4, 2))

            # Turn controls (- / + buttons for simulation)
            btn_box = ctk.CTkFrame(k_frame, fg_color="transparent")
            btn_box.pack(pady=2)

            btn_left = ctk.CTkButton(
                btn_box, text="◀", width=28, height=26,
                fg_color="#2a2d36", hover_color="#3b82f6",
                command=lambda idx=k: self._on_ui_knob_turn(idx, -1)
            )
            btn_left.pack(side="left", padx=2)

            btn_click = ctk.CTkButton(
                btn_box, text="CLICK", width=50, height=26, font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#3b82f6", hover_color="#2563eb",
                command=lambda idx=k: self._on_ui_knob_click(idx)
            )
            btn_click.pack(side="left", padx=2)

            btn_right = ctk.CTkButton(
                btn_box, text="▶", width=28, height=26,
                fg_color="#2a2d36", hover_color="#3b82f6",
                command=lambda idx=k: self._on_ui_knob_turn(idx, 1)
            )
            btn_right.pack(side="left", padx=2)

            # Bind selection
            k_frame.bind("<Button-1>", lambda e, idx=k: self._select_knob(idx))
            k_title.bind("<Button-1>", lambda e, idx=k: self._select_knob(idx))
            self.knob_widgets.append({"frame": k_frame, "title": k_title})

        # --- Column 2: 6 LCD Keys Grid (3 columns x 2 rows) ---
        keys_box = ctk.CTkFrame(content_box, fg_color="#141519", corner_radius=14, border_width=1, border_color="#2b2d35")
        keys_box.pack(side="left", padx=12, pady=10)

        keys_header = ctk.CTkLabel(keys_box, text="LCD KEYS (112×112)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b")
        keys_header.pack(pady=(10, 5))

        grid_frame = ctk.CTkFrame(keys_box, fg_color="transparent")
        grid_frame.pack(padx=12, pady=10)

        # 2 rows x 3 columns
        for idx in range(6):
            r = idx // 3
            c = idx % 3

            btn = ctk.CTkButton(
                grid_frame,
                text="",
                width=112,
                height=112,
                corner_radius=12,
                border_width=2,
                border_color="#3b82f6" if idx == 0 else "#2e313b",
                fg_color="#181a20",
                hover_color="#262a34",
                command=lambda i=idx: self._on_ui_key_click(i)
            )
            btn.grid(row=r, column=c, padx=8, pady=8)
            self.key_widgets.append(btn)

        # --- Column 3: 3 Physical Side Buttons ---
        side_box = ctk.CTkFrame(content_box, fg_color="#141519", corner_radius=14, border_width=1, border_color="#2b2d35")
        side_box.pack(side="left", padx=12, pady=10, fill="y")

        side_header = ctk.CTkLabel(side_box, text="SIDE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748b")
        side_header.pack(pady=(10, 5))

        side_titles = ["▲ Prev", "▼ Next", "● Home"]
        for s in range(3):
            s_btn = ctk.CTkButton(
                side_box,
                text=side_titles[s],
                width=80,
                height=76,
                corner_radius=10,
                border_width=1,
                border_color="#2b2d35",
                fg_color="#1e2026",
                hover_color="#3b82f6",
                command=lambda idx=s: self._on_ui_side_button_click(idx)
            )
            s_btn.pack(padx=10, pady=8)
            self.side_widgets.append(s_btn)

    # =========================================================================
    # Sidebar: Action Library & Inspector
    # =========================================================================
    def _build_sidebar_panel(self):
        self.tabview = ctk.CTkTabview(self.sidebar_panel, fg_color="#18181b")
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_actions = self.tabview.add("Action Palette")
        self.tab_inspector = self.tabview.add("Key / Knob Settings")

        self._build_action_palette()
        self._build_inspector_tab()

    def _build_action_palette(self):
        scroll = ctk.CTkScrollableFrame(self.tab_actions, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        categories = [
            ("🎵 Spotify & Spicetify", [
                ("spicetify_playpause", "Play / Pause", "spotify_play"),
                ("mpris_next", "Next Track", "skip_next"),
                ("mpris_prev", "Previous Track", "skip_next"),
                ("spicetify_volume", "Spotify Volume (Knob)", "volume"),
            ]),
            ("🔊 System Audio", [
                ("system_volume", "Master Volume (Knob)", "volume"),
                ("system_mute", "Toggle Mute", "volume_mute"),
            ]),
            ("🚀 App Launchers & Web", [
                ("app_launcher", "Launch Terminal", "terminal", {"command": "x-terminal-emulator || gnome-terminal || alacritty"}),
                ("app_launcher", "Launch Discord", "web", {"command": "discord"}),
                ("app_launcher", "Launch OBS Studio", "web", {"command": "obs"}),
                ("open_url", "Open Webpage (URL)", "web", {"url": "https://youtube.com"}),
            ]),
            ("📊 System Monitor", [
                ("system_stats", "Live CPU / RAM Graph", "cpu", {"metric": "both"}),
            ]),
            ("⌨️ Macros & Hotkeys", [
                ("hotkey", "Custom Hotkey", "keyboard", {"hotkey": "ctrl+shift+m"}),
            ]),
            ("📱 Pages & Navigation", [
                ("page_next", "Next Page", "arrow_right"),
                ("page_prev", "Previous Page", "arrow_left"),
                ("page_home", "Home Page", "home"),
            ])
        ]

        for cat_title, actions in categories:
            lbl = ctk.CTkLabel(scroll, text=cat_title, font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8")
            lbl.pack(anchor="w", padx=6, pady=(12, 4))

            for act_info in actions:
                act_type = act_info[0]
                act_name = act_info[1]
                icon = act_info[2]
                settings = act_info[3] if len(act_info) > 3 else {}

                item_btn = ctk.CTkButton(
                    scroll,
                    text=f"+ Assign: {act_name}",
                    anchor="w",
                    height=32,
                    fg_color="#27272a",
                    hover_color="#3b82f6",
                    command=lambda t=act_type, n=act_name, ic=icon, s=settings: self._assign_action(t, n, ic, s)
                )
                item_btn.pack(fill="x", padx=6, pady=2)

    def _build_inspector_tab(self):
        container = ctk.CTkFrame(self.tab_inspector, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.inspector_title = ctk.CTkLabel(container, text="Selection: Key 1", font=ctk.CTkFont(size=15, weight="bold"))
        self.inspector_title.pack(anchor="w", pady=(0, 10))

        # Title entry
        ctk.CTkLabel(container, text="Button Label / Title:").pack(anchor="w", pady=(5, 2))
        self.entry_title = ctk.CTkEntry(container, placeholder_text="e.g. Play/Pause")
        self.entry_title.pack(fill="x", pady=(0, 10))

        # Action Type dropdown
        ctk.CTkLabel(container, text="Action Type:").pack(anchor="w", pady=(5, 2))
        self.action_type_var = ctk.StringVar(value="spicetify_playpause")
        self.action_type_menu = ctk.CTkOptionMenu(
            container,
            values=[
                "spicetify_playpause", "mpris_next", "mpris_prev",
                "system_mute", "app_launcher", "open_url", "hotkey",
                "system_stats", "page_next", "page_prev", "none"
            ],
            variable=self.action_type_var
        )
        self.action_type_menu.pack(fill="x", pady=(0, 10))

        # Command / URL / Param Entry
        self.param_label = ctk.CTkLabel(container, text="Command / Parameter:")
        self.param_label.pack(anchor="w", pady=(5, 2))
        self.entry_param = ctk.CTkEntry(container, placeholder_text="e.g. gnome-terminal or URL")
        self.entry_param.pack(fill="x", pady=(0, 15))

        # Save Button
        btn_save = ctk.CTkButton(
            container,
            text="Apply Changes",
            fg_color="#10b981",
            hover_color="#059669",
            command=self._save_inspector_changes
        )
        btn_save.pack(fill="x", pady=6)

        # Clear Action Button
        btn_clear = ctk.CTkButton(
            container,
            text="Clear / Reset",
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._clear_selected_action
        )
        btn_clear.pack(fill="x", pady=6)

    # =========================================================================
    # Selection & Binding Handlers
    # =========================================================================
    def _select_key(self, key_idx: int):
        self.selected_target_type = "key"
        self.selected_target_id = key_idx

        # Update border highlight
        for i, btn in enumerate(self.key_widgets):
            btn.configure(border_color="#3b82f6" if i == key_idx else "#2e313b")

        page = self.config_manager.get_current_page()
        keys = page.get("keys", [])
        key_data = keys[key_idx] if key_idx < len(keys) else {}

        self.inspector_title.configure(text=f"Selected: LCD Key #{key_idx + 1}")
        self.entry_title.delete(0, "end")
        self.entry_title.insert(0, key_data.get("title", ""))
        self.action_type_var.set(key_data.get("type", "none"))

        settings = key_data.get("settings", {})
        param_val = settings.get("command") or settings.get("url") or settings.get("hotkey") or ""
        self.entry_param.delete(0, "end")
        self.entry_param.insert(0, param_val)

        self.tabview.set("Key / Knob Settings")

    def _select_knob(self, knob_idx: int):
        self.selected_target_type = "knob"
        self.selected_target_id = knob_idx

        page = self.config_manager.get_current_page()
        knobs = page.get("knobs", [])
        knob_data = knobs[knob_idx] if knob_idx < len(knobs) else {}

        self.inspector_title.configure(text=f"Selected: Rotary Knob #{knob_idx + 1}")
        self.entry_title.delete(0, "end")
        self.entry_title.insert(0, knob_data.get("title", f"Knob {knob_idx + 1}"))
        self.action_type_var.set(knob_data.get("turn_type", "system_volume"))

        self.entry_param.delete(0, "end")
        self.tabview.set("Key / Knob Settings")

    def _assign_action(self, act_type: str, title: str, icon: str, settings: Dict):
        if self.selected_target_type == "key":
            self.config_manager.set_key_action(
                self.selected_target_id,
                action_type=act_type,
                title=title,
                icon=icon,
                settings=settings
            )
            self._select_key(self.selected_target_id)
        elif self.selected_target_type == "knob":
            self.config_manager.set_knob_action(
                self.selected_target_id,
                turn_type=act_type,
                click_type="system_mute",
                title=title,
                settings=settings
            )
            self._select_knob(self.selected_target_id)

        self.refresh_deck_display()

    def _save_inspector_changes(self):
        new_title = self.entry_title.get()
        new_type = self.action_type_var.get()
        new_param = self.entry_param.get().strip()

        settings = {}
        if new_type == "app_launcher":
            settings["command"] = new_param
        elif new_type == "open_url":
            settings["url"] = new_param
        elif new_type == "hotkey":
            settings["hotkey"] = new_param

        if self.selected_target_type == "key":
            self.config_manager.set_key_action(
                self.selected_target_id,
                action_type=new_type,
                title=new_title,
                icon="custom",
                settings=settings
            )
        elif self.selected_target_type == "knob":
            self.config_manager.set_knob_action(
                self.selected_target_id,
                turn_type=new_type,
                title=new_title,
                settings=settings
            )

        self.refresh_deck_display()

    def _clear_selected_action(self):
        if self.selected_target_type == "key":
            self.config_manager.set_key_action(self.selected_target_id, action_type="none", title="", icon="")
            self._select_key(self.selected_target_id)
        elif self.selected_target_type == "knob":
            self.config_manager.set_knob_action(self.selected_target_id, turn_type="none", title="")
            self._select_knob(self.selected_target_id)
        self.refresh_deck_display()

    # =========================================================================
    # Screen & LCD Rendering Engine Sync
    # =========================================================================
    def refresh_deck_display(self):
        page = self.config_manager.get_current_page()
        keys = page.get("keys", [])

        stats = self.action_runner.get_system_stats()

        for idx in range(6):
            if idx < len(keys):
                k = keys[idx]
                act_type = k.get("type", "none")
                title = k.get("title", "")
                icon_name = k.get("icon", "")

                stats_tuple = (stats["cpu"], stats["ram"]) if act_type == "system_stats" else None
                img = self.image_engine.render_key(
                    icon_name=icon_name,
                    title=title,
                    stats_val=stats_tuple
                )
            else:
                img = self.image_engine.render_key(title=f"Key {idx+1}")

            # Send to physical Stream Dock hardware
            if self.device and self.device.connected and not self.device.is_mock:
                self.device.set_key_image(idx, img)

            # Update Virtual UI Button
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 100))
            self.key_images[idx] = ctk_img
            self.key_widgets[idx].configure(image=ctk_img)

        # Update Knob Labels
        knobs = page.get("knobs", [])
        for k_idx, k_widget in enumerate(self.knob_widgets):
            if k_idx < len(knobs):
                k_widget["title"].configure(text=knobs[k_idx].get("title", f"Knob {k_idx+1}"))

    def _start_stats_loop(self):
        def loop():
            while True:
                time.sleep(2.0)
                try:
                    self.after(0, self._check_dynamic_updates)
                except Exception:
                    break

        t = threading.Thread(target=loop, daemon=True, name="VSDCraft-StatsMonitor")
        t.start()

    def _check_dynamic_updates(self):
        page = self.config_manager.get_current_page()
        keys = page.get("keys", [])
        has_stats = any(k.get("type") == "system_stats" for k in keys)
        if has_stats:
            self.refresh_deck_display()

    # =========================================================================
    # Action Triggers (Hardware + UI simulation)
    # =========================================================================
    def _on_ui_key_click(self, key_idx: int):
        self._select_key(key_idx)
        self._trigger_key_action(key_idx)

    def _on_device_key_press(self, key_idx: int, pressed: bool):
        if pressed:
            self.after(0, lambda: self._flash_key_ui(key_idx))
            self._trigger_key_action(key_idx)

    def _flash_key_ui(self, key_idx: int):
        if 0 <= key_idx < len(self.key_widgets):
            self.key_widgets[key_idx].configure(border_color="#10b981")
            self.after(200, lambda: self.key_widgets[key_idx].configure(
                border_color="#3b82f6" if key_idx == self.selected_target_id else "#2e313b"
            ))

    def _trigger_key_action(self, key_idx: int):
        page = self.config_manager.get_current_page()
        keys = page.get("keys", [])
        if key_idx < len(keys):
            k = keys[key_idx]
            act_type = k.get("type", "none")
            settings = k.get("settings", {})
            self.action_runner.trigger_key(act_type, settings)

            # If page switch occurred, refresh
            if act_type.startswith("page_"):
                self.after(50, self.refresh_deck_display)

    def _on_ui_knob_turn(self, knob_idx: int, delta: int):
        self._select_knob(knob_idx)
        self._trigger_knob_turn(knob_idx, delta)

    def _on_device_knob_rotate(self, knob_idx: int, delta: int):
        self._trigger_knob_turn(knob_idx, delta)

    def _trigger_knob_turn(self, knob_idx: int, delta: int):
        page = self.config_manager.get_current_page()
        knobs = page.get("knobs", [])
        if knob_idx < len(knobs):
            k = knobs[knob_idx]
            turn_type = k.get("turn_type", "none")
            settings = k.get("settings", {})
            self.action_runner.trigger_knob_rotate(turn_type, delta, settings)

    def _on_ui_knob_click(self, knob_idx: int):
        self._select_knob(knob_idx)
        page = self.config_manager.get_current_page()
        knobs = page.get("knobs", [])
        if knob_idx < len(knobs):
            k = knobs[knob_idx]
            click_type = k.get("click_type", "none")
            settings = k.get("settings", {})
            self.action_runner.trigger_knob_click(click_type, settings)

    def _on_device_knob_press(self, knob_idx: int, pressed: bool):
        if pressed:
            self._on_ui_knob_click(knob_idx)

    def _on_ui_side_button_click(self, btn_idx: int):
        page = self.config_manager.get_current_page()
        side_btns = page.get("side_buttons", [])
        if btn_idx < len(side_btns):
            b = side_btns[btn_idx]
            self.action_runner.trigger_key(b.get("type", "none"), {})
            self.after(50, self.refresh_deck_display)

    def _on_device_side_button_press(self, btn_idx: int, pressed: bool):
        if pressed:
            self._on_ui_side_button_click(btn_idx)

    def _on_brightness_change(self, value):
        val = int(value)
        self.config_manager.data["brightness"] = val
        self.config_manager.save()
        if self.device:
            self.device.set_brightness(val)

    def _on_profile_change(self, profile_name):
        if profile_name == "+ New Profile":
            # Simple prompt logic or default
            profile_name = f"Profile_{len(self.config_manager.data.get('profiles', {})) + 1}"
            self.config_manager.data.setdefault("profiles", {})[profile_name] = {
                "active_page_index": 0,
                "pages": self.config_manager.data["profiles"]["Default"]["pages"]
            }
            self.profile_menu.configure(values=list(self.config_manager.data["profiles"].keys()) + ["+ New Profile"])

        self.config_manager.data["active_profile"] = profile_name
        self.config_manager.save()
        self.refresh_deck_display()
