# P2P Static

Используйте этот сценарий для прямого Ethernet-кабеля или изолированной сети без DHCP server.

Плата получает фиксированный IP из SD `config.json`. Host interface тоже должен быть настроен на фиксированный IP в той же подсети.

## Файлы

- Скопируйте [`sd_config.json`](./sd_config.json) в корень SD-карты как `config.json`.
- Скопируйте [`host_config.json`](./host_config.json) в `/opt/voltbro/ethernet-can/p2p.json`.
- Если host использует netplan, возьмите [`../../extra/10-ethernet-can.yaml`](../../extra/10-ethernet-can.yaml) как template.

## Адреса

- Host: `10.0.0.1/24`
- Плата: `10.0.0.2/24`
- Hostname платы: `ethernetcan-p2p.local`

Host JSON использует literal `10.0.0.2`. Можно заменить на `ethernetcan-p2p.local`, если на host работает mDNS.

## Шаги

1. Положите `sd_config.json` на SD-карту как `config.json`.
2. Настройте Ethernet interface host как `10.0.0.1/24`.
3. Подключите плату напрямую к host.
4. Проверьте связь:

```bash
ping 10.0.0.2
curl http://10.0.0.2/api/v1/status
```

5. Установите host JSON и перезапустите service:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/p2p.json
sudo systemctl restart ethernet-can.service
```

6. Проверьте CAN data:

```bash
candump vcan1.0
```

## Примечания

Host IP должен быть стабильным. Плата отправляет UDP data на `network.host_ip` из applied runtime config.
