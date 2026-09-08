# First setup: router, no SD card

[Русский](README_ru.md)

[Choose a connection](../../README.md) · [Install the client](../install.md)

Run commands from the repository root after installing the client. The example enables only bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, with a 10 ms period. Use your CAN device's bitrates; for classic CAN set `data_kbit: 0`.

1. Connect the board by Ethernet to a router LAN port. Connect the computer to the same router, preferably by cable. DHCP must be enabled; an isolated guest network is unsuitable. Leave the SD slot empty.
2. Connect the CAN device to bus0 and power it following the [wiring requirements](../../README.md#board-power-and-can-wiring).
3. Run `ip -4 -br address`. Find the computer's IPv4 on the board's network. In these examples `192.168.2.2` is **the computer's address, not the board's**; replace it with yours. Reserve this address for the computer in the router's DHCP settings.
4. Check connectivity:

   ```bash
   getent ahostsv4 ethernetcan.local
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   ```

   If the name is not found, find the board's IP in the router's DHCP client list. Use that IP instead of `ethernetcan.local` in commands, the browser and `network.device_ip`.
5. Install the template and open the working file:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/router_no_sd/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Replace `network.host_ip` with your IPv4 and check `fdcan` bitrates. Keep the default `ethernetcan.local` name. Save the file.
6. Start the client. It configures CAN on the board and persists the settings in Flash:

   ```bash
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```
7. Check the result:

   ```bash
   systemctl status ethernet-can.service --no-pager
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   candump vcan1.0
   ```

   Expect `active (running)` and `fdcan.config_applied=true`. Frames appear in `candump` when the attached CAN device transmits. Press Ctrl+C to stop viewing. If no frames arrive, see [troubleshooting](../../README.md#troubleshooting).

Done. The board remembers CAN settings after reset without SD. The computer and client are still needed for SocketCAN traffic. A switch without a DHCP server does not replace the router: use [static IPs](../p2p_static/README.md) for that network.
