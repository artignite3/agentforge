"""Frame-aligned voice, original score and Foley. Requires numpy and bundled FFmpeg."""

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe"
RATE = 48000
LENGTH = RATE * 45
WORK = ROOT / "work/audio"
RAW = WORK / "raw"
OUT = ROOT / "public/audio"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)


def read(path):
    with wave.open(str(path)) as wav:
        return (
            np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768
        )


def write(path, signal):
    signal = np.clip(signal, -0.999, 0.999)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1 if signal.ndim == 1 else 2)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes((signal * 32767).astype("<i2").tobytes())


def trim(signal):
    hits = np.flatnonzero(np.abs(signal) > 0.005)
    if not len(hits):
        raise RuntimeError("Empty voice phrase")
    start = max(0, hits[0] - int(0.035 * RATE))
    end = min(len(signal), hits[-1] + int(0.08 * RATE))
    signal = signal[start:end].copy()
    edge = min(300, len(signal) // 20)
    signal[:edge] *= np.linspace(0, 1, edge)
    signal[-edge:] *= np.linspace(1, 0, edge)
    return signal


story = json.loads((ROOT / "creative/storyboard.json").read_text(encoding="utf-8-sig"))
manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8-sig"))
voice = np.zeros(LENGTH)
cues = []
for scene in story["scenes"]:
    phrases = [x for x in manifest if x["scene"] == scene["id"]]
    clips = [trim(read(RAW / x["file"])) for x in phrases]
    start, end = scene["speech"]
    gap = 0.115
    allowance = (end - start) / 30 - gap * (len(clips) - 1)
    tempo = max(1.0, sum(len(x) / RATE for x in clips) / allowance)
    cursor = int(start / 30 * RATE)
    for phrase, clip in zip(phrases, clips, strict=True):
        temp = RAW / ("trim-" + phrase["file"])
        processed = RAW / ("fit-" + phrase["file"])
        write(temp, clip)
        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(temp),
                "-af",
                f"atempo={tempo:.8f}",
                str(processed),
            ],
            check=True,
        )
        clip = read(processed)
        clip *= 0.56 / max(0.01, float(np.max(np.abs(clip))))
        voice[cursor : cursor + len(clip)] += clip
        cues.append(
            {
                "scene": scene["id"],
                "phrase": phrase["phrase"],
                "text": phrase["text"],
                "startFrame": round(cursor / RATE * 30),
                "endFrame": round((cursor + len(clip)) / RATE * 30),
                "tempo": round(tempo, 4),
            }
        )
        cursor += len(clip) + int(gap * RATE)

write(OUT / "narration.wav", voice)
(ROOT / "creative/narration-timing.json").write_text(json.dumps(cues, indent=2), encoding="utf-8")

# Original minimalist tonal score. No sampled recordings or third-party music.
t = np.arange(LENGTH) / RATE
score = np.zeros((LENGTH, 2))
fade = np.minimum(t / 1.8, 1) * np.minimum((45 - t) / 1.1, 1)
duck = 1 - 0.54 * np.minimum(
    np.convolve((np.abs(voice[::480]) > 0.018).astype(float), np.ones(24) / 24, mode="same").repeat(
        480
    )[:LENGTH],
    1,
)
for frequency, amplitude in [
    (55, 0.026),
    (110, 0.01),
    (164.8138, 0.010),
    (220, 0.009),
    (329.6276, 0.006),
]:
    wavelet = np.sin(2 * np.pi * frequency * t + 0.2 * np.sin(2 * np.pi * 0.13 * t))
    slow = 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t + frequency)
    score[:, 0] += amplitude * wavelet * slow
    score[:, 1] += amplitude * np.sin(2 * np.pi * frequency * t + 0.12) * slow
score *= fade[:, None] * duck[:, None]
rng = np.random.default_rng(4261312)


def sound(frame, duration, kind="tick", gain=0.05, pan=0):
    n = int(duration * RATE)
    tt = np.arange(n) / RATE
    if kind == "impact":
        tone = np.sin(2 * np.pi * (68 * tt + 35 * (1 - np.exp(-9 * tt)) / 9))
        signal = tone * np.exp(-tt * 6) + 0.09 * rng.normal(size=n) * np.exp(-tt * 30)
    elif kind == "whoosh":
        noise = rng.normal(size=n)
        smoothed = np.convolve(noise, np.ones(23) / 23, mode="same")
        signal = smoothed * np.sin(np.pi * np.minimum(tt / duration, 1)) ** 2
    elif kind == "riser":
        signal = (
            np.sin(2 * np.pi * (130 * tt + 240 * tt**2)) * np.sin(np.pi * tt / duration) ** 2 * 0.3
        )
    else:
        signal = (np.sin(2 * np.pi * 1250 * tt) + 0.4 * np.sin(2 * np.pi * 2500 * tt)) * np.exp(
            -tt * 55
        )
    signal *= gain
    offset = round(frame / 30 * RATE)
    length = min(n, LENGTH - offset)
    score[offset : offset + length, 0] += signal[:length] * (1 - pan) * 0.75
    score[offset : offset + length, 1] += signal[:length] * (1 + pan) * 0.75


crash = next(x for x in cues if x["scene"] == 1 and x["phrase"] == 1)["startFrame"] + 22
sound(crash, 0.65, "impact", 0.11)
sound(182, 0.95, "riser", 0.026)
sound(258, 0.9, "impact", 0.095)
sound(418, 0.92, "whoosh", 0.11, pan=0.2)
for frame in [522, 597, 651, 716, 834, 919, 989, 1040]:
    sound(frame, 0.12, "tick", 0.026, pan=(-0.15 if frame % 2 else 0.15))
sound(761, 0.55, "whoosh", 0.08, pan=-0.25)
sound(1098, 0.65, "whoosh", 0.06)
sound(1140, 1.2, "impact", 0.08)
for frame, freq in [(1288, 220), (1294, 329.6276)]:
    n = int(1.8 * RATE)
    tt = np.arange(n) / RATE
    sig = 0.034 * np.sin(2 * np.pi * freq * tt) * np.minimum(tt / 0.018, 1) * np.exp(-tt * 2.5)
    off = round(frame / 30 * RATE)
    count = min(n, LENGTH - off)
    score[off : off + count] += sig[:count, None]
write(OUT / "score-and-sfx.wav", score)
mix = score + voice[:, None]
write(WORK / "mix-unmastered.wav", mix)
cmd = [
    str(FFMPEG),
    "-y",
    "-hide_banner",
    "-i",
    str(WORK / "mix-unmastered.wav"),
    "-af",
    "loudnorm=I=-16:TP=-1:LRA=8:print_format=json,volume=-0.35dB",
    "-ar",
    str(RATE),
    "-c:a",
    "pcm_s16le",
    str(OUT / "master.wav"),
]
result = subprocess.run(cmd, capture_output=True, text=True, check=True)
(WORK / "mastering.log").write_text(result.stderr, encoding="utf-8")


def timestamp(fr):
    ms = round(fr / 30 * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


(ROOT / "creative/narration.srt").write_text(
    "\n\n".join(
        f"{i + 1}\n{timestamp(x['startFrame'])} --> {timestamp(x['endFrame'])}\n{x['text']}"
        for i, x in enumerate(cues)
    )
    + "\n",
    encoding="utf-8",
)
print(
    json.dumps(
        {"phrase_cues": cues, "master": "public/audio/master.wav", "crashFrame": crash}, indent=2
    )
)
