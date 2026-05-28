# Multiple Boards Web Config

Use this scenario when several boards are configured manually through their web panels, and one host service listens to all of them.

Each board gets a different hostname. Each host JSON has no `fdcan`, so the launcher waits for each board's persisted runtime config.

## Files

For board 1:

- SD: [`board1_sd_config.json`](./board1_sd_config.json) as `config.json`
- Host: [`board1_host_config.json`](./board1_host_config.json) as `/opt/voltbro/ethernet-can/board1.json`

For board 2:

- SD: [`board2_sd_config.json`](./board2_sd_config.json) as `config.json`
- Host: [`board2_host_config.json`](./board2_host_config.json) as `/opt/voltbro/ethernet-can/board2.json`

## How It Works

Both boards use DHCP and mDNS:

- `ethernetcan-1.local`
- `ethernetcan-2.local`

The host uses one shared `network.host_ip`. Interface names must not overlap between boards. In this example board 1 maps to `vcan1.x`, and board 2 maps to `vcan2.x`.

## Steps

1. Prepare one SD card per board.
2. Boot both boards.
3. Open each panel and apply its FDCAN runtime config:

```text
http://ethernetcan-1.local/panel
http://ethernetcan-2.local/panel
```

4. Install both host JSON files:

```bash
sudo install -m 0644 board1_host_config.json /opt/voltbro/ethernet-can/board1.json
sudo install -m 0644 board2_host_config.json /opt/voltbro/ethernet-can/board2.json
sudo systemctl restart ethernet-can.service
```

5. Check traffic:

```bash
candump vcan1.0
candump vcan2.0
```

## Notes

The host service binds one UDP socket to the shared host IP. Boards are distinguished by UDP source IP, so each board hostname must resolve to a different address.
