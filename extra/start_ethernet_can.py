#!/usr/bin/env python3

import time
import os
import sys
import signal
import subprocess
import threading

from pathlib import Path
from typing import List

START_DELAY = 10
RESTART_DELAY = 2
PROCESS_STATE_POLL_DELAY = 1
WORKING_DIR = Path(os.getenv("ETHERNET_CAN_CONFIGS_DIR",  "/opt/voltbro/ethernet-can")).resolve().absolute()
ETHERNET_CAN_EXECUTABLE = os.getenv("ETHERNET_CAN_EXECUTABLE", "/opt/voltbro/ethernet-can/bin/ethernet-can")

STOP_REQUESTED = False

USE_SYSTEMD_JOURNAL = os.getppid() == 1
if USE_SYSTEMD_JOURNAL:
    try:
        from systemd import journal
    except ImportError:
        USE_SYSTEMD_JOURNAL = False
if not USE_SYSTEMD_JOURNAL:
    class BogusJournal:
        def send(self, msg, *args, **kwargs):
            extra = ""
            if args:
                extra += " "
                extra += " ".join(map(str, args))
            if kwargs:
                extra += " "
                extra += " ".join(f"{k}={v}" for k, v in kwargs.items())
            print(f"{msg}{extra}")

    journal = BogusJournal()


def handle_signal(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    journal.send(f"Received signal {signum}, shutting down...")


def setup_vcan() -> bool:
    journal.send("Setting up VCAN interfaces")
    journal.send("Loading vcan kernel module...")
    retcode = subprocess.call(["modprobe", "vcan"])
    if retcode != 0:
        journal.send("Failed to load vcan kernel module", RETCODE=retcode)
        return False

    VCAN_INTERFACES: set[str] = {"vcan0", "vcan1", "vcan2", "vcan3", "vcan4"}
    MTU = 72

    existing_ifaces = set(os.listdir('/sys/class/net/'))
    existing_vcan_ifaces = VCAN_INTERFACES.intersection(existing_ifaces)

    journal.send(f"Existing vcan ifaces: {existing_vcan_ifaces}")

    for iface in VCAN_INTERFACES:
        if iface not in existing_ifaces:
            journal.send(f"Creating {iface}...")
            retcode = subprocess.call(["ip", "link", "add", "dev", iface, "type", "vcan"])
            if retcode != 0:
                journal.send(f"Failed to create {iface}", RETCODE=retcode)
                return False

        journal.send(f"Configuring {iface}...")

        retcode = subprocess.call(["ip", "link", "set", iface, "mtu", str(MTU)])
        if retcode != 0:
            journal.send(f"Failed to set MTU for {iface}", RETCODE=retcode)
            return False

        retcode = subprocess.call(["ip", "link", "set", iface, "up"])
        if retcode != 0:
            journal.send(f"Failed to bring {iface} up", RETCODE=retcode)
            return False

    journal.send("All VCAN interfaces configured successfully")
    return True


def stream_process_output(config: Path, proc: subprocess.Popen):
    stdout = proc.stdout
    if stdout is None:
        return

    try:
        for line in stdout:
            journal.send(f"[{config}] {line.rstrip()}")
    except Exception as e:
        journal.send(f"Logging thread for {config} failed: {e}")
    finally:
        try:
            stdout.close()
        except Exception:
            pass
        journal.send(f"Logging thread for {config} exited")


def start_process(config):
    journal.send(f"Starting EthernetCAN host process for {config}")
    try:
        proc = subprocess.Popen(
            [ETHERNET_CAN_EXECUTABLE, "--config", str(config)],
            cwd=WORKING_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        t = threading.Thread(
            target=stream_process_output,
            args=(config, proc),
            daemon=True,
        )
        t.start()
        return proc
    except OSError as e:
        journal.send(f"Failed to start process for <{config}>: {e}")
        return None



def get_configs(directory: Path) -> List[Path]:
    if not directory.is_dir():
        raise ValueError(f"{directory} is not a valid directory")
    return list(directory.glob("*.ini"))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    journal.send("Starting VCAN configuration")
    success = setup_vcan()
    if not success:
        journal.send("Failed during VCAN configuration")
        sys.exit(1)
    else:
        journal.send("VCAN configuration completed successfully")

    journal.send(f"Sleeping for {START_DELAY} seconds")
    time.sleep(START_DELAY)

    configs = get_configs(WORKING_DIR)
    if not configs:
        journal.send(f"No configs found in {WORKING_DIR}!")
        sys.exit(1)
    journal.send(f"Will start EthernetCAN with configs: {list(map(str, configs))}")
    processes = [(config, start_process(config)) for config in configs]

    while not STOP_REQUESTED:
        for i, (config, proc) in enumerate(processes):
            if proc is None:
                journal.send(f"Process for <{config}> is not running; retrying in {RESTART_DELAY}s")
                time.sleep(RESTART_DELAY)
                processes[i] = (config, start_process(config))
                continue

            if proc.poll() is not None:
                journal.send(
                    f"Process for <{config}> exited with code {proc.returncode}. Restarting in {RESTART_DELAY}s..."
                )
                time.sleep(RESTART_DELAY)
                processes[i] = (config, start_process(config))

        time.sleep(PROCESS_STATE_POLL_DELAY)

    journal.send("Stopping child processes...")
    for config, proc in processes:
        if proc is not None and proc.poll() is None:
            journal.send(f"Terminating process for <{config}>")
            proc.terminate()

    for config, proc in processes:
        if proc is not None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                journal.send(f"Killing unresponsive process for <{config}>")
                proc.kill()

    journal.send("Shutdown complete")
