#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import time

from pathlib import Path

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

MTU = 72
BUS_COUNT = 6
BUS_PREFIX = "bus"
REST_TIMEOUT_SECONDS = 3.0
REST_RETRIES = 10
REST_RETRY_DELAY_SECONDS = 0.5
HEALTHCHECK_HZ = os.getenv("ETHERNET_CAN_HEALTHCHECK_HZ", "1.0")
HEALTHCHECK_MAX_FAILURES = os.getenv("ETHERNET_CAN_HEALTHCHECK_MAX_FAILURES", "3")
CONFIG_WAIT_TIMEOUT_SECONDS = os.getenv("ETHERNET_CAN_CONFIG_WAIT_TIMEOUT_SECONDS", "30")
VALID_NOMINAL_BAUDS = {62, 125, 250, 500, 1000}
VALID_DATA_BAUDS = {0, 1000, 2000, 4000, 8000}

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


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        fail(f"command failed ({result.returncode}): <{' '.join(cmd)}>")


def parse_uint(value, label: str, config_path: Path, max_value: int = 0xFFFFFFFF) -> int:
    if isinstance(value, bool):
        fail(f"invalid {label} in {config_path}: {value}")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        fail(f"invalid {label} in {config_path}: {value}")

    if not (0 <= parsed <= max_value):
        fail(f"invalid {label} in {config_path}: {value}")
    return parsed


def require_mapping(value, label: str, config_path: Path) -> dict:
    if not isinstance(value, dict):
        fail(f"missing or invalid {label} in {config_path}")
    return value


def read_alias(mapping: dict, aliases: tuple[str, ...], label: str, config_path: Path):
    for alias in aliases:
        if alias in mapping:
            return mapping[alias]
    fail(f"missing {label} in {config_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--config-dir", action="append", default=[])
    parser.add_argument("--config-wait-timeout", default=CONFIG_WAIT_TIMEOUT_SECONDS)
    return parser.parse_args()


def discover_configs(args: argparse.Namespace) -> list[Path]:
    config_paths = [Path(path).resolve() for path in args.config]
    config_dirs = [Path(path).resolve() for path in args.config_dir]

    if not config_paths and not config_dirs:
        config_dirs.append(DEFAULT_CONFIG_DIR)

    for config_dir in config_dirs:
        if not config_dir.is_dir():
            fail(f"not a config dir: {config_dir}")
        config_paths.extend(sorted(path.resolve() for path in config_dir.glob("*.json")))

    config_paths = sorted(set(config_paths))
    if not config_paths:
        fail("no JSON config files found")
    return config_paths


def sync_interfaces(interfaces: list[str]) -> None:
    run(["modprobe", "vcan"])

    existing = set(os.listdir("/sys/class/net"))
    for iface in interfaces:
        if iface not in existing:
            run(["ip", "link", "add", "dev", iface, "type", "vcan"])

        run(["ip", "link", "set", iface, "mtu", str(MTU)])
        run(["ip", "link", "set", iface, "up"])


def parse_bus_map(network: dict, config_path: Path) -> tuple[dict[int, str], list[bool]]:
    host_interface_map = require_mapping(network.get("host_interface_map"), "network.host_interface_map", config_path)
    interfaces: dict[int, str] = {}
    enabled_buses = [False] * BUS_COUNT
    bus_error_msg = f"invalid bus name %s in {config_path}, expected {BUS_PREFIX}0...{BUS_PREFIX}{BUS_COUNT-1}"

    for bus_name, iface_value in host_interface_map.items():
        if not isinstance(bus_name, str) or not bus_name.startswith(BUS_PREFIX):
            fail(bus_error_msg % bus_name)
        try:
            bus_num = int(bus_name.removeprefix(BUS_PREFIX))
        except ValueError:
            fail(bus_error_msg % bus_name)
        if not (0 <= bus_num < BUS_COUNT):
            fail(bus_error_msg % bus_name)

        iface = str(iface_value).strip()
        if not iface:
            fail(f"empty interface name for {bus_name} in {config_path}")
        interfaces[bus_num] = iface
        enabled_buses[bus_num] = True

    if not interfaces:
        fail(f"network.host_interface_map has no enabled buses in {config_path}")
    return interfaces, enabled_buses


