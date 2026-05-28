# Mixed Config

Use this scenario when one Linux host service runs boards with different config ownership styles.

In this example:

- `ethernetcan-host.local` is host-managed. Its host JSON contains `fdcan`.
- `ethernetcan-panel.local` is board-managed. Its host JSON has no `fdcan`, so the board must already have an applied `runtime.json`.

## Files

For the host-managed board:

- SD: [`host_managed_sd_config.json`](./host_managed_sd_config.json) as `config.json`
- Host: [`host_managed_host_config.json`](./host_managed_host_config.json) as `/opt/voltbro/ethernet-can/host-managed.json`

For the board-managed board:

- SD: [`board_managed_sd_config.json`](./board_managed_sd_config.json) as `config.json`
- Host: [`board_managed_host_config.json`](./board_managed_host_config.json) as `/opt/voltbro/ethernet-can/board-managed.json`

## Steps

1. Prepare both boards with their SD configs.
2. Configure `ethernetcan-panel.local` once through `/panel` so it saves `runtime.json`.
3. Install both host JSON files:

```bash
sudo install -m 0644 host_managed_host_config.json /opt/voltbro/ethernet-can/host-managed.json
sudo install -m 0644 board_managed_host_config.json /opt/voltbro/ethernet-can/board-managed.json
sudo systemctl restart ethernet-can.service
```

## What To Expect

The launcher sends REST config only to `ethernetcan-host.local`. For `ethernetcan-panel.local`, it waits for the existing board-applied config and then starts the data listener.

Both boards share `network.host_ip`, but their SocketCAN interface names do not overlap.
