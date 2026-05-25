# Multiple Boards

This note shows one practical way to connect 2 Ethernet-CAN boards:

- board 1: `192.168.0.2`
- board 2: `192.168.0.3`
- host: `192.168.0.100`

The host uses one shared IP. Boards are distinguished by device IP on the host side.

> Guide assumes you use a router with base network `192.168.0.0/24` and no firewall.

## 1. Configure both boards

Prepare one SD card for each board.

Board 1 `config.json`:

```json
{
  "network": {
    "hostname": "ethernetcan-1.local",
    "dhcp": false,
    "host_ip": "192.168.0.100",
    "device_ip": "192.168.0.2",
    "netmask": "255.255.255.0",
    "gateway": "0.0.0.0"
  }
}
```

Board 2 `config.json`:

```json
{
  "network": {
    "hostname": "ethernetcan-2.local",
    "dhcp": false,
    "host_ip": "192.168.0.100",
    "device_ip": "192.168.0.3",
    "netmask": "255.255.255.0",
    "gateway": "0.0.0.0"
  }
}
```

## 2. Configure host network

Plug both boards into the router VLAN ports, and connect your host to the router via WiFi or Ethernet.

Verify that both boards respond:

```bash
ping 192.168.0.2
ping 192.168.0.3
```

## 3. Create 2 host config files

Use [`extra/configs/example.json`](../extra/configs/example.json) as the template.

Create `/opt/voltbro/ethernet-can/board1.json`:

```json
{
  "network": {
    "host_ip": "192.168.0.100",
    "device_ip": "192.168.0.2",
    "host_interface_map": {
      "bus0": "vcan1.0",
      "bus1": "vcan1.1",
      "bus2": "vcan1.2",
      "bus3": "vcan1.3",
      "bus4": "vcan1.4",
      "bus5": "vcan1.5"
    }
  },
  "fdcan": {
    "period_ns": 10000000,
    "nominal_kbit": 1000,
    "data_kbit": 8000
  }
}
```

Create `/opt/voltbro/ethernet-can/board2.json`:

```json
{
  "network": {
    "host_ip": "192.168.0.100",
    "device_ip": "192.168.0.3",
    "host_interface_map": {
      "bus0": "vcan2.0",
      "bus1": "vcan2.1",
      "bus2": "vcan2.2",
      "bus3": "vcan2.3",
      "bus4": "vcan2.4",
      "bus5": "vcan2.5"
    }
  },
  "fdcan": {
    "period_ns": 10000000,
    "nominal_kbit": 1000,
    "data_kbit": 8000
  }
}
```

Notes:

1. `network.host_ip` is the same in both files.
2. `network.device_ip` must be unique for each board.
3. `network.host_interface_map` both enables buses and assigns Linux interface names.
4. Interface names must not overlap between boards.

## 4. Start the host software

Manual start:

```bash
sudo /opt/voltbro/ethernet-can/bin/start_ethernet_can.py
```

Or use the systemd unit described in [`README.md`](../README.md).

The launcher will:

1. Scan all `*.json` files in `/opt/voltbro/ethernet-can`
2. Validate addresses and interface mappings
3. Send REST config for files that contain `fdcan`
4. Create missing VCAN interfaces
5. Start one shared host process for both boards

## 5. Check that it works

Open CAN dumps on interfaces from both boards:

```bash
candump vcan1.0
candump vcan2.0
```

You can also watch service logs:

```bash
journalctl -u ethernet-can.service -f
```

If traffic from board 1 is mapped to `vcan1.x` and traffic from board 2 is mapped to `vcan2.x`, the setup is correct.
