# Зафиксировать настройки на SD

[English](README.md)

[Выбор подключения](../../README_ru.md) · [Установка клиента](../install_ru.md)

Команды выполняйте из корня репозитория после установки клиента. Пример включает только bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, период 10 мс. Выставьте скорости вашего CAN-устройства; для classic CAN укажите `data_kbit: 0`.

1. Подключите плату и компьютер к одному роутеру с DHCP. Подключите CAN-устройство к bus0 и подайте питание, соблюдая [правила подключения](../../README_ru.md#плата-питание-и-подключение-can).
2. Выполните `ip -4 -br address`. Найдите IPv4 компьютера в сети платы и запишите его. В примерах `192.168.2.2` — **адрес компьютера, не платы**; замените его своим адресом. Закрепите этот адрес для компьютера в DHCP-настройках роутера.
3. Отредактируйте [config.json](config.json): в `data_plane.host_ip` впишите IP компьютера, в `buses` — скорости и включённые шины. Явно заданные runtime-поля будут защищены от изменения через REST/панель.
4. Скопируйте файл в корень FAT/FAT32 SD под именем `config.json`. Безопасно извлеките карту, вставьте в выключенную плату и включите её.
5. Проверьте связь:

   ```bash
   getent ahostsv4 ethernetcan.local
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   ```

   Если имя не найдено, посмотрите IP платы в списке DHCP-клиентов роутера. Используйте этот IP вместо `ethernetcan.local` в командах, браузере и `network.device_ip`.

   В status должны быть `sd_mounted=true`, `config_json_present=true`, `runtime_flash_valid=true` и `fdcan.config_applied=true`.
6. Установите конфиг клиента:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/sd_locked_config/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Укажите тот же IP компьютера. Если изменили список шин на SD, согласуйте `host_interface_map`. Секцию `fdcan` не добавляйте.
7. Запустите клиент:

   ```bash
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```
8. Проверьте результат:

   ```bash
   systemctl status ethernet-can.service --no-pager
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   candump vcan1.0
   ```

   Ожидайте службу `active (running)` и `fdcan.config_applied=true`. В `candump` появятся кадры, если подключённое CAN-устройство их передаёт. Остановить просмотр — Ctrl+C. Если кадров нет, откройте [диагностику](../../README_ru.md#troubleshooting--если-что-то-не-работает).

Конфликтующее изменение через панель/REST вернёт `409 Conflict`. Для изменения зафиксированных полей отредактируйте SD и перезапустите плату. При удалении SD блокировки исчезнут после перезапуска, но сохранённые во Flash настройки CAN останутся.
