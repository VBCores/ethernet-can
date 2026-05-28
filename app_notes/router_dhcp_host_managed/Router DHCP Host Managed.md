# Router DHCP Host Managed

This is the recommended first setup.

The board is connected to a normal router or switch network. The router gives it an IP address through DHCP. The host service addresses the board by hostname, so the exact DHCP lease does not need to be known in advance.

FDCAN config is owned by the host JSON. This is convenient because changing bitrate, period, or enabled buses only requires editing the host config and restarting the service.

## Files

- Copy [`sd_config.json`](./sd_config.json) to the SD-card root as `config.json`.
- Copy [`host_config.json`](./host_config.json) to `/opt/voltbro/ethernet-can/ethernetcan1.json`.

## How It Works

The SD `config.json` only sets board identity:

- hostname: `ethernetcan1.local`;
- DHCP enabled.

The host JSON contains:

- `network.host_ip`: IP address of the Linux host on the Ethernet-CAN network;
- `network.device_ip`: board hostname;
- `network.host_interface_map`: SocketCAN interface mapping;
- `fdcan`: period and CAN-FD bitrates.

Because `fdcan` is present, the launcher sends `PUT /api/v1/config` at startup. The board applies the config and saves it as `runtime.json`.

## Steps

1. Format the SD card as FAT.
2. Put `sd_config.json` on the card as `config.json`.
3. Insert the SD card and power the board.
4. Check that the board resolves:

```bash
getent hosts ethernetcan1.local
curl http://ethernetcan1.local/api/v1/status
```

5. Install `host_config.json`:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/ethernetcan1.json
sudo systemctl restart ethernet-can.service
```

6. Check logs and CAN data:

```bash
journalctl -u ethernet-can.service -f
candump vcan1.0
```

## Notes

If hostname resolution fails on Linux, check that `libnss-mdns` and Avahi are installed and that `hosts:` in `/etc/nsswitch.conf` contains `mdns4_minimal`.
