"""Acquire the full FFmpeg build needed for frame-selection and blackdetect filters."""

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".tools"
target.mkdir(exist_ok=True)
meta = json.load(urllib.request.urlopen("https://pypi.org/pypi/imageio-ffmpeg/0.6.0/json"))
wheel = next(x for x in meta["urls"] if x["filename"].endswith("win_amd64.whl"))
archive = target / wheel["filename"]
if not archive.exists():
    urllib.request.urlretrieve(wheel["url"], archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != wheel["digests"]["sha256"]:
    raise RuntimeError("QA tool download failed its SHA-256 integrity check")
with zipfile.ZipFile(archive) as z:
    executable = next(x for x in z.namelist() if x.endswith(".exe") and "ffmpeg" in x)
    (target / "ffmpeg.exe").write_bytes(z.read(executable))
    licenses = [x for x in z.namelist() if "license" in x.lower()]
    for index, name in enumerate(licenses):
        (target / f"license-{index}.txt").write_bytes(z.read(name))
(target / "provenance.json").write_text(
    json.dumps(
        {
            "package": "imageio-ffmpeg",
            "version": "0.6.0",
            "download": wheel["url"],
            "sha256": wheel["digests"]["sha256"],
        },
        indent=2,
    )
)
print("Full QA FFmpeg ready in .tools/ffmpeg.exe")
