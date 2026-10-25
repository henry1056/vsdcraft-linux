"""
StreamDock Plugin Host for VSDCraft Linux.
Spawns and communicates with .sdPlugin bundles (like Spicetify StreamDock plugin)
via bidirectional WebSockets, adhering to the StreamDock / Stream Deck plugin protocol.
"""

import os
import json
import asyncio
import logging
import threading
import subprocess
import websockets
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger("vsdcraft.plugin_host")

class PluginHost:
    def __init__(self, port: int = 28975):
        self.port = port
        self.plugins = {}  # uuid -> plugin_info
        self.active_connections = {}  # uuid -> websocket
        self.context_callbacks: Dict[str, Callable[[str, Any], None]] = {} # context -> callback(event, payload)
        self.server = None
        self._loop = None
        self._thread = None
        self.running = False

    def start(self):
        """Start the WebSocket server in a background thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True, name="PluginHost-Server")
        self._thread.start()
        logger.info(f"PluginHost WebSocket server starting on ws://127.0.0.1:{self.port}")

    def _run_server(self):
        async def main_async():
            self._loop = asyncio.get_running_loop()

            async def handler(websocket):
                plugin_uuid = None
                try:
                    async for raw_msg in websocket:
                        try:
                            msg = json.loads(raw_msg)
                        except Exception:
                            continue
                        
                        event = msg.get("event")
                        if event in ("registerPlugin", "registerPropertyInspector"):
                            plugin_uuid = msg.get("uuid")
                            self.active_connections[plugin_uuid] = websocket
                            logger.info(f"Plugin registered successfully: {plugin_uuid}")
                        else:
                            self._handle_incoming_plugin_msg(msg)
                except Exception:
                    pass
                finally:
                    if plugin_uuid and plugin_uuid in self.active_connections:
                        del self.active_connections[plugin_uuid]
                        logger.info(f"Plugin disconnected: {plugin_uuid}")

            async with websockets.serve(handler, "127.0.0.1", self.port):
                logger.info(f"PluginHost WebSocket listening on ws://127.0.0.1:{self.port}")
                await asyncio.Future() # Run forever

        try:
            asyncio.run(main_async())
        except Exception as e:
            logger.debug(f"PluginHost server loop exit: {e}")

    def _handle_incoming_plugin_msg(self, msg: Dict[str, Any]):
        """Handle events sent by the plugin (setImage, setTitle, etc.)."""
        event = msg.get("event")
        context = msg.get("context")
        payload = msg.get("payload", {})
        
        if context and context in self.context_callbacks:
            self.context_callbacks[context](event, payload)

    def send_to_plugin(self, uuid: str, msg: Dict[str, Any]):
        """Send a message to a registered plugin."""
        if not self._loop or uuid not in self.active_connections:
            return
        ws = self.active_connections[uuid]
        payload = json.dumps(msg)
        asyncio.run_coroutine_threadsafe(ws.send(payload), self._loop)

    def dispatch_key_down(self, uuid: str, action: str, context: str, settings: Dict = None):
        self.send_to_plugin(uuid, {
            "event": "keyDown",
            "action": action,
            "context": context,
            "device": "StreamDock_N3",
            "payload": {
                "settings": settings or {},
                "coordinates": {"row": 0, "column": 0},
                "state": 0
            }
        })

    def dispatch_dial_rotate(self, uuid: str, action: str, context: str, ticks: int, settings: Dict = None):
        self.send_to_plugin(uuid, {
            "event": "dialRotate",
            "action": action,
            "context": context,
            "device": "StreamDock_N3",
            "payload": {
                "settings": settings or {},
                "ticks": ticks,
                "pressed": False
            }
        })

    def dispatch_will_appear(self, uuid: str, action: str, context: str, settings: Dict = None):
        self.send_to_plugin(uuid, {
            "event": "willAppear",
            "action": action,
            "context": context,
            "device": "StreamDock_N3",
            "payload": {
                "settings": settings or {},
                "coordinates": {"row": 0, "column": 0},
                "state": 0
            }
        })

    def launch_plugin_bundle(self, plugin_dir: str):
        """
        Reads manifest.json of an .sdPlugin directory and launches its Node.js entry point.
        """
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            logger.error(f"No manifest.json found in {plugin_dir}")
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            uuid = manifest.get("UUID") or manifest.get("CodePath") or os.path.basename(plugin_dir)
            code_path = manifest.get("CodePath", "plugin/index.js")
            full_code_path = os.path.join(plugin_dir, code_path)

            if not os.path.exists(full_code_path):
                # Fallback check
                full_code_path = os.path.join(plugin_dir, "plugin", "index.js")

            logger.info(f"Launching plugin '{manifest.get('Name')}' ({uuid}) from {full_code_path}")

            # Command line args matching VSD Craft / Stream Dock SDK:
            cmd = [
                "node",
                full_code_path,
                "-port", str(self.port),
                "-pluginUUID", uuid,
                "-registerEvent", "registerPlugin"
            ]

            process = subprocess.Popen(
                cmd,
                cwd=plugin_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            self.plugins[uuid] = {
                "manifest": manifest,
                "process": process,
                "dir": plugin_dir
            }
            return True
        except Exception as e:
            logger.error(f"Failed to launch plugin bundle {plugin_dir}: {e}")
            return False
