# Web Panel Runtime Config

Use this scenario when the board should remember its FDCAN config and the host should only start the data listener.

The host JSON intentionally has no `fdcan` section. That tells the launcher not to send config. Instead, it waits until the board reports an applied runtime config and then starts the C++ data plane with the period read from the board.

## Files

- Copy [`sd_config.json`](./sd_config.json) to the SD-card root as `config.json`.
- Copy [`host_config.json`](./host_config.json) to `/opt/voltbro/ethernet-can/panel.json`.

## First-Time Board Setup

1. Open the panel:

```text
http://ethernetcan-panel.local/panel
```

2. Edit the config JSON in the panel. Minimal example for bus0:

```json
{
  "data_plane": {
    "host_ip": "192.168.2.2"
  },
  "frames_integration_period_ns": 10000000,
  "buses": [
    {"bus": 0, "enabled": true, "nominal_kbit": 1000, "data_kbit": 8000},
    {"bus": 1, "enabled": false},
    {"bus": 2, "enabled": false},
    {"bus": 3, "enabled": false},
    {"bus": 4, "enabled": false},
    {"bus": 5, "enabled": false}
  ]
}
```

3. Apply it. The board writes `runtime.json`.
4. Restart or power-cycle the board and check `GET /api/v1/status`: `fdcan.config_applied` should be `true`.

## Host Startup

Install the listener-only host JSON:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/panel.json
sudo systemctl restart ethernet-can.service
```

The launcher waits for the board config. If you want it to wait forever during manual setup, set:

```bash
ETHERNET_CAN_CONFIG_WAIT_TIMEOUT_SECONDS=-1
```

## Notes

If the board has no valid `runtime.json`, this mode will not start the host listener until the panel config is applied.
