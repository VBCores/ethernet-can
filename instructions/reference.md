# Configuration reference

[Русский](reference_ru.md)

[Choose a connection](../README.md)

## Where settings live

| File | Location | Purpose |
| --- | --- | --- |
| `ethernetcan.json` | Linux: `/opt/voltbro/ethernet-can/` | Computer IP, board address, SocketCAN interfaces, optional `fdcan` |
| `config.json` | SD root, if used | Board network settings and runtime field locks |
| H7 Flash record | Inside the board | Last persisted CAN configuration; no separate `runtime.json` |

With `fdcan`, the client sets bitrates and period and restores its configuration after repeated failed healthchecks. Without `fdcan`, it waits for the board configuration; destination IP and enabled buses must match host JSON. A client with `fdcan` can therefore overwrite changes made in the panel.

Host JSON `network.host_ip` is the **computer** address; `network.device_ip` is the **board** address or name. `host_interface_map` enables the required buses; host-managed configuration disables absent buses. One process handles multiple boards, with one JSON per board.

`fdcan.period_ns` is UDP aggregation time in nanoseconds: `10000000` = 10 ms; `0` = immediate sending. It is not the CAN message generation frequency. `nominal_kbit` and `data_kbit` set bitrates; `data_kbit: 0` means classic CAN. Format is selected for the whole bus. The wire field contains bus number and CAN ID, but no classic/FD flag. Classic payloads are limited to 8 bytes; CAN FD lengths are 0..8, 12, 16, 20, 24, 32, 48, 64.

## SD and boot

Without SD, DHCP and `ethernetcan.local` are defaults; MAC is derived from the H7 UID. SD supports `network.hostname`, `dhcp`, `device_ip`, `netmask`, `gateway`, `host_ip`, `mac_address`, `wake_on_lan_mac`/`wol_mac`. For static IP set `dhcp:false` together with `device_ip`. Firmware never overwrites user `config.json`; the file must be smaller than 2048 bytes.

SD locks runtime fields `data_plane.host_ip`, `frames_integration_period_ns` and explicit `buses` fields. At boot, firmware validates Flash and SD compatibility; on conflict it tries to build a full configuration from SD and persist it. Without a complete configuration, networking and the panel remain available but CAN waits for setup. INI and `runtime.json` are no longer used.

Connectivity checks and common problems: [Troubleshooting](../README.md#troubleshooting).
