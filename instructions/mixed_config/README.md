# Two boards: host and browser configuration

[Русский](README_ru.md)

[Choose a connection](../../README.md) · [Install the client](../install.md)

First check [one board without SD](../router_no_sd/README.md). Here both boards connect to the same DHCP router and one service runs on the computer. Boards need distinct addresses: this example uses SD to assign `ethernetcan-1.local` and `ethernetcan-2.local`. These are explicit example settings, not factory names. As an SD-free alternative, reserve different board IPs on the router and use those IPs in host JSON instead of names.

1. Install the client. Connect both boards and the computer to router LAN ports. Connect a CAN device to each board's bus0 following the [wiring requirements](../../README.md#board-power-and-can-wiring).
2. Find the computer IP with `ip -4 -br address` and reserve it on the router. Replace `192.168.2.2` with this address in **both** [host_managed_host_config.json](host_managed_host_config.json) and [board_managed_host_config.json](board_managed_host_config.json). Interfaces are already separate: first board bus0 → `vcan1.0`, second board bus0 → `vcan2.0`.
3. Copy [host_managed_sd_config.json](host_managed_sd_config.json) to the first board's FAT/FAT32 SD as `config.json`; copy [board_managed_sd_config.json](board_managed_sd_config.json) to the second card under the same name. Safely eject the cards, insert with board power off, then power both boards.
4. Check addresses:

   ```bash
   getent ahostsv4 ethernetcan-1.local
   getent ahostsv4 ethernetcan-2.local
   ```

   They must differ. If a name is not found, find the board IP on the router and use it in that board's JSON and browser URL.
5. Stop the service: `sudo systemctl stop ethernet-can.service`. The first board uses `fdcan` in its host JSON: check bitrates there. Open `http://ethernetcan-2.local/panel` for the second board. Paste [runtime_config.json](runtime_config.json) into the panel JSON field, replace `data_plane.host_ip` with the same computer IP, check CAN bitrates and click Apply. The example enables only bus0. For classic CAN set `data_kbit: 0`. Wait for `fdcan.config_applied=true`.
6. Move the previous single-board config out of `/opt/voltbro/ethernet-can` to a backup directory: the service reads every JSON in its directory. Install the two new files:

   ```bash
   sudo install -m 0644 instructions/mixed_config/host_managed_host_config.json /opt/voltbro/ethernet-can/board1.json
   sudo install -m 0644 instructions/mixed_config/board_managed_host_config.json /opt/voltbro/ethernet-can/board2.json
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```

7. Check `systemctl status ethernet-can.service --no-pager`. In separate terminals run `candump vcan1.0` and `candump vcan2.0`. Frames should appear when the CAN devices transmit. Press Ctrl+C to stop viewing.

The client configures the first board over REST and waits for the second board's saved settings. All boards must use the same computer IP, but distinct board IPs and interface names. When changing enabled buses, update interface maps; restart the service after changing classic/FD mode.
