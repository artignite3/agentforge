"""Inspect the actual MP4, extract representative/consecutive frames, and measure audio."""

import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "node_modules/@remotion/compositor-win32-x64-msvc"
FFMPEG = ROOT / ".tools/ffmpeg.exe"
VIDEO = ROOT / "out/Project_Launch_Cinematic.mp4"
if not VIDEO.exists():
    VIDEO = ROOT.parents[1] / "assets/media/Project_Launch_Cinematic.mp4"
QA = ROOT / "out/qa"
QA.mkdir(parents=True, exist_ok=True)


def run(args):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, check=True)


probe = json.loads(
    run(
        [BIN / "ffprobe.exe", "-v", "error", "-show_format", "-show_streams", "-of", "json", VIDEO]
    ).stdout
)
(QA / "metadata.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
video = next(s for s in probe["streams"] if s["codec_type"] == "video")
audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
assert (video["width"], video["height"]) == (1920, 1080)
assert video["r_frame_rate"] == "30/1" and int(video["nb_frames"]) == 1350
assert video["codec_name"] == "h264" and audio["codec_name"] == "aac"
assert abs(float(video["duration"]) - 45) < 0.001

representative = [
    0,
    30,
    78,
    126,
    194,
    210,
    270,
    360,
    449,
    490,
    574,
    634,
    699,
    750,
    779,
    824,
    874,
    915,
    990,
    1060,
    1109,
    1165,
    1240,
    1349,
]
boundaries = [210, 450, 780, 1110]
consecutive = [b + delta for b in boundaries for delta in range(-3, 4)]
allframes = sorted(set(representative + consecutive + [94, 95, 96, 1197, 1206, 1236]))
frame_dir = QA / "frames"
frame_dir.mkdir(exist_ok=True)
selection = "+".join(f"eq(n\\,{frame})" for frame in allframes)
run(
    [
        FFMPEG,
        "-y",
        "-v",
        "error",
        "-threads",
        "2",
        "-i",
        VIDEO,
        "-filter_threads",
        "1",
        "-vf",
        f"select={selection}",
        "-vsync",
        "0",
        "-threads",
        "2",
        frame_dir / "capture-%03d.png",
    ]
)
for index, frame in enumerate(allframes):
    (frame_dir / f"capture-{index + 1:03}.png").replace(frame_dir / f"frame-{frame:04}.png")

font_path = "C:/Windows/Fonts/consola.ttf"
font = ImageFont.truetype(font_path, 18)


def sheet(frames, columns, tile_width, filename, title):
    tile_height = round(tile_width * 9 / 16)
    row_height = tile_height + 32
    rows = (len(frames) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * tile_width, rows * row_height + 56), "#0B0F17")
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 15), title, font=font, fill="#EBBC9D")
    for i, frame in enumerate(frames):
        x = (i % columns) * tile_width
        y = (i // columns) * row_height + 56
        canvas.paste(
            Image.open(frame_dir / f"frame-{frame:04}.png").resize((tile_width, tile_height)),
            (x, y),
        )
        draw.text(
            (x + 12, y + tile_height + 5),
            f"F {frame:04} / {frame / 30:05.2f}s",
            font=font,
            fill="#94A3B8",
        )
    canvas.save(ROOT / "out" / filename, quality=96)


sheet(
    representative, 4, 480, "Contact_Sheet.jpg", "AGENTFORGE / ACTUAL MP4 / REPRESENTATIVE FRAMES"
)
sheet(
    consecutive,
    7,
    300,
    "Transition_Contact_Sheet.jpg",
    "SCENE BOUNDARIES / SEVEN CONSECUTIVE EXPORTED FRAMES EACH",
)
black = run(
    [
        FFMPEG,
        "-hide_banner",
        "-threads",
        "2",
        "-i",
        VIDEO,
        "-filter_threads",
        "1",
        "-vf",
        "blackdetect=d=0.03:pix_th=0.02:pic_th=0.99",
        "-an",
        "-f",
        "null",
        "-",
    ]
).stderr
(QA / "black-frame-scan.log").write_text(black, encoding="utf-8")
assert "black_start:" not in black
levels = run(
    [
        FFMPEG,
        "-hide_banner",
        "-threads",
        "2",
        "-i",
        VIDEO,
        "-af",
        "loudnorm=I=-16:TP=-1:LRA=8:print_format=json",
        "-vn",
        "-f",
        "null",
        "-",
    ]
).stderr
(QA / "exported-audio-levels.log").write_text(levels, encoding="utf-8")
level_json = json.loads(levels[levels.rfind("{") : levels.rfind("}") + 1])
decode = run([FFMPEG, "-v", "error", "-threads", "2", "-i", VIDEO, "-f", "null", "-"]).stderr
(QA / "decode-errors.log").write_text(decode, encoding="utf-8")
assert not decode.strip()
run(
    [
        FFMPEG,
        "-y",
        "-v",
        "error",
        "-i",
        VIDEO,
        "-vn",
        "-ar",
        "48000",
        "-c:a",
        "pcm_s16le",
        QA / "exported-audio.wav",
    ]
)


def samples(path):
    with wave.open(str(path)) as w:
        return (
            np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
            .astype(np.float64)
            .reshape(-1, w.getnchannels())
            / 32768
        )


reference = samples(ROOT / "public/audio/master.wav").mean(axis=1)[::48]
decoded = samples(QA / "exported-audio.wav")
comparison = decoded.mean(axis=1)[::48]
count = min(len(reference), len(comparison))
correlation = float(np.corrcoef(reference[:count], comparison[:count])[0, 1])
assert correlation > 0.98 and np.max(np.abs(decoded)) < 0.999
summary = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "frames": 1350,
    "videoDurationSeconds": 45.0,
    "containerDurationSeconds": float(probe["format"]["duration"]),
    "videoCodec": video["codec_name"],
    "audioCodec": audio["codec_name"],
    "audioChannels": audio["channels"],
    "integratedLUFS": float(level_json["input_i"]),
    "truePeakDBTP": float(level_json["input_tp"]),
    "audioMasterCorrelation": round(correlation, 6),
    "clippedAudioSamples": 0,
    "blackIntervals": 0,
    "decodeErrors": 0,
    "representativeFrames": representative,
    "consecutiveBoundaryFrames": consecutive,
    "manualAudioListening": "Not performed: this agent environment does not accept audio input. Playback files are supplied for human audition.",
}
(QA / "verification-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
