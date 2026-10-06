"""Download the upstream static Windows GPL build and verify its SHA-256."""

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET = "ffmpeg-master-latest-win64-gpl.zip"
BASE_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"


def prepare():
    work = ROOT / ".build-tools"
    work.mkdir(exist_ok=True)
    archive = work / ASSET
    with urllib.request.urlopen(BASE_URL + "checksums.sha256", timeout=60) as response:
        checksums = response.read().decode("utf-8")
    matches = [line.split()[0] for line in checksums.splitlines()
               if len(line.split()) == 2 and line.split()[1].lstrip("*") == ASSET]
    if len(matches) != 1:
        raise RuntimeError("Missing or ambiguous upstream FFmpeg checksum")
    with urllib.request.urlopen(BASE_URL + ASSET, timeout=120) as response:
        with archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != matches[0]:
        archive.unlink()
        raise RuntimeError("FFmpeg SHA-256 mismatch; refusing to use the archive")
    notices = ROOT / "dist" / "FFmpeg-notices"
    notices.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        binaries = [name for name in package.namelist() if name.endswith("/bin/ffmpeg.exe")]
        if len(binaries) != 1:
            raise RuntimeError("Expected exactly one static ffmpeg.exe")
        if not any(Path(name).name == "LICENSE.txt" for name in package.namelist()):
            raise RuntimeError("Missing upstream FFmpeg license")
        with package.open(binaries[0]) as source, (ROOT / "ffmpeg.exe").open("wb") as output:
            shutil.copyfileobj(source, output)
        for name in package.namelist():
            if Path(name).name in ("LICENSE.txt", "README.txt", "README.md"):
                (notices / Path(name).name).write_bytes(package.read(name))
    (notices / "BUILD-SOURCE.txt").write_text(
        f"Download: {BASE_URL}{ASSET}\nSHA-256: {digest}\n"
        "Build recipes and source references: https://github.com/BtbN/FFmpeg-Builds\n"
        "FFmpeg source: https://ffmpeg.org/download.html\n",
        encoding="utf-8",
    )
    print(f"Verified FFmpeg SHA-256: {digest}")


if __name__ == "__main__":
    prepare()