def load_board_configs(config_paths: list[Path]) -> tuple[str, list[str], list[dict]]:
    host_ip = None
    owners: dict[str, str] = {}
    boards_by_name: dict[str, str] = {}
    devices: dict[str, str] = {}
    board_configs: list[dict] = []

    for config_path in config_paths:
        try:
            raw_config = json.loads(config_path.read_text())
        except OSError as exc:
            fail(f"failed to read {config_path}: {exc}")
        except ValueError as exc:
            fail(f"invalid JSON in {config_path}: {exc}")

        config = require_mapping(raw_config, "root object", config_path)
        extra_top_level = set(config) - {"network", "fdcan"}
        if extra_top_level:
            fail(f"unsupported top-level keys in {config_path}: {sorted(extra_top_level)}")

        network = require_mapping(config.get("network"), "network", config_path)
        board_name = config_path.stem
        if board_name in boards_by_name:
            fail(f"duplicate board name <{board_name}>: <{config_path}> and <{boards_by_name[board_name]}>")
        boards_by_name[board_name] = str(config_path)

        config_host_ip = str(read_alias(
            network,
            ("host_ip", "host_ip_address", "Host_IP_address"),
            "network.host_ip",
            config_path,
        )).strip()
        if host_ip is None:
            host_ip = config_host_ip
        elif host_ip != config_host_ip:
            fail(f"host ip mismatch: {config_path} uses {config_host_ip}, expected {host_ip}")

        device_ip = str(read_alias(
            network,
            ("device_ip", "device_ip_address", "device_address", "Device_IP_address"),
            "network.device_ip",
            config_path,
        )).strip()
        if not device_ip:
            fail(f"empty network.device_ip in {config_path}")
        if device_ip in devices:
            fail(f"duplicate device address <{device_ip}>: <{config_path}> and <{devices[device_ip]}>")
        devices[device_ip] = str(config_path)

        interfaces, enabled_buses = parse_bus_map(network, config_path)
        for iface in interfaces.values():
            if iface in owners:
                fail(f"interface overlap: {iface} is used by both {owners[iface]} and {config_path}")
            owners[iface] = str(config_path)

        board_config = {
            "name": board_name,
            "config_path": str(config_path),
            "device_ip": device_ip,
            "host_ip": config_host_ip,
            "interfaces": interfaces,
            "enabled_buses": enabled_buses,
            "managed": "fdcan" in config,
            "period": None,
            "payload": None,
        }

        if "fdcan" in config:
            fdcan = require_mapping(config["fdcan"], "fdcan", config_path)
            period = parse_uint(
                read_alias(fdcan, ("period_ns", "frames_integration_period_ns", "period"), "fdcan.period_ns", config_path),
                "fdcan.period_ns",
                config_path,
            )
            nominal_baud = parse_uint(
                read_alias(fdcan, ("nominal_kbit", "nominal_baud", "Nominal_baud"), "fdcan.nominal_kbit", config_path),
                "fdcan.nominal_kbit",
                config_path,
                max_value=0xFFFF,
            )
            data_baud = parse_uint(
                read_alias(fdcan, ("data_kbit", "data_baud", "Data_baud"), "fdcan.data_kbit", config_path),
                "fdcan.data_kbit",
                config_path,
                max_value=0xFFFF,
            )
            if period == 0:
                fail(f"invalid fdcan.period_ns in {config_path}: {period}")
            if nominal_baud not in VALID_NOMINAL_BAUDS:
                fail(f"unsupported fdcan.nominal_kbit in {config_path}: {nominal_baud}")
            if data_baud not in VALID_DATA_BAUDS:
                fail(f"unsupported fdcan.data_kbit in {config_path}: {data_baud}")

            board_config["period"] = period
            board_config["payload"] = {
                "data_plane": {
                    "host_ip": config_host_ip,
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
            }

        board_configs.append(board_config)

    if host_ip is None:
        fail("no config files found")

    return host_ip, sorted(owners), board_configs


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


def board_runtime_compatible(config: dict, actual: dict) -> tuple[bool, str, object]:
    if not isinstance(actual, dict):
        return False, "missing config object", None

    period = actual.get("frames_integration_period_ns")
    if not isinstance(period, int) or period <= 0:
        return False, "invalid frames_integration_period_ns", None

    actual_buses_by_num = {bus.get("bus"): bus for bus in actual.get("buses", []) if isinstance(bus, dict)}
    for bus_num, expected_enabled in enumerate(config["enabled_buses"]):
        actual_bus = actual_buses_by_num.get(bus_num)
        if actual_bus is None:
            return False, f"bus{bus_num} missing", None
        if bool(actual_bus.get("enabled")) != expected_enabled:
            return False, f"bus{bus_num}.enabled mismatch", None

    return True, "ok", period


def wait_for_board_runtime_config(config: dict, timeout_seconds: float) -> int:
    board_name = config["name"]
    device_ip = config["device_ip"]
    deadline = None if timeout_seconds < 0 else time.monotonic() + timeout_seconds
    last_log_at = 0.0
    last_reason = None
    journal.send(f"Waiting for board-managed config on {board_name} [{device_ip}]")

    while True:
        reason = None
        try:
            response = requests.get(
                f"http://{device_ip}/api/v1/status",
                headers={"Accept": "application/json"},
                timeout=REST_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                status = response.json()
                if status.get("fdcan", {}).get("config_applied") is True:
                    ok, reason, period = board_runtime_compatible(config, status.get("config"))
                    if ok and period is not None:
                        journal.send(f"  board config ready, period={period} ns")
                        return period
                    reason = f"board config not compatible yet: {reason}"
                else:
                    reason = "board config is not applied yet"
            else:
                reason = f"HTTP {response.status_code} {response.text}"
        except (requests.RequestException, ValueError) as exc:
            reason = f"waiting failed: {exc}"

        now = time.monotonic()
        if reason != last_reason or now - last_log_at >= 5.0:
            journal.send(f"  {reason}")
            last_reason = reason
            last_log_at = now

        if deadline is not None and time.monotonic() >= deadline:
            fail(f"timed out waiting for board-managed config on {board_name} [{device_ip}]")
        time.sleep(REST_RETRY_DELAY_SECONDS)


def configure_or_wait_for_boards(board_configs: list[dict], timeout_seconds: float) -> None:
    for config in board_configs:
        if config["managed"]:
            configure_board_via_rest(config, fail_on_error=True)
        else:
            config["period"] = wait_for_board_runtime_config(config, timeout_seconds)


def build_executable_args(host_ip: str, board_configs: list[dict]) -> list[str]:
    cmd = [ETHERNET_CAN_EXECUTABLE, "--host-ip", host_ip]

    for config in board_configs:
        if config["period"] is None:
            fail(f"internal error: missing period for {config['name']}")

        cmd.extend(
            [
                "--board",
                config["name"],
                "--device-ip",
                config["device_ip"],
                "--period",
                str(config["period"]),
            ]
        )
        for bus_num, iface in sorted(config["interfaces"].items()):
            cmd.extend([f"--bus{bus_num}", iface])

    return cmd


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

    if config["managed"]:
        matches, reason = config_matches(config["payload"], status.get("config"))
        if not matches:
            return False, reason
        return True, "ok"

    if status.get("fdcan", {}).get("config_applied") is not True:
        return False, "board config is not applied"

    ok, reason, _period = board_runtime_compatible(config, status.get("config"))
    if not ok:
        return False, reason
    return True, "ok"


def run_host_with_healthcheck(cmd: list[str], board_configs: list[dict]) -> int:
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
    failure_counts = {config["name"]: 0 for config in board_configs}
    interval = 1.0 / healthcheck_hz

    try:
        while process.poll() is None:
            time.sleep(interval)
            if process.poll() is not None:
                break
            for config in board_configs:
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

                if failure_counts[board_name] > max_failures and config["managed"]:
                    journal.send(f"Healthcheck reconfiguring {board_name} [{config['device_ip']}]: {reason}")
                    if configure_board_via_rest(config, fail_on_error=False):
                        failure_counts[board_name] = 0
    finally:
        if process.poll() is None:
            process.terminate()

    return process.returncode


def main() -> int:
    args = parse_args()
    try:
        config_wait_timeout = float(args.config_wait_timeout)
    except ValueError:
        fail(f"invalid config wait timeout: {args.config_wait_timeout}")

    config_paths = discover_configs(args)
    host_ip, interfaces, board_configs = load_board_configs(config_paths)

    journal.send("Configs:")
    for path in config_paths:
        journal.send(f"  {path}")

    journal.send("Interfaces:")
    for iface in interfaces:
        journal.send(f"  {iface}")

    configure_or_wait_for_boards(board_configs, config_wait_timeout)
    sync_interfaces(interfaces)
    cmd = build_executable_args(host_ip, board_configs)

    journal.send("Launching:")
    journal.send(f"  {' '.join(cmd)}")

    return run_host_with_healthcheck(cmd, board_configs)


if __name__ == "__main__":
    raise SystemExit(main())
