# P2P Static

Use this scenario for a direct Ethernet cable or an isolated network with no DHCP server.

The board receives a fixed IP from SD `config.json`. The host interface must also be configured with a fixed IP in the same subnet.

## Files

- Copy [`sd_config.json`](./sd_config.json) to the SD-card root as `config.json`.
- Copy [`host_config.json`](./host_config.json) to `/opt/voltbro/ethernet-can/p2p.json`.
- Use [`../../extra/10-ethernet-can.yaml`](../../extra/10-ethernet-can.yaml) as the netplan template if your host uses netplan.

## Addresses

- Host: `10.0.0.1/24`
- Board: `10.0.0.2/24`
- Board hostname: `ethernetcan-p2p.local`

The host JSON uses literal `10.0.0.2`. You can use `ethernetcan-p2p.local` instead if mDNS is available on the host.

## Steps

1. Put `sd_config.json` on the SD card as `config.json`.
2. Configure the host Ethernet interface as `10.0.0.1/24`.
3. Connect the board directly to the host.
4. Verify connectivity:

```bash
ping 10.0.0.2
curl http://10.0.0.2/api/v1/status
```

5. Install the host JSON and restart the service:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/p2p.json
sudo systemctl restart ethernet-can.service
```

6. Check CAN data:

```bash
candump vcan1.0
```

## Notes

Keep the host IP stable. The board sends UDP data to `network.host_ip` from its applied runtime config.
