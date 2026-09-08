# Lock settings on SD

[Русский](README_ru.md)

[Choose a connection](../../README.md) · [Install the client](../install.md)

Run commands from the repository root after installing the client. The example enables only bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, with a 10 ms period. Use your CAN device's bitrates; for classic CAN set `data_kbit: 0`.

1. Connect the board and computer to the same DHCP router. Connect the CAN device to bus0 and power it following the [wiring requirements](../../README.md#board-power-and-can-wiring).
2. Run `ip -4 -br address`. Find the computer's IPv4 on the board's network. In these examples `192.168.2.2` is **the computer's address, not the board's**; replace it with yours. Reserve this address for the computer in the router's DHCP settings.
3. Edit [config.json](config.json): set `data_plane.host_ip` to the computer IP and set bitrates and enabled buses in `buses`. Explicit runtime fields will be protected from REST/panel changes.
4. Copy the file to the root of a FAT/FAT32 SD as `config.json`. Safely eject it, insert it with the board powered off, then power the board.
5. Check connectivity:

   ```bash
   getent ahostsv4 ethernetcan.local
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   ```

   If the name is not found, find the board's IP in the router's DHCP client list. Use that IP instead of `ethernetcan.local` in commands, the browser and `network.device_ip`.

   Status should show `sd_mounted=true`, `config_json_present=true`, `runtime_flash_valid=true` and `fdcan.config_applied=true`.
6. Install the host configuration:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/sd_locked_config/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Use the same computer IP. If you changed enabled buses on SD, match `host_interface_map`. Do not add `fdcan`.
7. Start the client:

   ```bash
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```
8. Check the result:

   ```bash
   systemctl status ethernet-can.service --no-pager
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   candump vcan1.0
   ```

   Expect `active (running)` and `fdcan.config_applied=true`. Frames appear in `candump` when the attached CAN device transmits. Press Ctrl+C to stop viewing. If no frames arrive, see [troubleshooting](../../README.md#troubleshooting).

A conflicting panel/REST change returns `409 Conflict`. To change locked fields, edit SD and restart the board. Removing SD removes the locks after reboot, but CAN settings persisted in Flash remain.
