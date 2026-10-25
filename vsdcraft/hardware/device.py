"""
Stream Dock N3 Hardware Communication Driver.
Handles USB HID communication, event parsing (keys, knobs, side buttons),
and sending JPEG image buffers to LCD keys.
"""

import io
import time
import logging
import threading
from typing import Callable, Optional, Dict, Any
from PIL import Image

logger = logging.getLogger("vsdcraft.device")

try:
    import hid
    HAS_HID = True
except ImportError:
    HAS_HID = False

class StreamDockDevice:
    """
    Driver for Stream Dock N3 and compatible hardware controllers.
    """
    KEY_WIDTH = 112
    KEY_HEIGHT = 112
    KEY_COUNT = 6
    KNOB_COUNT = 3
    SIDE_BUTTON_COUNT = 3
    CHUNK_SIZE = 1024

    def __init__(self, path: Optional[bytes] = None, is_mock: bool = False):
        self.path = path
        self.is_mock = is_mock or not HAS_HID
        self.dev = None
        self.connected = False
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        
        # State tracking
        self.key_states = [False] * self.KEY_COUNT
        self.knob_states = [False] * self.KNOB_COUNT
        self.side_button_states = [False] * self.SIDE_BUTTON_COUNT

        # Callbacks
        self.on_key_press: Optional[Callable[[int, bool], None]] = None
        self.on_knob_rotate: Optional[Callable[[int, int], None]] = None # (knob_idx, delta)
        self.on_knob_press: Optional[Callable[[int, bool], None]] = None # (knob_idx, pressed)
        self.on_side_button_press: Optional[Callable[[int, bool], None]] = None # (btn_idx, pressed)

    def open(self) -> bool:
        if self.is_mock:
            self.connected = True
            logger.info("Opened StreamDock in VIRTUAL / MOCK mode (No physical hardware required)")
            return True

        if not HAS_HID:
            logger.warning("hidapi not available. Falling back to MOCK mode.")
            self.is_mock = True
            self.connected = True
            return True

        try:
            self.dev = hid.device()
            if self.path:
                self.dev.open_path(self.path)
            else:
                from .discovery import find_streamdocks
                devices = find_streamdocks()
                if not devices:
                    logger.warning("No physical Stream Dock found. Starting in simulation mode.")
                    self.is_mock = True
                    self.connected = True
                    return True
                self.dev.open_path(devices[0]["path"])

            self.dev.set_nonblocking(False)
            self.connected = True
            self._send_handshake()

            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True, name="StreamDock-Reader")
            self._read_thread.start()
            logger.info("Successfully connected to physical Stream Dock device.")
            return True
        except Exception as e:
            logger.error(f"Failed to open Stream Dock: {e}. Falling back to MOCK mode.")
            self.is_mock = True
            self.connected = True
            return True

    def close(self):
        self._running = False
        if self.dev:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None
        self.connected = False

    def _send_handshake(self):
        """Send initialization magic packets to wake up Stream Dock."""
        if not self.dev or self.is_mock:
            return
        try:
            # Standard wake/handshake sequence for Hotspotek/Mirabox firmware
            magic = b"\x00CRT\x00\x00CONNECT"
            self.dev.write(magic.ljust(64, b"\x00"))
            time.sleep(0.05)
        except Exception as e:
            logger.debug(f"Handshake note: {e}")

    def set_brightness(self, percent: int):
        """Set display backlight brightness (0-100%)."""
        if self.is_mock or not self.dev:
            return
        percent = max(0, min(100, percent))
        try:
            cmd = bytearray(64)
            cmd[0] = 0x00  # Report ID
            cmd[1] = 0x05  # Brightness command opcode
            cmd[2] = percent
            self.dev.write(bytes(cmd))
        except Exception as e:
            logger.error(f"Error setting brightness: {e}")

    def set_key_image(self, key_index: int, image_or_path: Any):
        """
        Send a JPEG image to the specified key LCD display (0 to 5).
        Accepts PIL Image, file path, or bytes.
        """
        if key_index < 0 or key_index >= self.KEY_COUNT:
            return

        # Prepare JPEG bytes
        img_bytes = self._prepare_image_bytes(image_or_path)
        if not img_bytes:
            return

        if self.is_mock or not self.dev:
            return

        try:
            self._send_image_chunks(key_index, img_bytes)
        except Exception as e:
            logger.error(f"Error sending image to key {key_index}: {e}")

    def _prepare_image_bytes(self, image_input: Any) -> bytes:
        """Convert input to properly sized 112x112 JPEG bytes."""
        if isinstance(image_input, bytes):
            return image_input

        im: Optional[Image.Image] = None
        if isinstance(image_input, str):
            try:
                im = Image.open(image_input).convert("RGB")
            except Exception as e:
                logger.error(f"Failed to open image file '{image_input}': {e}")
                return b""
        elif isinstance(image_input, Image.Image):
            im = image_input.convert("RGB")

        if im is None:
            return b""

        # Resize to native key dimensions
        im_resized = im.resize((self.KEY_WIDTH, self.KEY_HEIGHT), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im_resized.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def _send_image_chunks(self, key_index: int, jpeg_bytes: bytes):
        """
        Split JPEG bytes into chunks with device header and transmit via HID.
        Stream Dock packet format:
        [Report ID: 0x02] [Key Index] [Flags: 1=final, 0=chunk] [Payload Length (2 bytes)] [Offset (2 bytes)] ... data
        """
        total_len = len(jpeg_bytes)
        offset = 0
        chunk_payload_size = 1000

        while offset < total_len:
            end = min(offset + chunk_payload_size, total_len)
            chunk = jpeg_bytes[offset:end]
            is_last = 1 if end >= total_len else 0

            # Construct report
            packet = bytearray(1024)
            packet[0] = 0x02  # Report ID for image payload
            packet[1] = key_index
            packet[2] = is_last
            packet[3] = (len(chunk) >> 8) & 0xFF
            packet[4] = len(chunk) & 0xFF
            packet[5] = (offset >> 8) & 0xFF
            packet[6] = offset & 0xFF
            packet[7:7 + len(chunk)] = chunk

            self.dev.write(bytes(packet))
            offset = end
            time.sleep(0.001)

    def _read_loop(self):
        """Background thread listening for raw HID input reports."""
        logger.info("StreamDock input listening thread started.")
        while self._running and self.dev:
            try:
                data = self.dev.read(64, timeout_ms=50)
                if not data:
                    continue
                self._parse_report(data)
            except Exception as e:
                if self._running:
                    logger.debug(f"Read error or disconnect: {e}")
                time.sleep(0.1)

    def _parse_report(self, report: bytes):
        """
        Parse raw HID input report from Stream Dock N3:
        Report formats typically encode:
        - Byte 1: Report type / state
        - Bytes for keys: Key bitmask or direct button index
        - Bytes for rotary encoders: Direction + step count (+1 clockwise, 0xFF / -1 counter-clockwise)
        - Knob press buttons
        - Side physical buttons
        """
        if len(report) < 4:
            return

        report_id = report[0]

        # Standard button report parsing
        # (Handles both raw matrix bitmask and event-based payloads)
        if report_id == 0x01 or len(report) >= 8:
            # 6 LCD Keys
            # Look for button states in bytes 1-6 or bitmask
            for i in range(self.KEY_COUNT):
                is_down = bool(report[1 + i]) if len(report) > 1 + i else False
                if is_down != self.key_states[i]:
                    self.key_states[i] = is_down
                    if self.on_key_press:
                        self.on_key_press(i, is_down)

            # Knobs (3 rotary encoders)
            # Typically mapped to bytes 7, 8, 9 for rotation delta
            if len(report) >= 10:
                for k in range(self.KNOB_COUNT):
                    val = report[7 + k]
                    if val != 0:
                        delta = 1 if val == 1 else -1
                        if self.on_knob_rotate:
                            self.on_knob_rotate(k, delta)

            # Knob Clicks & Side Buttons
            if len(report) >= 13:
                for k in range(self.KNOB_COUNT):
                    click_down = bool(report[10 + k])
                    if click_down != self.knob_states[k]:
                        self.knob_states[k] = click_down
                        if self.on_knob_press:
                            self.on_knob_press(k, click_down)

    def simulate_key(self, key_index: int, pressed: bool):
        """Simulate a key press in Mock/Virtual mode."""
        if 0 <= key_index < self.KEY_COUNT:
            self.key_states[key_index] = pressed
            if self.on_key_press:
                self.on_key_press(key_index, pressed)

    def simulate_knob_rotate(self, knob_index: int, delta: int):
        """Simulate a knob turn in Mock/Virtual mode."""
        if 0 <= knob_index < self.KNOB_COUNT and self.on_knob_rotate:
            self.on_knob_rotate(knob_index, delta)

    def simulate_knob_press(self, knob_index: int, pressed: bool):
        """Simulate a knob press in Mock/Virtual mode."""
        if 0 <= knob_index < self.KNOB_COUNT:
            self.knob_states[knob_index] = pressed
            if self.on_knob_press:
                self.on_knob_press(knob_index, pressed)

    def simulate_side_button(self, btn_index: int, pressed: bool):
        """Simulate a side button press in Mock/Virtual mode."""
        if 0 <= btn_index < self.SIDE_BUTTON_COUNT:
            self.side_button_states[btn_index] = pressed
            if self.on_side_button_press:
                self.on_side_button_press(btn_index, pressed)
