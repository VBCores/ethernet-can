#!/usr/bin/env python3

import argparse
import configparser
import os
import subprocess
import sys
import time

from pathlib import Path

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

# "magic constants" - most used only once, but named for clarity
MTU = 72
BUS_COUNT = 6
BUS_PREFIX = "bus"
REST_TIMEOUT_SECONDS = 3.0
REST_RETRIES = 10
REST_RETRY_DELAY_SECONDS = 0.5
HEALTHCHECK_HZ = os.getenv("ETHERNET_CAN_HEALTHCHECK_HZ", "1.0")
HEALTHCHECK_MAX_FAILURES = os.getenv("ETHERNET_CAN_HEALTHCHECK_MAX_FAILURES", "3")
VALID_NOMINAL_BAUDS = {62, 125, 250, 500, 1000}
VALID_DATA_BAUDS = {0, 1000, 2000, 4000, 8000}

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


def parse_uint(value: str, label: str, config_path: Path, max_value: int = 0xFFFFFFFF) -> int:
    try:
        parsed = int(value.strip(), 10)
    except ValueError:
        fail(f"invalid {label} in {config_path}: {value}")

    if not (0 <= parsed <= max_value):
        fail(f"invalid {label} in {config_path}: {value}")
    return parsed


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


def build_executable_args(config_paths: list[Path]) -> tuple[list[str], list[str], list[dict]]:
    host_ip = None
    cmd = [ETHERNET_CAN_EXECUTABLE]
    owners: dict[str, str] = {}
    boards: dict[str, str] = {}
    rest_configs: list[dict] = []

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

        device_ip = require(ini, "NETWORK_PARAMS", "Device_IP_address", config_path=config_path).strip()
        period = parse_uint(
            require(ini, "DATA_ACQUIZITION", "Period", config_path=config_path),
            "DATA_ACQUIZITION.Period",
            config_path,
        )
        nominal_baud = parse_uint(
            require(ini, "FDCAN_PARAMS", "Nominal_baud", config_path=config_path),
            "FDCAN_PARAMS.Nominal_baud",
            config_path,
            max_value=0xFFFF,
        )
        data_baud = parse_uint(
            require(ini, "FDCAN_PARAMS", "Data_baud", config_path=config_path),
            "FDCAN_PARAMS.Data_baud",
            config_path,
            max_value=0xFFFF,
        )
        if nominal_baud not in VALID_NOMINAL_BAUDS:
            fail(f"unsupported FDCAN_PARAMS.Nominal_baud in {config_path}: {nominal_baud}")
        if data_baud not in VALID_DATA_BAUDS:
            fail(f"unsupported FDCAN_PARAMS.Data_baud in {config_path}: {data_baud}")

        cmd.extend(
            [
                "--board",
                board_name,
                "--device-ip",
                device_ip,
                "--period",
                str(period),
            ]
        )

        enabled_buses = [False] * BUS_COUNT
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
            enabled_buses[bus_num] = True
            cmd.extend([f"--bus{bus_num}", iface])

        rest_configs.append(
            {
                "name": board_name,
                "device_ip": device_ip,
                "payload": {
                    "data_plane": {
                        "host_ip": host_ip,
                    },
                    "frames_integration_period_ns": period,
                    "buses": [
                        {
                            "bus": bus,
                            "enabled": enabled_buses[bus],
                            "nominal_kbit": nominal_baud if enabled_buses[bus] else 0,
                            "data_kbit": data_baud if enabled_buses[bus] else 0,
                        }
                        for bus in range(BUS_COUNT)
                    ],
                },
            }
        )

    if host_ip is None:
        fail("no config files found")

    interfaces = sorted(owners)
    if not interfaces:
        fail("no enabled CAN interfaces found in configs")

    return cmd, interfaces, rest_configs


def configure_boards_via_rest(rest_configs: list[dict]) -> None:
    for config in rest_configs:
        configure_board_via_rest(config, fail_on_error=True)


def configure_board_via_rest(config: dict, fail_on_error: bool) -> bool:
    board_name = config["name"]
    device_ip = config["device_ip"]
    url = f"http://{device_ip}/api/v1/config"

    journal.send(f"Configuring {board_name} [{device_ip}] via REST:")
    try:
        for attempt in Retrying(
            stop=stop_after_attempt(REST_RETRIES),
            wait=wait_fixed(REST_RETRY_DELAY_SECONDS),
            retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
            reraise=True,
        ):
            with attempt:
                response = requests.put(
                    url,
                    json=config["payload"],
                    headers={"Accept": "application/json"},
                    timeout=REST_TIMEOUT_SECONDS,
                )
    except requests.RequestException as exc:
        message = f"REST config failed for {board_name} [{device_ip}]: {exc}"
        if fail_on_error:
            fail(message)
        journal.send(message)
        return False

    if response.status_code != 200:
        message = f"REST config failed for {board_name} [{device_ip}]: HTTP {response.status_code} {response.text}"
        if fail_on_error:
            fail(message)
        journal.send(message)
        return False

    journal.send(f"  HTTP {response.status_code} {response.text}")
    return True


