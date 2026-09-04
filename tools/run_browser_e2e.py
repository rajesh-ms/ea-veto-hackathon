"""Drive and record all three browser demo scenarios against the real local API."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_server(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Local API exited before becoming ready: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.15)
    raise RuntimeError("Local API did not become ready within 25 seconds")


def run_scenario(page: Page, button: str, completion: str) -> str:
    page.get_by_test_id(button).click()
    marker = page.get_by_test_id(completion)
    marker.wait_for(state="visible", timeout=45_000)
    text = marker.inner_text()
    if "validated" not in text.lower():
        raise AssertionError(f"Scenario marker did not validate: {text}")
    return text


def record(output: Path) -> dict[str, object]:
    resolved_root = ROOT.resolve()
    output = output.resolve()
    if not output.is_relative_to(resolved_root):
        raise ValueError("Recording output must remain inside the repository")
    output.parent.mkdir(parents=True, exist_ok=True)
    port = available_port()
    url = f"http://127.0.0.1:{port}"
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ea_copilot.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=resolved_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    try:
        wait_for_server(f"{url}/health", process)
        with tempfile.TemporaryDirectory(prefix="ea-copilot-video-") as video_dir:
            with sync_playwright() as playwright:
                try:
                    browser = playwright.chromium.launch(headless=True)
                except PlaywrightError:
                    browser = playwright.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    record_video_dir=video_dir,
                    record_video_size={"width": 1440, "height": 900},
                    color_scheme="light",
                )
                page = context.new_page()
                console_errors: list[str] = []
                gate_conflicts: list[str] = []
                page.on(
                    "console",
                    lambda message: (
                        console_errors.append(message.text) if message.type == "error" else None
                    ),
                )
                page.on(
                    "response",
                    lambda response: (
                        gate_conflicts.append(response.url)
                        if response.status == 409 and response.url.endswith("/draft")
                        else None
                    ),
                )
                page.goto(f"{url}/demo?record=1", wait_until="networkidle")
                page.wait_for_timeout(900)
                markers = [run_scenario(page, "run-s1", "scenario-1-complete")]
                page.get_by_test_id("draft-created-marker").wait_for(state="visible")
                page.get_by_test_id("calendar-lane-exec-a").wait_for(state="visible")
                page.get_by_test_id("calendar-lane-exec-b").wait_for(state="visible")

                markers.append(run_scenario(page, "run-s2", "scenario-2-complete"))
                assert page.get_by_test_id("calendar-lane-exec-a").inner_text()
                assert page.get_by_test_id("calendar-lane-exec-b").inner_text()

                markers.append(run_scenario(page, "run-s3", "scenario-3-complete"))
                page.get_by_test_id("memory-summary").last.wait_for(state="visible")
                page.get_by_test_id("candidate-inert-marker").wait_for(state="visible")
                page.get_by_test_id("profile-version-change").wait_for(state="visible")
                page.screenshot(
                    path=str(output.with_name("ea-copilot-demo-final.png")),
                    full_page=True,
                )
                video = page.video
                page.close()
                context.close()
                browser.close()
                if video is None:
                    raise RuntimeError("Playwright did not attach a video recorder")
                source = Path(video.path())
                staged = output.with_suffix(".staged.webm")
                shutil.copyfile(source, staged)
                os.replace(staged, output)
                if len(gate_conflicts) != 1:
                    raise RuntimeError(
                        f"Expected one pre-approval draft conflict, observed {gate_conflicts}"
                    )
                unexpected_errors = [
                    message for message in console_errors if "409 (Conflict)" not in message
                ]
                if unexpected_errors:
                    raise RuntimeError(f"Browser console errors: {unexpected_errors}")
        return {"output": str(output), "bytes": output.stat().st_size, "markers": markers}
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(record(args.record), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
