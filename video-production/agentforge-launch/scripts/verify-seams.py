"""Inspect the actual joined video around every internal five-second render join."""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
video = ROOT / "out/Project_Launch_Cinematic.mp4"
if not video.exists():
    video = ROOT.parents[1] / "assets/media/Project_Launch_Cinematic.mp4"
frames = [b + d for b in range(150, 1350, 150) for d in [-1, 0, 1]]
folder = ROOT / "out/qa/seams"
folder.mkdir(parents=True, exist_ok=True)
selection = "+".join(f"eq(n\\,{frame})" for frame in frames)
subprocess.run(
    [
        str(ROOT / ".tools/ffmpeg.exe"),
        "-y",
        "-v",
        "error",
        "-threads",
        "2",
        "-i",
        str(video),
        "-filter_threads",
        "1",
        "-vf",
        f"select={selection}",
        "-vsync",
        "0",
        "-threads",
        "2",
        str(folder / "capture-%03d.png"),
    ],
    check=True,
)
canvas = Image.new("RGB", (1800, 8 * 367 + 56), "#0B0F17")
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 18)
draw.text(
    (18, 15), "RENDER SECTION JOINS / PREVIOUS, BOUNDARY, NEXT FRAME", font=font, fill="#EBBC9D"
)
for i, frame in enumerate(frames):
    x = i % 3 * 600
    y = i // 3 * 367 + 56
    canvas.paste(Image.open(folder / f"capture-{i + 1:03}.png").resize((600, 337)), (x, y))
    draw.text((x + 12, y + 343), f"F {frame:04} / {frame / 30:.2f}s", font=font, fill="#94A3B8")
canvas.save(ROOT / "out/Render_Join_Contact_Sheet.jpg", quality=96)
print("Extracted 24 consecutive frames around all eight render joins.")
