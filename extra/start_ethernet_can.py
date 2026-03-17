#!/usr/bin/env python3

import argparse
import configparser
import os
import subprocess
import sys

from pathlib import Path

# "magic constants" - most used only once, but named for clarity
MTU = 72
BUS_COUNT = 6
BUS_PREFIX = "bus"

# Env config
DEFAULT_CONFIG_DIR = Path(os.getenv("ETHERNET_CAN_CONFIGS_DIR", "/opt/voltbro/ethernet-can")).resolve()
ETHERNET_CAN_EXECUTABLE = os.getenv("ETHERNET_CAN_EXECUTABLE", "/opt/voltbro/ethernet-can/bin/ethernet-can")

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


def fail(message: str) -> None:
    journal.send(message)
    sys.exit(1)

def require(obj, *path, config_path: Path):
    current = obj
    traversed: list[str] = []

    for key in path:
        traversed.append(str(key))
        try:
            current = current[key]
        except KeyError:
            fail(f"missing {'.'.join(traversed)} in {config_path}")

    return current


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        fail(f"command failed ({result.returncode}): <{' '.join(cmd)}>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--config-dir", action="append", default=[])
    return parser.parse_args()


def discover_configs(args: argparse.Namespace) -> list[Path]:
    config_paths = [Path(path).resolve() for path in args.config]
    config_dirs = [Path(path).resolve() for path in args.config_dir]

    if not config_paths and not config_dirs:
        config_dirs.append(DEFAULT_CONFIG_DIR)

    for config_dir in config_dirs:
        if not config_dir.is_dir():
            fail(f"not a config dir: {config_dir}")
        config_paths.extend(sorted(path.resolve() for path in config_dir.glob("*.ini")))

    config_paths = sorted(set(config_paths))
    if not config_paths:
        fail("no config files found")
    return config_paths


def sync_interfaces(interfaces: list[str]) -> None:
    run(["modprobe", "vcan"])

    existing = set(os.listdir("/sys/class/net"))
    for iface in interfaces:
        if iface not in existing:
            run(["ip", "link", "add", "dev", iface, "type", "vcan"])

        run(["ip", "link", "set", iface, "mtu", str(MTU)])
        run(["ip", "link", "set", iface, "up"])


def build_executable_args(config_paths: list[Path]) -> tuple[list[str], list[str]]:
    host_ip = None
    cmd = [ETHERNET_CAN_EXECUTABLE]
    owners: dict[str, str] = {}
    boards: dict[str, str] = {}

    for config_path in config_paths:
        ini = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        if not ini.read(config_path):
            fail(f"failed to read {config_path}")

        config_host_ip = require(ini, "NETWORK_PARAMS", "Host_IP_address", config_path=config_path).strip()
        if host_ip is None:
            host_ip = config_host_ip
            cmd.extend(["--host-ip", host_ip])
        elif host_ip != config_host_ip:
            fail(f"host ip mismatch: {config_path} uses {config_host_ip}, expected {host_ip}")

        board_name = config_path.stem
        if board_name in boards:
            fail(f"duplicate board name <{board_name}>: <{config_path}> and <{boards[board_name]}>")
        boards[board_name] = str(config_path)

        cmd.extend(
            [
                "--board",
                board_name,
                "--device-ip",
                require(ini, "NETWORK_PARAMS", "Device_IP_address", config_path=config_path).strip(),
                "--period",
                require(ini, "DATA_ACQUIZITION", "Period", config_path=config_path).strip(),
                "--nominal",
                require(ini, "FDCAN_PARAMS", "Nominal_baud", config_path=config_path).strip(),
                "--data",
                require(ini, "FDCAN_PARAMS", "Data_baud", config_path=config_path).strip(),
            ]
        )

        bus_error_msg = f"invalid bus name %s in {config_path}, expected {BUS_PREFIX}0...{BUS_PREFIX}{BUS_COUNT-1}"
        for bus_name in require(ini, "HOST_INTERFACE_MAP", config_path=config_path):
            if not bus_name.startswith(BUS_PREFIX):
                fail(bus_error_msg % bus_name)
            try:
                bus_num = int(bus_name.removeprefix(BUS_PREFIX))
            except ValueError:
                fail(bus_error_msg % bus_name)
            if not (0 <= bus_num < BUS_COUNT):
                fail(bus_error_msg % bus_name)

            iface = require(ini, "HOST_INTERFACE_MAP", bus_name, config_path=config_path).strip()
            if not iface:
                fail(f"empty interface name for {bus_name} in {config_path}")
            if iface in owners:
                fail(f"interface overlap: {iface} is used by both {owners[iface]} and {config_path}")
            
            owners[iface] = str(config_path)
            cmd.extend([f"--bus{bus_num}", iface])

    if host_ip is None:
        fail("no config files found")

    interfaces = sorted(owners)
    if not interfaces:
        fail("no enabled CAN interfaces found in configs")

    return cmd, interfaces


def main() -> int:
    args = parse_args()
    config_paths = discover_configs(args)
    cmd, interfaces = build_executable_args(config_paths)

    journal.send("Configs:")
    for path in config_paths:
        journal.send(f"  {path}")

    journal.send("Interfaces:")
    for iface in interfaces:
        journal.send(f"  {iface}")

    sync_interfaces(interfaces)

    journal.send("Launching:")
    journal.send(f"  {' '.join(cmd)}")

    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
