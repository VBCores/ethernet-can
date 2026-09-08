#!/usr/bin/env python3

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock


LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "extra" / "start_ethernet_can.py"
SPEC = importlib.util.spec_from_file_location("start_ethernet_can", LAUNCHER_PATH)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class BoardRuntimeCompatibleTest(unittest.TestCase):
    def setUp(self):
        self.config = {
            "name": "listener",
            "device_ip": "192.0.2.2",
            "host_ip": "192.0.2.1",
            "interfaces": {0: "vcan0"},
            "enabled_buses": [True, False, False, False, False, False],
            "classic_buses": [False, False, False, False, False, False],
            "managed": False,
            "period": None,
            "payload": None,
        }
        self.actual = {
            "data_plane": {
                "host_ip": "192.0.2.1",
                "local_port": 1555,
                "host_port": 1556,
            },
            "frames_integration_period_ns": 10_000_000,
            "buses": [
                {
                    "bus": bus,
                    "enabled": bus == 0,
                    **({"nominal_kbit": 1000, "data_kbit": 8000} if bus == 0 else {}),
                }
                for bus in range(launcher.BUS_COUNT)
            ],
        }

    def test_accepts_matching_data_plane_and_buses(self):
        self.assertEqual(
            launcher.board_runtime_compatible(self.config, self.actual),
            (True, "ok", 10_000_000),
        )

    def test_rejects_missing_or_mismatched_data_plane(self):
        cases = (
            ("host_ip", "192.0.2.99", "data_plane.host_ip mismatch"),
            ("local_port", 1556, "data_plane.local_port mismatch"),
            ("host_port", 1555, "data_plane.host_port mismatch"),
        )
        for field, value, expected_reason in cases:
            with self.subTest(field=field):
                actual = copy.deepcopy(self.actual)
                actual["data_plane"][field] = value
                self.assertEqual(
                    launcher.board_runtime_compatible(self.config, actual),
                    (False, expected_reason, None),
                )

        for field in ("host_ip", "local_port", "host_port"):
            with self.subTest(missing_field=field):
                actual = copy.deepcopy(self.actual)
                del actual["data_plane"][field]
                self.assertFalse(
                    launcher.board_runtime_compatible(self.config, actual)[0]
                )

        actual = copy.deepcopy(self.actual)
        del actual["data_plane"]
        self.assertEqual(
            launcher.board_runtime_compatible(self.config, actual),
            (False, "missing data_plane", None),
        )

    def test_board_managed_startup_reads_config_without_put(self):
        status_response = mock.Mock(status_code=200, text="")
        status_response.json.return_value = {"fdcan": {"config_applied": True}}
        config_response = mock.Mock(status_code=200, text="")
        config_response.json.return_value = self.actual

        with mock.patch.object(
            launcher.requests,
            "get",
            side_effect=(status_response, config_response),
        ) as get, mock.patch.object(launcher.requests, "put") as put:
            launcher.configure_or_wait_for_boards([self.config], timeout_seconds=0)

        self.assertEqual(self.config["period"], 10_000_000)
        self.assertEqual(self.config["classic_buses"], [False] * launcher.BUS_COUNT)
        self.assertEqual(get.call_count, 2)
        put.assert_not_called()

    def test_board_managed_classic_mode_reaches_host_cli(self):
        actual = copy.deepcopy(self.actual)
        actual["buses"][0]["data_kbit"] = 0
        status_response = mock.Mock(status_code=200, text="")
        status_response.json.return_value = {"fdcan": {"config_applied": True}}
        config_response = mock.Mock(status_code=200, text="")
        config_response.json.return_value = actual

        with mock.patch.object(
            launcher.requests,
            "get",
            side_effect=(status_response, config_response),
        ), mock.patch.object(launcher.requests, "put") as put:
            launcher.configure_or_wait_for_boards([self.config], timeout_seconds=0)

        self.assertTrue(self.config["classic_buses"][0])
        self.assertIn("--classic-bus0", launcher.build_executable_args("192.0.2.1", [self.config]))
        put.assert_not_called()

    def test_managed_healthcheck_requires_applied_status(self):
        config = copy.deepcopy(self.config)
        config["managed"] = True
        config["payload"] = {
            "data_plane": {"host_ip": "192.0.2.1"},
            "frames_integration_period_ns": 10_000_000,
            "buses": self.actual["buses"],
        }
        status_response = mock.Mock(status_code=200, text="")
        status_response.json.return_value = {"fdcan": {"config_applied": False}}

        with mock.patch.object(launcher.requests, "get", return_value=status_response) as get:
            self.assertEqual(
                launcher.healthcheck_board(config),
                (False, "board config is not applied"),
            )

        self.assertEqual(get.call_count, 1)

    def test_managed_startup_waits_for_config_applied(self):
        config = copy.deepcopy(self.config)
        config["managed"] = True
        config["period"] = 10_000_000

        with mock.patch.object(
            launcher,
            "configure_board_via_rest",
            return_value=True,
        ) as configure, mock.patch.object(
            launcher,
            "healthcheck_board",
            side_effect=((False, "board config is not applied"), (True, "ok")),
        ) as healthcheck, mock.patch.object(launcher.time, "sleep"):
            launcher.configure_or_wait_for_boards([config], timeout_seconds=-1)

        configure.assert_called_once_with(config, fail_on_error=True)
        self.assertEqual(healthcheck.call_count, 2)


if __name__ == "__main__":
    unittest.main()
