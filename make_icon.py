"""Generate a multi-size .ico app icon for the Jianpu Converter."""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]
BG_TOP = (79, 70, 229)      # #4F46E5 indigo
BG_BOTTOM = (30, 41, 59)    # #1E293B dark slate
FG = (248, 250, 252)        # #F8FAFC off-white

os.makedirs(os.path.dirname(OUT), exist_ok=True)


def font_for(size):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, int(size * 0.62))
    return ImageFont.load_default()


def make(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded-square vertical gradient
    r = size * 0.22
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG_TOP)
    for y in range(size):
        t = y / (size - 1)
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (size - 1, y)], fill=color + (255,))
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, outline=FG + (70,), width=max(1, size // 32))
    # centred "简" glyph
    f = font_for(size)
    bbox = d.textbbox((0, 0), "简", font=f)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pos = ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1] - size * 0.02)
    d.text(pos, "简", font=f, fill=FG)
    return img


imgs = [make(s) for s in SIZES]
imgs[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
print("saved", OUT)
