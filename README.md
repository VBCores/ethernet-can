# Ethernet-CAN board

**[http://vbcores.com/products/ethernet-can](http://vbcores.com/products/ethernet-can)**

![Ethernet-CAN](./extra/images/ethernet-can.png)

## What This Device Is

Ethernet-CAN is an IP device with six logical CAN-FD buses. The board has two MCUs:

- STM32H7 owns Ethernet, HTTP REST, the web panel, SD-card config, and CAN buses `0..2`.
- STM32G4 is connected to H7 over SPI and owns CAN buses `3..5`.

The board uses normal IP networking. By default it can get an address from DHCP and is reachable by an mDNS hostname such as `ethernetcan.local`. If your network does not use DHCP, or if you need fixed identity settings, put `config.json` on the SD card and set static IP, hostname, MAC, netmask, gateway, or other network fields there.

The board exposes:

- `GET /api/v1/status`: network state, FDCAN state, counters, reset/watchdog diagnostics, SD persistence state.
- `GET /api/v1/config`: currently applied runtime config.
- `PUT /api/v1/config`: apply runtime config and save it as `runtime.json`.
- `/panel`: small web control panel for status and config.

CAN data itself uses UDP. HTTP is only the config/status plane.

## Host Service Model

The Linux host service creates the data channel between the board and SocketCAN. It needs:

- one host IP address;
- one board address, either literal IPv4 or hostname;
- a map from board bus numbers to Linux CAN interface names.

The Python launcher reads host JSON files, prepares VCAN interfaces, optionally configures the board through REST, and starts the C++ data-plane process. The C++ process does not parse JSON and does not configure the board; it only forwards UDP CAN frames to and from SocketCAN.

The host supports multiple boards behind one shared host IP. Each board gets its own host JSON file, and incoming UDP packets are assigned to boards by source IP.

## FDCAN Config Ownership

Choose one ownership style per board.

| Style | Where the FDCAN config lives | Host JSON contains `fdcan` | Typical use |
| --- | --- | --- | --- |
| Host-managed | Host JSON | Yes | Easiest to edit from Linux/systemd config. The launcher sends REST config on startup and reapplies it on healthcheck mismatch. |
| Web/panel-managed | Board `runtime.json` | No | User configures the board once through `/panel`; after that the host only starts the listener. |
| SD-locked | SD `config.json` | No | Fixed board-owned config. Fields explicitly present in `config.json` are locked; conflicting REST config is rejected. |

The SD card uses two files in the root directory:

- `config.json`: user-owned file. Firmware reads it and never overwrites it.
- `runtime.json`: last successfully applied full runtime config. Firmware creates and updates it after REST or panel config.

If `runtime.json` is valid, the board applies it at boot. If it is missing, the board tries to build a runtime config from defaults plus locked fields in `config.json`. If the result is incomplete, REST and `/panel` still start, but FDCAN remains unapplied until a config arrives.

Old host INI and SD INI configs are no longer used.

## Recommended First Setup

For most users:

1. Put a minimal SD `config.json` on the board with a hostname and DHCP enabled.
2. Let the router give the board an IP address.
3. Use the board hostname as `network.device_ip` in host JSON.
4. Put `fdcan` in host JSON so the host service owns FDCAN bitrate and period.

See [Router DHCP Host Managed](./app_notes/router_dhcp_host_managed/Router%20DHCP%20Host%20Managed.md) for the complete example.

Use the other app notes when you need direct point-to-point static addressing, web-panel config, SD-locked config, or multiple boards.

## Hardware

Solder the CAN-FD termination jumper pads on the back side of the board as required by your CAN network. Without proper termination, CAN communication will not work.

Before powering a CAN network, measure resistance between `CANH` and `CANL`. It should be about `60 Ohm` when two `120 Ohm` terminators are present. If it is `120 Ohm`, one terminator is missing.

CAN uses two signal wires, but stable operation also requires a shared ground reference between all devices. Recommended wire colors are `CANH` yellow, `CANL` green, ground black.

## Firmware

1. Use STM32CubeProgrammer with [ST-Link](https://vbcores.tilda.ws/products/vb-stlink).
2. Flash both H7 and G4 firmware images from the release package.
3. On the G4 chip, set Option Byte `NSWBoot0` to `0` (unchecked in `OB -> Option Bytes`).

The H7 firmware starts network, REST API, and `/panel` even if no FDCAN runtime config is available yet.

## Board SD Card

Format the SD card as FAT and put JSON files in the root directory.

Minimal `config.json`:

```json
{
  "network": {
    "hostname": "ethernetcan.local",
    "dhcp": true
  }
}
```

Network fields accepted in `config.json`:

- `hostname`: mDNS hostname, with or without `.local`.
- `dhcp`: `true` by default.
- `host_ip`: host UDP destination IP used by board data plane.
- `device_ip`, `netmask`, `gateway`: static board addressing. If `device_ip` is present, DHCP is disabled.
- `mac_address`: optional board MAC override. If omitted, firmware derives a locally administered MAC from the H7 hardware UID.
- `wake_on_lan_mac` or `wol_mac`: optional Wake-on-LAN target.

For locked FDCAN config, `config.json` may also contain runtime fields from `GET /api/v1/config`: `data_plane.host_ip`, `frames_integration_period_ns`, and `buses`. Any explicitly present runtime field is treated as locked.

## Host Software Installation

This repository is intended to be built and installed on the Linux host that controls one or more Ethernet-CAN boards.

Install tools and runtime components:

```bash
sudo apt update
sudo apt install -y build-essential cmake libboost-program-options-dev python3 python3-systemd python3-requests python3-tenacity can-utils iproute2 kmod
```

Clone, build, and install:

```bash
git clone --recurse-submodules https://github.com/VBCores/ethernet-can
cd ethernet-can
cmake -S . -B build
cmake --build build
sudo cmake --install build
```

Installed files:

- `/opt/voltbro/ethernet-can/bin/ethernet-can`
- `/opt/voltbro/ethernet-can/bin/start_ethernet_can.py`
- `/opt/voltbro/ethernet-can/systemd/ethernet-can.service`

Host JSON config files are not installed automatically. Put them in `/opt/voltbro/ethernet-can` or set `ETHERNET_CAN_CONFIGS_DIR` in the systemd unit.

## Host JSON Configuration

Use [`extra/configs/example.json`](./extra/configs/example.json) as a host-managed template and [`extra/configs/example-board-managed.json`](./extra/configs/example-board-managed.json) as a listener-only template.

Each host JSON file describes one board. Top-level keys:

- `network`: required.
- `fdcan`: optional. Its presence means host-managed FDCAN config.

`network` fields:

- `host_ip`: Linux host IP used for the UDP data plane.
- `device_ip`: board address, either IPv4 or hostname such as `ethernetcan.local`.
- `host_interface_map`: maps `bus0`..`bus5` to Linux CAN interface names. A bus is enabled on the host when it is present in this map.

`fdcan` fields:

- `period_ns`: UDP frame integration period in nanoseconds.
- `nominal_kbit`: FDCAN nominal bitrate.
- `data_kbit`: FDCAN data bitrate. Use `0` for classic CAN mode.

Manual debug start:

```bash
sudo /opt/voltbro/ethernet-can/bin/start_ethernet_can.py
```

The launcher polls `GET /api/v1/status` while the host data plane is running. In host-managed mode it compares the board config with the expected JSON and sends `PUT /api/v1/config` again after repeated mismatch or no-response failures. In listener-only mode it checks that a compatible board-applied config is still present.

`ETHERNET_CAN_CONFIG_WAIT_TIMEOUT_SECONDS=-1` makes listener-only startup wait forever for a board config.

## Systemd Service

Install the unit after host JSON files are in place:

```bash
sudo install -m 0644 /opt/voltbro/ethernet-can/systemd/ethernet-can.service /etc/systemd/system/ethernet-can.service
sudo systemctl daemon-reload
sudo systemctl enable --now ethernet-can.service
```

Check service logs:

```bash
systemctl status ethernet-can.service
journalctl -u ethernet-can.service -f
```

After startup, the launcher creates and configures interfaces from `network.host_interface_map`. Check data with:

```bash
candump vcan1.0
```

## App Notes

Concrete setups live in [app_notes](./app_notes):

- Router DHCP with host-managed FDCAN config.
- Direct point-to-point static network.
- Web-panel runtime config.
- SD-locked board config.
- Multiple boards.
- Mixed host-managed and board-managed boards.

## Build Notes For Firmware Developers

The host software is Linux-native. The firmware is under `STM32H7-ETH-LWIP` and `STM32G4-SPI-CAN`.

The H7 firmware is built around STM32Cube and lwIP in a superloop, without an RTOS. Ethernet and the first three FDCAN buses live on H7. The companion G4 is configured by H7 over SPI and handles the remaining buses. Be careful with H7 memory placement, DMA buffers, MPU/cache settings, and linker scripts.

The default H7 build path is CMake. If using STM32CubeMX, keep user code blocks and verify that custom source files remain in the project after regeneration.

## Troubleshooting

- `device_ip` may be a hostname. The host uses normal Linux `getaddrinfo()`, so mDNS resolution depends on host resolver setup, usually `libnss-mdns`/Avahi.
- If `/panel` opens but CAN does not move, check `GET /api/v1/status`: `fdcan.config_applied`, bus state, queue drops, and SD persistence errors.
- If host-managed startup fails with HTTP `409`, SD `config.json` contains locked fields that conflict with host JSON.
- If listener-only startup waits forever, configure the board through `/panel` or provide `runtime.json`/locked SD config.
- If frames arrive on the wire but not in `candump`, check `network.host_interface_map`, interface names, and `candump` target.
