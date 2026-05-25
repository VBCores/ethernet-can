# Mixed Config

Используйте этот сценарий, когда один Linux host service запускает платы с разными стилями владения config.

В примере:

- `ethernetcan-host.local` управляется host. Его host JSON содержит `fdcan`.
- `ethernetcan-panel.local` управляется платой. В его host JSON нет `fdcan`, поэтому на плате уже должен быть applied `runtime.json`.

## Файлы

Для host-managed платы:

- SD: [`host_managed_sd_config.json`](./host_managed_sd_config.json) как `config.json`
- Host: [`host_managed_host_config.json`](./host_managed_host_config.json) как `/opt/voltbro/ethernet-can/host-managed.json`

Для board-managed платы:

- SD: [`board_managed_sd_config.json`](./board_managed_sd_config.json) как `config.json`
- Host: [`board_managed_host_config.json`](./board_managed_host_config.json) как `/opt/voltbro/ethernet-can/board-managed.json`

## Шаги

1. Подготовьте обе платы с их SD configs.
2. Один раз настройте `ethernetcan-panel.local` через `/panel`, чтобы плата сохранила `runtime.json`.
3. Установите оба host JSON:

```bash
sudo install -m 0644 host_managed_host_config.json /opt/voltbro/ethernet-can/host-managed.json
sudo install -m 0644 board_managed_host_config.json /opt/voltbro/ethernet-can/board-managed.json
sudo systemctl restart ethernet-can.service
```

## Ожидаемое поведение

Launcher отправляет REST config только на `ethernetcan-host.local`. Для `ethernetcan-panel.local` он ждет существующий board-applied config и затем запускает data listener.

Обе платы используют общий `network.host_ip`, но имена SocketCAN interfaces не пересекаются.
