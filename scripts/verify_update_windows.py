"""Exercise the unchanged V5.14 updater with real released Windows executables.

The original GUI is closed by the harness when the legacy updater requests exit.
No UI clicks, rendering changes or modifications to the old BAT are performed.
"""

import ast
import hashlib
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
import traceback
from pathlib import Path
from types import SimpleNamespace

from smoke_windows import application_window_exists

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "91b75df"
MANIFEST_URL = "https://raw.githubusercontent.com/interforever90/image-motion-tool/main/version.json"
OLD_URL = "https://github.com/interforever90/image-motion-tool/releases/download/v5.14/ImageMotionTool_V5_14.exe"


def report(text):
    print(text, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write(text + "\n\n")


def probe_cmd_endings(directory):
    for label, ending in (("CR-only legacy", "\r"), ("CRLF", "\r\n")):
        script = directory / "probe.bat"
        script.write_bytes(ending.join([
            "@echo off", "echo LINE_ONE", "echo LINE_TWO", "exit /b 0", "",
        ]).encode("ascii"))
        result = subprocess.run(["cmd", "/d", "/c", str(script)],
                                capture_output=True, text=True, timeout=10)
        report(f"CMD probe {label}: exit {result.returncode}; "
               f"stdout={result.stdout!r}; stderr={result.stderr!r}")


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def stop(process):
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True)
        process.wait(timeout=30)


def main():
    if os.name != "nt":
        raise RuntimeError("The legacy updater verification requires Windows")
    socket.setdefaulttimeout(90)
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE}:image_motion_tool.py"], cwd=ROOT, text=True,
        encoding="utf-8",
    )
    cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in ("_version_tuple", "check_update", "apply_update")]
    assert len(methods) == 3, "Missing legacy updater methods"
    legacy_cls = ast.ClassDef(name="LegacyUpdater", bases=[], keywords=[], body=methods,
                              decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[legacy_cls], type_ignores=[]))
    with tempfile.TemporaryDirectory(prefix="imt-upgrade-") as directory:
        work = Path(directory)
        probe_cmd_endings(work)
        installed = work / "ImageMotionTool.exe"
        urllib.request.urlretrieve(OLD_URL, installed)
        original_hash = digest(installed)
        old = subprocess.Popen([str(installed)], cwd=work)
        errors = []
        updater_threads = []

        def start_thread(*args, **kwargs):
            thread = threading.Thread(*args, **kwargs)
            updater_threads.append(thread)
            return thread

        def after(delay, callback):
            if delay:
                time.sleep(delay / 1000)
            callback()

        namespace = {
            "APP_VERSION": "5.14", "VERSION_URL": MANIFEST_URL,
            "Path": Path, "urllib": urllib,
            "sys": SimpleNamespace(executable=str(installed)),
            "tempfile": SimpleNamespace(gettempdir=lambda: str(work)),
            "subprocess": subprocess,
            "threading": SimpleNamespace(Thread=start_thread),
            "messagebox": SimpleNamespace(
                askyesno=lambda *args: True,
                showerror=lambda title, message: errors.append(f"{title}: {message}"),
                showinfo=lambda title, message: errors.append(f"{title}: {message}"),
            ),
        }
        try:
            deadline = time.monotonic() + 90
            while not application_window_exists("5.14"):
                if old.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Original released V5.14 GUI did not start")
                time.sleep(0.5)
            report("Released V5.14 GUI started successfully")
            exec(compile(module, "legacy-v5.14-updater", "exec"), namespace)
            updater = namespace["LegacyUpdater"]()
            updater.root = SimpleNamespace(after=after, destroy=lambda: stop(old))
            updater.check_update()
            report("Original baseline updater started")
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                if errors:
                    raise RuntimeError("Legacy updater failed: " + "; ".join(errors))
                if application_window_exists("5.15") and digest(installed) != original_hash:
                    new_copy = work / "ImageMotionToolUpdater" / "ImageMotionTool_NEW.exe"
                    assert not new_copy.exists(), "Update download was not moved into place"
                    print("PASS: released V5.14 started; original updater downloaded the public "
                          "V5.15 asset, replaced the EXE and restarted the V5.15 GUI")
                    break
                time.sleep(1)
            else:
                bat = work / "ImageMotionTool_apply_update.bat"
                endings = "missing BAT" if not bat.exists() else repr(bat.read_bytes()[-100:])
                new_copy = work / "ImageMotionToolUpdater" / "ImageMotionTool_NEW.exe"
                report(f"Old process exit: {old.poll()}; installed changed: "
                       f"{digest(installed) != original_hash}; download remains: {new_copy.exists()}")
                raise RuntimeError("Legacy V5.14 updater did not restart V5.15; BAT tail: " + endings)
        finally:
            for thread in updater_threads:
                thread.join(timeout=100)
            stop(old)
            # Only this harness launches an application of this name on this runner.
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
