# Multiple Boards Web Config

Используйте этот сценарий, когда несколько плат настроены вручную через web panels, а один host service слушает их все.

У каждой платы свой hostname. В каждом host JSON нет `fdcan`, поэтому launcher ждет persisted runtime config от каждой платы.

## Файлы

Для board 1:

- SD: [`board1_sd_config.json`](./board1_sd_config.json) как `config.json`
- Host: [`board1_host_config.json`](./board1_host_config.json) как `/opt/voltbro/ethernet-can/board1.json`

Для board 2:

- SD: [`board2_sd_config.json`](./board2_sd_config.json) как `config.json`
- Host: [`board2_host_config.json`](./board2_host_config.json) как `/opt/voltbro/ethernet-can/board2.json`

## Как это работает

Обе платы используют DHCP и mDNS:

- `ethernetcan-1.local`
- `ethernetcan-2.local`

Host использует один общий `network.host_ip`. Имена интерфейсов не должны пересекаться между платами. В этом примере board 1 использует `vcan1.x`, а board 2 использует `vcan2.x`.

## Шаги

1. Подготовьте отдельную SD-карту для каждой платы.
2. Включите обе платы.
3. Откройте panel каждой платы и примените ее FDCAN runtime config:

```text
http://ethernetcan-1.local/panel
http://ethernetcan-2.local/panel
```

4. Установите оба host JSON:

```bash
sudo install -m 0644 board1_host_config.json /opt/voltbro/ethernet-can/board1.json
sudo install -m 0644 board2_host_config.json /opt/voltbro/ethernet-can/board2.json
sudo systemctl restart ethernet-can.service
```

5. Проверьте traffic:

```bash
candump vcan1.0
candump vcan2.0
```

## Примечания

Host service bind-ит один UDP socket на общий host IP. Платы различаются по UDP source IP, поэтому каждый hostname должен резолвиться в отдельный адрес.
