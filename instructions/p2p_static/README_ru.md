# Прямой кабель: компьютер ↔ плата

[English](README.md)

[Выбор подключения](../../README_ru.md) · [Установка клиента](../install_ru.md)

Команды выполняйте из корня репозитория после установки клиента. Пример включает только bus0 → `vcan1.0`, CAN FD `1000/8000 kbit/s`, период 10 мс. Выставьте скорости вашего CAN-устройства; для classic CAN укажите `data_kbit: 0`.

В этом сценарии SD задаёт фиксированный IP платы. Роутер и DHCP не нужны. Без SD стандартная прошивка ожидает DHCP; для первого запуска без SD выберите [роутер](../router_no_sd/README_ru.md).

1. Подключите CAN-устройство к bus0 и подайте питание, соблюдая [правила подключения](../../README_ru.md#плата-питание-и-подключение-can). Соедините Ethernet-порт платы с отдельным Ethernet-портом компьютера.
2. Подготовьте FAT/FAT32 SD. Скопируйте [sd_config.json](sd_config.json) в её корень под именем `config.json`. Безопасно извлеките карту, вставьте в выключенную плату и включите её. Плата получит `10.0.0.2/24`.
3. Настройте на компьютере **порт, подключённый к плате**, как `10.0.0.1/24`, без шлюза и DNS. В настройках сети Linux выберите этот проводной профиль → IPv4 → вручную → адрес `10.0.0.1`, маска `255.255.255.0`, шлюз пустой → сохранить и переподключить профиль. Сначала убедитесь, что `10.0.0.0/24` не занята другой сетью/VPN; иначе согласованно смените подсеть в обоих JSON и на компьютере. Для netplan есть [шаблон](../../extra/10-ethernet-can.yaml): замените `INTERFACE_NAME` именем из `ip -br link`, объедините с действующей конфигурацией и используйте `sudo netplan try`.
4. Проверьте `curl --max-time 5 http://10.0.0.2/api/v1/status`.
5. Установите пример:

   ```bash
   sudo systemctl stop ethernet-can.service
   sudo install -m 0644 instructions/p2p_static/host_config.json /opt/voltbro/ethernet-can/ethernetcan.json
   sudo nano /opt/voltbro/ethernet-can/ethernetcan.json
   ```

   Здесь IP уже согласованы: компьютер `10.0.0.1`, плата `10.0.0.2`. Проверьте скорости CAN и сохраните файл.
6. Запустите клиент:

   ```bash
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```
7. Проверьте результат:

   ```bash
   systemctl status ethernet-can.service --no-pager
   curl --max-time 5 http://10.0.0.2/api/v1/status
   candump vcan1.0
   ```

   Ожидайте службу `active (running)` и `fdcan.config_applied=true`. В `candump` появятся кадры, если подключённое CAN-устройство их передаёт. Остановить просмотр — Ctrl+C. Если кадров нет, откройте [диагностику](../../README_ru.md#troubleshooting--если-что-то-не-работает).
