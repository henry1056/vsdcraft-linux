"""
Image rendering engine for Stream Dock LCD keys (112x112).
Generates icons, text badges, progress arcs, and composite JPEG buffers.
"""

from PIL import Image, ImageDraw, ImageFont
import io
import math
import os
from typing import Optional, Tuple

KEY_SIZE = (112, 112)

class ImageEngine:
    def __init__(self, assets_dir: Optional[str] = None):
        self.assets_dir = assets_dir or os.path.join(os.path.dirname(__file__), "..", "assets")
        self._font_cache = {}

    def get_font(self, size: int):
        if size in self._font_cache:
            return self._font_cache[size]
        try:
            # Common Linux fonts
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf"
            ]
            for p in font_paths:
                if os.path.exists(p):
                    f = ImageFont.truetype(p, size)
                    self._font_cache[size] = f
                    return f
        except Exception:
            pass
        f = ImageFont.load_default()
        self._font_cache[size] = f
        return f

    def render_key(
        self,
        icon_name: str = "",
        title: str = "",
        bg_color: Tuple[int, int, int] = (20, 22, 28),
        icon_color: Tuple[int, int, int] = (255, 255, 255),
        custom_image_path: str = "",
        stats_val: Optional[Tuple[float, float]] = None # (cpu%, ram%)
    ) -> Image.Image:
        """
        Renders a 112x112 RGB image ready for LCD keys.
        """
        im = Image.new("RGB", KEY_SIZE, bg_color)
        draw = ImageDraw.Draw(im)

        # 1. Custom Image if provided
        if custom_image_path and os.path.exists(custom_image_path):
            try:
                user_img = Image.open(custom_image_path).convert("RGBA")
                user_img = user_img.resize(KEY_SIZE, Image.Resampling.LANCZOS)
                im.paste(user_img, (0, 0), user_img)
            except Exception:
                pass

        # 2. Vector built-in icons
        elif icon_name:
            self._draw_builtin_icon(draw, icon_name, icon_color)

        # 3. Dynamic System Stats
        if stats_val is not None:
            cpu, ram = stats_val
            self._draw_system_stats(draw, cpu, ram)

        # 4. Title Text Overlay (at the bottom)
        if title:
            self._draw_title(draw, title)

        return im

    def _draw_builtin_icon(self, draw: ImageDraw.ImageDraw, name: str, color: Tuple[int, int, int]):
        cx, cy = 56, 46

        if name == "spotify_play" or name == "play":
            # Play triangle
            points = [(cx - 14, cy - 20), (cx - 14, cy + 20), (cx + 20, cy)]
            draw.polygon(points, fill=color)
        elif name == "pause":
            # Pause two bars
            draw.rectangle([cx - 15, cy - 18, cx - 5, cy + 18], fill=color)
            draw.rectangle([cx + 5, cy - 18, cx + 15, cy + 18], fill=color)
        elif name == "skip_next":
            # Next track triangle + bar
            points = [(cx - 16, cy - 18), (cx - 16, cy + 18), (cx + 8, cy)]
            draw.polygon(points, fill=color)
            draw.rectangle([cx + 10, cy - 18, cx + 16, cy + 18], fill=color)
        elif name == "volume_mute":
            # Speaker with X
            draw.polygon([(cx - 20, cy - 8), (cx - 10, cy - 8), (cx, cy - 18), (cx, cy + 18), (cx - 10, cy + 8), (cx - 20, cy + 8)], fill=color)
            draw.line([cx + 8, cy - 10, cx + 22, cy + 10], fill=(240, 80, 80), width=3)
            draw.line([cx + 22, cy - 10, cx + 8, cy + 10], fill=(240, 80, 80), width=3)
        elif name == "terminal":
            # >_ prompt
            draw.line([cx - 20, cy - 15, cx - 5, cy, cx - 20, cy + 15], fill=(50, 220, 100), width=4)
            draw.line([cx + 2, cy + 14, cx + 20, cy + 14], fill=(50, 220, 100), width=4)
        elif name == "web":
            # Globe outline
            draw.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=(70, 150, 255), width=3)
            draw.line([cx - 22, cy, cx + 22, cy], fill=(70, 150, 255), width=2)
            draw.ellipse([cx - 12, cy - 22, cx + 12, cy + 22], outline=(70, 150, 255), width=2)
        elif name == "cpu":
            # Microchip
            draw.rectangle([cx - 16, cy - 16, cx + 16, cy + 16], outline=(255, 180, 40), width=3)
            draw.rectangle([cx - 8, cy - 8, cx + 8, cy + 8], fill=(255, 180, 40))
            # Pins
            for offset in (-10, 0, 10):
                draw.line([cx + offset, cy - 22, cx + offset, cy - 16], fill=(255, 180, 40), width=2)
                draw.line([cx + offset, cy + 16, cx + offset, cy + 22], fill=(255, 180, 40), width=2)
                draw.line([cx - 22, cy + offset, cx - 16, cy + offset], fill=(255, 180, 40), width=2)
                draw.line([cx + 16, cy + offset, cx + 22, cy + offset], fill=(255, 180, 40), width=2)
        else:
            # Default icon placeholder circle
            draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=color, width=3)

    def _draw_system_stats(self, draw: ImageDraw.ImageDraw, cpu: float, ram: float):
        # Draw Dual Bars: CPU (Cyan/Green), RAM (Purple/Blue)
        # Background bars
        draw.rectangle([16, 26, 96, 38], fill=(35, 40, 50), outline=(60, 65, 80))
        draw.rectangle([16, 52, 96, 64], fill=(35, 40, 50), outline=(60, 65, 80))

        # Filled portion
        cpu_w = int(16 + (80 * (min(100.0, max(0.0, cpu)) / 100.0)))
        ram_w = int(16 + (80 * (min(100.0, max(0.0, ram)) / 100.0)))

        draw.rectangle([16, 26, cpu_w, 38], fill=(30, 215, 96)) # Green
        draw.rectangle([16, 52, ram_w, 64], fill=(80, 160, 255)) # Blue

        font = self.get_font(10)
        draw.text((16, 12), f"CPU {int(cpu)}%", fill=(220, 220, 220), font=font)
        draw.text((16, 40), f"RAM {int(ram)}%", fill=(220, 220, 220), font=font)

    def _draw_title(self, draw: ImageDraw.ImageDraw, title: str):
        font = self.get_font(13)
        # Bounding box for bottom label
        draw.rectangle([0, 86, 112, 112], fill=(12, 14, 18, 210))
        # Center text
        bbox = draw.textbbox((0, 0), title, font=font)
        tw = bbox[2] - bbox[0]
        tx = max(2, (112 - tw) // 2)
        draw.text((tx, 91), title, fill=(240, 240, 245), font=font)

    def to_jpeg_bytes(self, image: Image.Image) -> bytes:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
