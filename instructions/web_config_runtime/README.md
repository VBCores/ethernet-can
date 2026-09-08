# Configure in a browser, no SD card

[Русский](README_ru.md)

[Choose a connection](../../README.md) · [Install the client](../install.md)

Run commands from the repository root after installing the client. The example enables only bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, with a 10 ms period. Use your CAN device's bitrates; for classic CAN set `data_kbit: 0`.

1. Connect the board and computer to the same DHCP router. Leave the SD slot empty.
2. Connect the CAN device to bus0 and power it following the [wiring requirements](../../README.md#board-power-and-can-wiring).
3. Run `ip -4 -br address`. Find the computer's IPv4 on the board's network. In these examples `192.168.2.2` is **the computer's address, not the board's**; replace it with yours. Reserve this address for the computer in the router's DHCP settings.
4. Check connectivity:

   ```bash
   getent ahostsv4 ethernetcan.local
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   ```

   If the name is not found, find the board's IP in the router's DHCP client list. Use that IP instead of `ethernetcan.local` in commands, the browser and `network.device_ip`.
5. Stop the service: `sudo systemctl stop ethernet-can.service`. Open `http://ethernetcan.local/panel`. Paste [runtime_config.json](runtime_config.json) into the JSON field, replace `data_plane.host_ip` with the computer IP, set CAN bitrates and click Apply. Wait for `fdcan.config_applied=true` in status. Settings persist in Flash.
6. Install the host configuration:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/web_config_runtime/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Set `network.host_ip` to the same computer IP. This file has **no `fdcan` section**: settings come from the board. Keep it absent to continue using browser configuration.
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

When changing enabled buses, update the client's `host_interface_map` too. After changing classic/FD mode, restart the service so it reads the new mode.
