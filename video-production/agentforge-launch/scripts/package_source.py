"""Package the standalone film source and assets, excluding installed tools and renders."""

import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "out/AgentForge_Launch_Source.zip"
excluded = {"node_modules", ".remotion", ".tools", "out", "work", "__pycache__"}
roots = ["src", "creative", "public", "licenses", "scripts"]
files = [
    ROOT / name
    for name in [
        ".gitignore",
        "README.md",
        "package.json",
        "package-lock.json",
        "remotion.config.ts",
        "tsconfig.json",
    ]
]
files += [path for name in roots for path in (ROOT / name).rglob("*") if path.is_file()]
files = sorted(
    path for path in files if not any(part in excluded for part in path.relative_to(ROOT).parts)
)
ignore = subprocess.run(
    ["git", "check-ignore", "--no-index", "--stdin", "-z"],
    cwd=ROOT,
    input=b"\0".join(str(path.relative_to(ROOT)).encode() for path in files) + b"\0",
    capture_output=True,
    check=False,
)
if ignore.returncode not in {0, 1}:
    raise RuntimeError("Package from a Git checkout so its ignore rules protect private files")
ignored = {name.decode().replace("\\", "/") for name in ignore.stdout.split(b"\0") if name}
out.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(out, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
    for path in files:
        relative = path.relative_to(ROOT)
        if relative.as_posix() not in ignored:
            archive.write(path, Path("agentforge-launch") / relative)
print(f"Packaged source and assets: {out.stat().st_size:,} bytes")
