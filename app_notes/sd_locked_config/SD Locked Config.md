# SD Locked Config

Use this scenario when the board must own and lock the FDCAN config.

The SD `config.json` contains both network identity and runtime FDCAN fields. Fields explicitly present in `config.json` are locked. If a host or panel sends a conflicting `PUT /api/v1/config`, firmware rejects it with `409 Conflict`.

## Files

- Copy [`config.json`](./config.json) to the SD-card root as `config.json`.
- Copy [`host_config.json`](./host_config.json) to `/opt/voltbro/ethernet-can/locked.json`.

## How It Works

At boot, the board reads `config.json`, builds a full runtime config from the locked fields and defaults, applies it, and saves normalized `runtime.json`.

The host JSON has no `fdcan`, so the launcher does not send config. It waits for the board-applied config and starts the data listener.

## Steps

1. Put `config.json` on the SD card.
2. Boot the board.
3. Check status:

```bash
curl http://ethernetcan-locked.local/api/v1/status
```

Expected state:

- `persistence.config_json_present`: `true`
- `persistence.runtime_json_valid`: `true`
- `fdcan.config_applied`: `true`

4. Install host JSON and restart the service:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/locked.json
sudo systemctl restart ethernet-can.service
```

## Notes

Use this mode for production setups where FDCAN bitrate and enabled buses should not be accidentally changed from the host.
