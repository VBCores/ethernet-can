# Ethernet-CAN

[Русский](README_ru.md)

Ethernet-CAN connects up to six CAN/CAN FD buses to a Linux computer over Ethernet. The host client exposes SocketCAN interfaces for `candump`, ROS and other CAN applications.

You need the board with H7/G4 firmware, power, an Ethernet cable and a Linux computer with the client installed. **No SD card is needed for the usual router connection.** The board obtains an IP automatically and uses `ethernetcan.local`. CAN settings persist in internal Flash.

## Choose your connection

| What you want to do | Instructions | SD card |
| --- | --- | --- |
| **First setup: connect the computer and board to the same router** | **[Router, no SD](instructions/router_no_sd/README.md)** | Not needed |
| Connect the computer directly to the board without a router | [Direct cable with static IPs](instructions/p2p_static/README.md) | Required for board IP |
| Configure CAN in a browser, also without SD | [Router and web panel](instructions/web_config_runtime/README.md) | Not needed |
| Lock CAN settings on a card | [SD configuration](instructions/sd_locked_config/README.md) | Required |
| Connect several boards to one computer | [Multiple boards](instructions/multiple_boards_web_config/README.md) | Required in this example |
| Configure one board from the computer and another in a browser | [Mixed configuration](instructions/mixed_config/README.md) | Required in this example |

Each guide takes you from connection to checking CAN. [Client installation](instructions/install.md) is shared by all scenarios. If unsure, start with the first row.

[Configuration reference](instructions/reference.md) · [All instructions](instructions/README.md)

## Board, power and CAN wiring

Power the board through USB Type-C. Connect Ethernet to a router LAN port or a dedicated computer Ethernet port. Match the physical CAN connector number to the selected bus: for example, bus0 in the guide maps to `vcan1.0` on the computer.

Connect CANH to CANH, CANL to CANL, and common GND. Each CAN bus needs one 120 Ω terminator at each end. With power off, resistance between CANH and CANL should be about 60 Ω; about 120 Ω means one terminator is missing. If the board is at a bus end, enable its terminator using the solder jumper on the back; an extra terminator is not needed in the middle of the bus.

Connect wiring and insert SD with power off, then power the board and CAN devices. Check connector pinout and jumper placement for your board revision.

![Ethernet-CAN](extra/images/ethernet-can.png)

## Expectations and gotchas

- **Without SD, a DHCP server is needed**, usually a router. A plain switch or direct cable does not assign IPs. The direct connection guide uses SD and static IPs.
- The default single-board name is `ethernetcan.local`. Multiple boards need distinct addresses; a shared name cannot reliably select a particular board.
- `network.host_ip` is the **Linux computer's** IPv4; `network.device_ip` is the **board's** IP or name. Reserve the computer IP on the router. In a VM, use the VM's own address and an Ethernet interface accessible inside it.
- Examples enable only bus0 with CAN FD `1000/8000 kbit/s` and 10 ms aggregation. Set the connected device's bitrates. For classic CAN set `data_kbit: 0`. Aggregation time does not set the CAN message frequency.
- After startup, expect `active (running)` and `fdcan.config_applied=true`. Frames appear in `candump` only when a CAN device transmits. An accessible panel alone does not prove CAN traffic works.
- CAN settings persist in Flash across resets without SD. The computer client is still needed for SocketCAN traffic. Without a full configuration, the board opens the panel but waits for CAN setup.
- A host JSON `fdcan` section means the client controls settings and may overwrite panel changes. For browser configuration use the example without this section.
- The service reads every `*.json` directly in `/opt/voltbro/ethernet-can`. Keep one working file per board and store backups elsewhere. Do not run the service and a second manual client at the same time.
- When changing enabled buses, match `host_interface_map`; restart the service after switching classic/FD. Conflicting SD locks produce `409 Conflict`. Removing SD and rebooting removes locks but keeps persisted CAN settings.

## Firmware and hardware

H7 handles Ethernet, REST, panel, SD and bus0..2. G4 connects over SPI and handles bus3..5. Updating requires matching firmware for both MCUs and ST-Link; the previous board procedure specifies `NSWBoot0=0` for G4. Follow instructions for your board revision and firmware bundle. Firmware sources are in the separate ETH-FDCAN_firmware repository; this repository contains the Linux client.

`GET /api/v1/status` reports status; `GET /api/v1/config` returns runtime configuration; `PUT /api/v1/config` validates, persists and applies it. The panel is at `/panel`. UDP ports are fixed and cannot be changed through REST.

## Troubleshooting

Run commands on the Linux client computer. If mDNS fails, replace `ethernetcan.local` with the board IP from the router's DHCP list.

```bash
getent ahostsv4 ethernetcan.local
curl --max-time 5 http://ethernetcan.local/api/v1/status
curl --max-time 5 http://ethernetcan.local/api/v1/config
systemctl status ethernet-can.service --no-pager
journalctl -u ethernet-can.service -n 50 --no-pager
ip -br link
```

| Symptom | Check |
| --- | --- |
| Panel unavailable | Power, Ethernet link, same LAN, DHCP; avoid isolated guest networks |
| IP works, name fails | `avahi-daemon`, `libnss-mdns`, mDNS support in `hosts:` in `/etc/nsswitch.conf`; temporarily use board IP |
| Service fails to start | Journal; computer must own `host_ip`; one JSON per board; no second client occupying UDP 1556 |
| `409 Conflict` | SD locks the field: match SD or edit the card and reboot |
| Client waits for config | Apply panel settings; check `fdcan.config_applied`, destination IP and enabled buses |
| Empty `candump` | CAN device must transmit; check bus/interface, bitrates, power, common GND, termination and CAN error counters |
| REST works, Ethernet CAN traffic fails | Firewall: board receives UDP 1555, computer receives UDP 1556; HTTP uses TCP 80, mDNS UDP 5353 |
| `mount failed` without SD | Expected when no card is present; check `runtime_flash_valid` and `fdcan.config_applied` |

On systemd-resolved systems, the supplied `extra/ethernet-can-mdns.conf` can be used instead of Avahi: install it in `/etc/systemd/resolved.conf.d/`, restart resolved and check mDNS on the required interface with `resolvectl mdns`. For first setup, one working name resolver or the board IP is enough.
