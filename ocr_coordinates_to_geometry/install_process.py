"""Cancellable pip process with a nonblocking progress loop."""

import queue
import subprocess
import threading
import time


def run_install(command, progress_callback=None, cancelled_callback=None, timeout=1200):
    # Caller supplies the QGIS Python path and fixed pip requirements. No shell
    # expansion or user-entered command text is used.
    process = subprocess.Popen(  # nosec B603
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    messages = queue.Queue()
    output = []

    def read_output():
        try:
            for line in process.stdout:
                messages.put(line)
        finally:
            messages.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    started = time.monotonic()
    try:
        while True:
            # Also pump GUI events while pip is silent (DNS, download retries).
            if progress_callback:
                progress_callback("")
            if cancelled_callback and cancelled_callback():
                return False, "Installation cancelled by user."
            if time.monotonic() - started >= timeout:
                return False, "Installation timed out.\n" + "".join(output)
            try:
                line = messages.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                break
            output.append(line)
            if progress_callback:
                progress_callback(line.strip())
        remaining = max(0.1, timeout - (time.monotonic() - started))
        # stdout may close before pip exits; retain cancellation responsiveness.
        while process.poll() is None:
            if progress_callback:
                progress_callback("")
            if cancelled_callback and cancelled_callback():
                return False, "Installation cancelled by user."
            if time.monotonic() - started >= timeout:
                return False, "Installation timed out.\n" + "".join(output)
            time.sleep(min(0.1, remaining))
        log = "".join(output)
        return process.returncode == 0, log or f"pip exit code: {process.returncode}"
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join(timeout=2)
        if not reader.is_alive():
            process.stdout.close()
