# Multiple Boards

This note shows one practical way to connect 2 Ethernet-CAN boards:

- board 1: `192.168.0.2`
- board 2: `192.168.0.3`
- host: `192.168.0.100`

The host uses one shared IP. Boards are distinguished by device IP on the host side.

> Guide assumes you use a router with base network `192.168.0.0/24` and no firewall.
> This is most likely true for most basic routers - if not, modify either router settings or device IPs accordingly.

## 1. Configure both boards

Prepare one SD card for each board.

Board 1 `ethernet.ini`:

```ini
[ethernet]
host_ip = [192, 168, 0, 100]
device_ip = [192, 168, 0, 2]
```

Board 2 `ethernet.ini`:

```ini
[ethernet]
host_ip = [192, 168, 0, 100]
device_ip = [192, 168, 0, 3]
```

## 2. Configure host network

Plug both boards into the routers VLAN ports, and connect your host to the router via WiFi or Ethernet.

Verify that both boards respond:

```bash
ping 192.168.0.2
ping 192.168.0.3
```

## 3. Create 2 host config files

Use [`extra/configs/example.ini`](/Users/igor/Work/imec/projects/Other/ethernet-can/extra/configs/example.ini) as the template.

Create `/opt/voltbro/ethernet-can/board1.ini`:

```ini
[DATA_ACQUIZITION]
Period = 10000000

[NETWORK_PARAMS]
Host_IP_address = 192.168.0.100
Device_IP_address = 192.168.0.2

[HOST_INTERFACE_MAP]
bus0 = vcan1.0
bus1 = vcan1.1
bus2 = vcan1.2
bus3 = vcan1.3
bus4 = vcan1.4
bus5 = vcan1.5

[FDCAN_PARAMS]
Nominal_baud = 1000
Data_baud = 8000
```

Create `/opt/voltbro/ethernet-can/board2.ini`:

```ini
[DATA_ACQUIZITION]
Period = 10000000

[NETWORK_PARAMS]
Host_IP_address = 192.168.0.100
Device_IP_address = 192.168.0.3

[HOST_INTERFACE_MAP]
bus0 = vcan2.0
bus1 = vcan2.1
bus2 = vcan2.2
bus3 = vcan2.3
bus4 = vcan2.4
bus5 = vcan2.5

[FDCAN_PARAMS]
Nominal_baud = 1000
Data_baud = 8000
```

Notes:

1. `Host_IP_address` is the same in both files.
2. `Device_IP_address` must be unique for each board.
3. `[HOST_INTERFACE_MAP]` both enables buses and assigns Linux interface names.
4. Interface names **must** not overlap between boards.

## 4. Start the host software

Manual start:

```bash
sudo /opt/voltbro/ethernet-can/bin/start_ethernet_can.py
```

Or use the systemd unit described in [`README.md`](/Users/igor/Work/imec/projects/Other/ethernet-can/README.md).

The launcher will:

1. Scan all `*.ini` files in `/opt/voltbro/ethernet-can`
2. Validate IPs and interface mappings
3. Create missing VCAN interfaces
4. Start one shared host process for both boards

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
