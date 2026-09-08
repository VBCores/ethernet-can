# Настройка через браузер, без SD

[English](README.md)

[Выбор подключения](../../README_ru.md) · [Установка клиента](../install_ru.md)

Команды выполняйте из корня репозитория после установки клиента. Пример включает только bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, период 10 мс. Выставьте скорости вашего CAN-устройства; для classic CAN укажите `data_kbit: 0`.

1. Подключите плату и компьютер к одному роутеру с DHCP. Оставьте SD-слот пустым.
2. Подключите CAN-устройство к bus0 и подайте питание, соблюдая [правила подключения](../../README_ru.md#плата-питание-и-подключение-can).
3. Выполните `ip -4 -br address`. Найдите IPv4 компьютера в сети платы и запишите его. В примерах `192.168.2.2` — **адрес компьютера, не платы**; замените его своим адресом. Закрепите этот адрес для компьютера в DHCP-настройках роутера.
4. Проверьте связь:

   ```bash
   getent ahostsv4 ethernetcan.local
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   ```

   Если имя не найдено, посмотрите IP платы в списке DHCP-клиентов роутера. Используйте этот IP вместо `ethernetcan.local` в командах, браузере и `network.device_ip`.
5. Остановите службу: `sudo systemctl stop ethernet-can.service`. Откройте `http://ethernetcan.local/panel`. В поле JSON вставьте содержимое [runtime_config.json](runtime_config.json), замените `data_plane.host_ip` адресом компьютера, выставьте скорости CAN и нажмите Apply. Дождитесь `fdcan.config_applied=true` в status. Настройки сохранятся во Flash.
6. Установите конфиг клиента:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/web_config_runtime/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Впишите тот же IP компьютера в `network.host_ip`. Здесь **нет секции `fdcan`**: настройки берутся с платы. Не добавляйте её, если хотите продолжать настраивать плату через браузер.
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

При изменении набора включённых шин обновите `host_interface_map` в конфиге клиента. После изменения режима classic/FD перезапустите службу, чтобы она перечитала режим.
