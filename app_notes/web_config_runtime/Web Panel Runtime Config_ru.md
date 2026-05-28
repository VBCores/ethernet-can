# Web Panel Runtime Config

Используйте этот сценарий, когда плата должна сама помнить FDCAN config, а host должен только запускать data listener.

В host JSON намеренно нет секции `fdcan`. Это говорит launcher не отправлять config. Вместо этого он ждет, пока плата сообщит об applied runtime config, затем запускает C++ data plane с period, прочитанным с платы.

## Файлы

- Скопируйте [`sd_config.json`](./sd_config.json) в корень SD-карты как `config.json`.
- Скопируйте [`host_config.json`](./host_config.json) в `/opt/voltbro/ethernet-can/panel.json`.

## Первичная настройка платы

1. Откройте panel:

```text
http://ethernetcan-panel.local/panel
```

2. Отредактируйте config JSON в panel. Минимальный пример для bus0:

```json
{
  "data_plane": {
    "host_ip": "192.168.2.2"
  },
  "frames_integration_period_ns": 10000000,
  "buses": [
    {"bus": 0, "enabled": true, "nominal_kbit": 1000, "data_kbit": 8000},
    {"bus": 1, "enabled": false},
    {"bus": 2, "enabled": false},
    {"bus": 3, "enabled": false},
    {"bus": 4, "enabled": false},
    {"bus": 5, "enabled": false}
  ]
}
```

3. Нажмите Apply. Плата запишет `runtime.json`.
4. Перезагрузите или перепитайте плату и проверьте `GET /api/v1/status`: `fdcan.config_applied` должен быть `true`.

## Запуск host

Установите listener-only host JSON:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/panel.json
sudo systemctl restart ethernet-can.service
```

Launcher будет ждать config на плате. Если во время ручной настройки нужно ждать бесконечно, задайте:

```bash
ETHERNET_CAN_CONFIG_WAIT_TIMEOUT_SECONDS=-1
```

## Примечания

Если на плате нет валидного `runtime.json`, этот режим не запустит host listener, пока config не будет применен через panel.
