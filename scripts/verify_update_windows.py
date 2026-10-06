"""Test updater methods extracted from actual released Windows executables.

Dialogs and GUI closure are simulated; the packaged updater and BAT stay intact.
"""
import hashlib
import json
import marshal
import os
import queue
import shutil
import subprocess
import tempfile
import time
import traceback
import types
import urllib.request
from pathlib import Path
from unittest.mock import patch

from PyInstaller.archive.readers import CArchiveReader
from smoke_windows import application_window_exists

OLD_URL = "https://github.com/interforever90/image-motion-tool/releases/download/v5.14/ImageMotionTool_V5_14.exe"
NEW_URL = "https://github.com/interforever90/image-motion-tool/releases/download/v5.15/ImageMotionTool.exe"


def report(text):
    print(text, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write(text + "\n\n")


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def stop(process):
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True)
        process.wait(timeout=30)


def packaged_methods(executable):
    archive = CArchiveReader(str(executable))
    if "python312.dll" not in archive.toc:
        raise RuntimeError("Inspection requires the packaged Python 3.12 format")
    entries = [name for name, entry in archive.toc.items()
               if entry[-1] == "s" and name.startswith("image_motion_tool")]
    assert len(entries) == 1, "Ambiguous application script"
    module = marshal.loads(archive.extract(entries[0]))
    methods = {}

    def visit(code):
        methods[code.co_name] = code
        for constant in code.co_consts:
            if isinstance(constant, types.CodeType):
                visit(constant)

    visit(module)
    return methods


def wait_for_upgrade(installed, old_hash, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if application_window_exists("5.15") and digest(installed) != old_hash:
            return True
        time.sleep(0.5)
    return False


def main():
    if os.name != "nt":
        raise RuntimeError("Updater verification requires Windows")
    with tempfile.TemporaryDirectory(prefix="imt-upgrade-") as directory:
        work = Path(directory)
        installed = work / "ImageMotionTool.exe"
        with urllib.request.urlopen(OLD_URL, timeout=90) as response, installed.open("wb") as output:
            shutil.copyfileobj(response, output)
        old_hash = digest(installed)
        original = packaged_methods(installed)
        old = subprocess.Popen([str(installed)], cwd=work)
        events = queue.Queue()

        def after(delay, callback):
            time.sleep(delay / 1000)
            callback()

        app = types.SimpleNamespace(q=events, root=types.SimpleNamespace(
            after=after, destroy=lambda: stop(old)))
        namespace = {
            "Path": Path, "urllib": urllib, "json": json, "shutil": shutil,
            "sys": types.SimpleNamespace(frozen=True, executable=str(installed)),
        }

        def original_method(name, *args):
            return types.FunctionType(original[name], namespace)(app, *args)

        try:
            deadline = time.monotonic() + 90
            while not application_window_exists("5.14"):
                if old.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Released V5.14 GUI did not start")
                time.sleep(0.5)
            report("Released V5.14 GUI started successfully")
            with patch.object(tempfile, "tempdir", str(work)):
                original_method("_check_updates_worker")
                event, manifest = events.get(timeout=10)
                assert event == "updatecheck", (event, manifest)
                assert manifest["version"] == "5.15" and manifest["download_url"] == NEW_URL
                original_method("_download_update_worker", manifest["download_url"])
                event, paths = events.get(timeout=10)
                assert event == "autoupdateready", (event, paths)
                current, staged_name = paths
                staged = Path(staged_name)
                new_hash = digest(staged)
                new_methods = packaged_methods(staged)
                report("::notice::Actual V5.14 updater read the public manifest and downloaded V5.15")
                commands = []
                real_popen = subprocess.Popen

                def capture_popen(args, **kwargs):
                    if args[0].lower() == "cmd.exe":
                        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        process = real_popen(args, **kwargs)
                        commands.append(process)
                        return process
                    return real_popen(args, **kwargs)

                with patch.object(subprocess, "Popen", capture_popen):
                    original_method("_launch_auto_replace", current, staged_name)
                assert len(commands) == 1, "Missing original BAT process"
                stdout, stderr = commands[0].communicate(timeout=45)
                legacy_ok = wait_for_upgrade(installed, old_hash, 10)
                if legacy_ok:
                    assert digest(installed) == new_hash
                    report("PASS: actual released V5.14 updater replaced the EXE and restarted V5.15")
                    return
                contents = (work / "ImageMotionTool_apply_update.bat").read_bytes()
                cr_only = b"\r" in contents and b"\n" not in contents
                report(f"::warning::Actual V5.14 BAT failed: CR-only={cr_only}, "
                       f"exit={commands[0].returncode}, download remains={staged.exists()}, "
                       f"installed unchanged={digest(installed) == old_hash}, "
                       f"stdout={stdout!r}, stderr={stderr!r}")
                assert staged.exists(), "Downloaded EXE missing after legacy failure"
                assert digest(installed) == old_hash, "Legacy updater partially replaced the EXE"
                fixed_namespace = dict(namespace, subprocess=subprocess, tempfile=tempfile,
                    messagebox=types.SimpleNamespace(askyesno=lambda *args: True))
                types.FunctionType(new_methods["apply_update"], fixed_namespace)(app, staged)
                assert wait_for_upgrade(installed, old_hash, 30), "V5.15 CRLF updater failed"
                assert digest(installed) == new_hash, "Updated executable differs from public V5.15"
                report("::notice::PASS: actual V5.15 CRLF updater replaced the identical downloaded "
                       "EXE and restarted the V5.15 GUI")
                raise RuntimeError("Released V5.14 cannot complete the automatic upgrade with its "
                                   "CR-only BAT. The V5.15 CRLF updater control passed. "
                                   "A one-time manual installation of V5.15 is required.")
        finally:
            stop(old)
            subprocess.run(["taskkill", "/IM", "ImageMotionTool.exe", "/T", "/F"],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        report(f"::error::{type(error).__name__}: {error}")
        report("```text\n" + traceback.format_exc() + "```")
        raise
