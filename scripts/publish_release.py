"""Publish a tested tag build; advertise it only after its assets are public."""

import ast
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "interforever90/image-motion-tool"


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def app_version(source):
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "APP_VERSION"
                   for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError("Missing APP_VERSION")


def main():
    current_source = (ROOT / "image_motion_tool.py").read_text(encoding="utf-8")
    sync_notes = not os.environ["RELEASE_TAG"]
    tag = os.environ["RELEASE_TAG"] or f"v{app_version(current_source)}"
    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+)+", tag):
        raise RuntimeError("Release tag must have the form v5.15")
    version = tag[1:]
    tagged_source = command("git", "show", f"{tag}:image_motion_tool.py")
    if app_version(tagged_source) != version or app_version(current_source) != version:
        raise RuntimeError("Tag, main APP_VERSION and release version must match")
    notes = command("git", "show", f"{tag}:release-notes/{version}.md")
    executable = ROOT / "dist" / "ImageMotionTool.exe"
    if not executable.is_file() or executable.stat().st_size < 1_000_000:
        raise RuntimeError("Missing or invalid tested ImageMotionTool.exe artifact")
    notices = ROOT / "dist" / "FFmpeg-notices"
    for name in ("LICENSE.txt", "BUILD-SOURCE.txt"):
        if not (notices / name).is_file():
            raise RuntimeError(f"Missing FFmpeg notice: {name}")
    notice_zip = shutil.make_archive(str(ROOT / "dist" / "FFmpeg-notices"), "zip", notices)
    note_file = ROOT / ".build-tools" / "release-notes.md"
    note_file.parent.mkdir(exist_ok=True)
    note_file.write_text(notes, encoding="utf-8")
    view = ["gh", "release", "view", tag, "--repo", REPOSITORY,
            "--json", "isDraft,assets,tagName,body"]
    existing = subprocess.run(view, cwd=ROOT, text=True, capture_output=True)
    if existing.returncode:
        if sync_notes:
            raise RuntimeError("Cannot sync notes without an existing public release")
        command("gh", "release", "create", tag, "--repo", REPOSITORY,
                "--verify-tag", "--draft", "--title", f"Image Motion Tool V{version}",
                "--notes-file", str(note_file))
        is_draft = True
    else:
        is_draft = json.loads(existing.stdout)["isDraft"]
    if sync_notes:
        if is_draft:
            raise RuntimeError("Note synchronization cannot publish a draft release")
        notes = (ROOT / "release-notes" / f"{version}.md").read_text(encoding="utf-8")
        note_file.write_text(notes, encoding="utf-8")
        command("gh", "release", "edit", tag, "--repo", REPOSITORY,
                "--notes-file", str(note_file))
    if is_draft:
        command("gh", "release", "upload", tag, str(executable), notice_zip,
                "--repo", REPOSITORY, "--clobber")
        command("gh", "release", "edit", tag, "--repo", REPOSITORY,
                "--draft=false", "--latest")
    published = json.loads(command(*view))
    notes = published["body"]
    expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/ImageMotionTool.exe"
    assets = {asset["name"]: asset for asset in published["assets"]}
    if published["isDraft"] or published["tagName"] != tag:
        raise RuntimeError("Release is not public")
    if "ImageMotionTool.exe" not in assets or "FFmpeg-notices.zip" not in assets:
        raise RuntimeError("Release assets are incomplete")
    if assets["ImageMotionTool.exe"]["size"] < 1_000_000:
        raise RuntimeError("Published executable is too small")
    if assets["ImageMotionTool.exe"]["url"] != expected_url:
        raise RuntimeError("Unexpected release download URL")
    manifest = {
        "version": version,
        "download_url": expected_url,
        "notes": notes.strip(),
    }
    manifest_path = ROOT / "version.json"
    if json.loads(manifest_path.read_text(encoding="utf-8")) == manifest:
        print("Release and version.json already published")
        return
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    command("git", "config", "user.name", "github-actions[bot]")
    command("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    command("git", "add", "--", "version.json")
    command("git", "commit", "-m", f"release: advertise V{version} update")
    command("git", "push", "origin", "HEAD:main")
    print(f"Published V{version}: {expected_url}")


if __name__ == "__main__":
    main()
