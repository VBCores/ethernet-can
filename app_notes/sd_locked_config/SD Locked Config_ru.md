# SD Locked Config

Используйте этот сценарий, когда плата должна сама владеть FDCAN config и защищать его от изменений.

SD `config.json` содержит и network identity, и runtime FDCAN fields. Поля, явно присутствующие в `config.json`, считаются locked. Если host или panel отправит конфликтующий `PUT /api/v1/config`, firmware вернет `409 Conflict`.

## Файлы

- Скопируйте [`config.json`](./config.json) в корень SD-карты как `config.json`.
- Скопируйте [`host_config.json`](./host_config.json) в `/opt/voltbro/ethernet-can/locked.json`.

## Как это работает

При boot плата читает `config.json`, собирает полный runtime config из locked fields и defaults, применяет его и сохраняет normalized `runtime.json`.

В host JSON нет `fdcan`, поэтому launcher не отправляет config. Он ждет board-applied config и запускает data listener.

## Шаги

1. Положите `config.json` на SD-карту.
2. Включите плату.
3. Проверьте status:

```bash
curl http://ethernetcan-locked.local/api/v1/status
```

Ожидаемое состояние:

- `persistence.config_json_present`: `true`
- `persistence.runtime_json_valid`: `true`
- `fdcan.config_applied`: `true`

4. Установите host JSON и перезапустите service:

```bash
sudo install -m 0644 host_config.json /opt/voltbro/ethernet-can/locked.json
sudo systemctl restart ethernet-can.service
```

## Примечания

Этот режим подходит для production setups, где FDCAN bitrate и enabled buses не должны случайно меняться с host.
