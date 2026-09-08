# Direct cable: computer ↔ board

[Русский](README_ru.md)

[Choose a connection](../../README.md) · [Install the client](../install.md)

Run commands from the repository root after installing the client. The example enables only bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, with a 10 ms period. Use your CAN device's bitrates; for classic CAN set `data_kbit: 0`.

This scenario uses SD to set the board's fixed IP. No router or DHCP is required. Without SD the default firmware expects DHCP; for a first setup without SD use a [router](../router_no_sd/README.md).

1. Connect the CAN device to bus0 and power it following the [wiring requirements](../../README.md#board-power-and-can-wiring). Connect the board's Ethernet port to a dedicated Ethernet port on the computer.
2. Prepare a FAT/FAT32 SD card. Copy [sd_config.json](sd_config.json) to its root as `config.json`. Safely eject it, insert it with board power off, then power the board. Its address will be `10.0.0.2/24`.
3. Configure the computer's **port connected to the board** as `10.0.0.1/24`, without gateway or DNS. In Linux network settings select that wired profile → IPv4 → manual → address `10.0.0.1`, mask `255.255.255.0`, gateway blank → save and reconnect. First check that another network/VPN does not use `10.0.0.0/24`; otherwise change the subnet consistently in both JSON files and on the computer. For netplan use the [template](../../extra/10-ethernet-can.yaml): replace `INTERFACE_NAME` with the name from `ip -br link`, merge into your existing configuration and use `sudo netplan try`.
4. Check `curl --max-time 5 http://10.0.0.2/api/v1/status`.
5. Install the template:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/p2p_static/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   IPs already match: computer `10.0.0.1`, board `10.0.0.2`. Check CAN bitrates and save.
6. Start the client:

   ```bash
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```
7. Check the result:

   ```bash
   systemctl status ethernet-can.service --no-pager
   curl --max-time 5 http://10.0.0.2/api/v1/status
   candump vcan1.0
   ```

   Expect `active (running)` and `fdcan.config_applied=true`. Frames appear in `candump` when the attached CAN device transmits. Press Ctrl+C to stop viewing. If no frames arrive, see [troubleshooting](../../README.md#troubleshooting).
