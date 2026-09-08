# Первый запуск: через роутер, без SD

[English](README.md)

[Выбор подключения](../../README_ru.md) · [Установка клиента](../install_ru.md)

Команды выполняйте из корня репозитория после установки клиента. Пример включает только bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, период 10 мс. Выставьте скорости вашего CAN-устройства; для classic CAN укажите `data_kbit: 0`.

1. Подключите плату Ethernet-кабелем к LAN-порту роутера. Компьютер подключите к тому же роутеру, предпочтительно кабелем. На роутере должен работать DHCP; гостевая сеть с изоляцией устройств не подходит. SD-карту не вставляйте.
2. Подключите CAN-устройство к bus0 и подайте питание, соблюдая [правила подключения](../../README_ru.md#плата-питание-и-подключение-can).
3. Выполните `ip -4 -br address`. Найдите IPv4 компьютера в сети платы и запишите его. В примерах `192.168.2.2` — **адрес компьютера, не платы**; замените его своим адресом. Закрепите этот адрес для компьютера в DHCP-настройках роутера.
4. Проверьте связь:

   ```bash
   getent ahostsv4 ethernetcan.local
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   ```

   Если имя не найдено, посмотрите IP платы в списке DHCP-клиентов роутера. Используйте этот IP вместо `ethernetcan.local` в командах, браузере и `network.device_ip`.
5. Установите пример и откройте рабочий файл:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/router_no_sd/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Замените `network.host_ip` своим IPv4, проверьте скорости в `fdcan`. Имя `ethernetcan.local` оставьте стандартным. Сохраните файл.
6. Запустите клиент. Он сам настроит CAN на плате и сохранит настройки во Flash:

   ```bash
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```
7. Проверьте результат:

   ```bash
   systemctl status ethernet-can.service --no-pager
   curl --max-time 5 http://ethernetcan.local/api/v1/status
   candump vcan1.0
   ```

   Ожидайте службу `active (running)` и `fdcan.config_applied=true`. В `candump` появятся кадры, если подключённое CAN-устройство их передаёт. Остановить просмотр — Ctrl+C. Если кадров нет, откройте [диагностику](../../README_ru.md#troubleshooting--если-что-то-не-работает).

Готово. После перезапуска плата помнит настройки CAN без SD. Компьютер и клиент всё равно нужны для обмена через SocketCAN. Простой свитч без DHCP-сервера не заменяет роутер: для такой сети используйте [статические IP](../p2p_static/README_ru.md).
