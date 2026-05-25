# Router DHCP Host Managed

Это рекомендуемый первый сценарий.

Плата подключена к обычному роутеру или switch network. Роутер выдает ей IP через DHCP. Host service обращается к плате по hostname, поэтому заранее знать DHCP lease не нужно.

FDCAN config принадлежит host JSON. Так удобнее менять bitrate, period и enabled buses: достаточно поправить host config и перезапустить service.

## Файлы

- Скопируйте [`sd_config.json`](./sd_config.json) в корень SD-карты как `config.json`.
- Скопируйте [`host_config.json`](./host_config.json) в `/opt/voltbro/ethernet-can/ethernetcan1.json`.

## Как это работает

SD `config.json` задает только identity платы:

- hostname: `ethernetcan1.local`;
- DHCP включен.

Host JSON содержит:

- `network.host_ip`: IP Linux host в сети Ethernet-CAN;
- `network.device_ip`: hostname платы;
- `network.host_interface_map`: SocketCAN interface mapping;
- `fdcan`: period и CAN-FD bitrates.

Так как секция `fdcan` присутствует, launcher при старте отправляет `PUT /api/v1/config`. Плата применяет config и сохраняет его как `runtime.json`.

## Шаги

1. Отформатируйте SD-карту как FAT.
2. Положите `sd_config.json` на карту как `config.json`.
3. Вставьте SD и включите плату.
4. Проверьте, что hostname резолвится:

```bash
getent hosts ethernetcan1.local
curl http://ethernetcan1.local/api/v1/status
```

5. Установите `host_config.json`:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/ethernetcan1.json
sudo systemctl restart ethernet-can.service
```

6. Проверьте логи и CAN data:

```bash
journalctl -u ethernet-can.service -f
candump vcan1.0
```

## Примечания

Если hostname не резолвится на Linux, проверьте, что установлены `libnss-mdns` и Avahi, а в `/etc/nsswitch.conf` строка `hosts:` содержит `mdns4_minimal`.