def config_matches(desired: dict, actual: dict) -> tuple[bool, str]:
    if not isinstance(actual, dict):
        return False, "missing config object"
    if actual.get("frames_integration_period_ns") != desired["frames_integration_period_ns"]:
        return False, "frames_integration_period_ns mismatch"
    if actual.get("data_plane", {}).get("host_ip") != desired["data_plane"]["host_ip"]:
        return False, "data_plane.host_ip mismatch"

    actual_buses_by_num = {bus.get("bus"): bus for bus in actual.get("buses", []) if isinstance(bus, dict)}
    for desired_bus in desired["buses"]:
        bus_num = desired_bus["bus"]
        actual_bus = actual_buses_by_num.get(bus_num)
        if actual_bus is None:
            return False, f"bus{bus_num} missing"
        for field in ("enabled", "nominal_kbit", "data_kbit"):
            if actual_bus.get(field) != desired_bus[field]:
                return False, f"bus{bus_num}.{field} mismatch"

    return True, "ok"


def healthcheck_board(config: dict) -> tuple[bool, str]:
    board_name = config["name"]
    device_ip = config["device_ip"]
    try:
        response = requests.get(
            f"http://{device_ip}/api/v1/status",
            headers={"Accept": "application/json"},
            timeout=REST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return False, f"HTTP {response.status_code} {response.text}"
        status = response.json()
    except requests.RequestException as exc:
        return False, str(exc)
    except ValueError as exc:
        return False, f"invalid status json: {exc}"

    matches, reason = config_matches(config["payload"], status.get("config"))
    if not matches:
        return False, reason
    return True, "ok"


def run_host_with_healthcheck(cmd: list[str], rest_configs: list[dict]) -> int:
    try:
        healthcheck_hz = float(HEALTHCHECK_HZ)
    except ValueError:
        fail(f"invalid ETHERNET_CAN_HEALTHCHECK_HZ: {HEALTHCHECK_HZ}")
    try:
        max_failures = int(HEALTHCHECK_MAX_FAILURES)
    except ValueError:
        fail(f"invalid ETHERNET_CAN_HEALTHCHECK_MAX_FAILURES: {HEALTHCHECK_MAX_FAILURES}")
    if healthcheck_hz <= 0:
        fail(f"invalid ETHERNET_CAN_HEALTHCHECK_HZ: {HEALTHCHECK_HZ}")
    if max_failures < 0:
        fail(f"invalid ETHERNET_CAN_HEALTHCHECK_MAX_FAILURES: {HEALTHCHECK_MAX_FAILURES}")

    process = subprocess.Popen(cmd)
    failure_counts = {config["name"]: 0 for config in rest_configs}
    interval = 1.0 / healthcheck_hz

    try:
        while process.poll() is None:
            time.sleep(interval)
            if process.poll() is not None:
                break
            for config in rest_configs:
                board_name = config["name"]
                ok, reason = healthcheck_board(config)
                if ok:
                    if failure_counts[board_name] != 0:
                        journal.send(f"Healthcheck recovered for {board_name}")
                    failure_counts[board_name] = 0
                    continue

                failure_counts[board_name] += 1
                journal.send(
                    f"Healthcheck failed for {board_name} [{config['device_ip']}] "
                    f"({failure_counts[board_name]}/{max_failures + 1}): {reason}"
                )

                if failure_counts[board_name] > max_failures:
                    journal.send(f"Healthcheck reconfiguring {board_name} [{config['device_ip']}]: {reason}")
                    if configure_board_via_rest(config, fail_on_error=False):
                        failure_counts[board_name] = 0
    finally:
        if process.poll() is None:
            process.terminate()

    return process.returncode


def main() -> int:
    args = parse_args()
    config_paths = discover_configs(args)
    cmd, interfaces, rest_configs = build_executable_args(config_paths)

    journal.send("Configs:")
    for path in config_paths:
        journal.send(f"  {path}")

    journal.send("Interfaces:")
    for iface in interfaces:
        journal.send(f"  {iface}")

    sync_interfaces(interfaces)
    configure_boards_via_rest(rest_configs)

    journal.send("Launching:")
    journal.send(f"  {' '.join(cmd)}")

    return run_host_with_healthcheck(cmd, rest_configs)


if __name__ == "__main__":
    raise SystemExit(main())
