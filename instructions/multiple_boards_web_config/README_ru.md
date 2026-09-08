# Несколько плат: настройка через браузер

[English](README.md)

[Выбор подключения](../../README_ru.md) · [Установка клиента](../install_ru.md)

Сначала проверьте [одну плату без SD](../router_no_sd/README_ru.md). Здесь обе платы подключаются к одному роутеру с DHCP, а на компьютере работает одна служба. Для двух плат нужны разные адреса: в этом примере SD задаёт имена `ethernetcan-1.local` и `ethernetcan-2.local`. Это явные настройки примера, а не заводские имена. Альтернатива без SD — закрепить разные IP плат на роутере и вписать их в host JSON вместо имён.

1. Установите клиент. Подключите обе платы и компьютер к LAN роутера. Подключите CAN-устройство к bus0 каждой платы по [правилам подключения](../../README_ru.md#плата-питание-и-подключение-can).
2. Найдите IP компьютера командой `ip -4 -br address` и закрепите его на роутере. Замените `192.168.2.2` этим адресом в **обоих** файлах: [board1_host_config.json](board1_host_config.json) и [board2_host_config.json](board2_host_config.json). Интерфейсы уже разделены: bus0 первой платы → `vcan1.0`, второй → `vcan2.0`.
3. На отдельную FAT/FAT32 SD первой платы скопируйте [board1_sd_config.json](board1_sd_config.json) как `config.json`; на SD второй — [board2_sd_config.json](board2_sd_config.json) с тем же именем. Безопасно извлеките карты, вставьте в выключенные платы и включите их.
4. Проверьте адреса:

   ```bash
   getent ahostsv4 ethernetcan-1.local
   getent ahostsv4 ethernetcan-2.local
   ```

   Они должны различаться. Если имя не найдено, найдите IP платы на роутере и используйте его в соответствующем JSON и браузере.
5. Остановите службу: `sudo systemctl stop ethernet-can.service`. Откройте по очереди `http://ethernetcan-1.local/panel` и `http://ethernetcan-2.local/panel`. В поле JSON панели вставьте [runtime_config.json](runtime_config.json), замените `data_plane.host_ip` тем же IP компьютера, проверьте скорости CAN и нажмите Apply. Пример включает только bus0; другие шины выключены. Для classic CAN установите `data_kbit: 0`. Дождитесь `fdcan.config_applied=true`.
6. Перенесите старый конфиг одной платы из `/opt/voltbro/ethernet-can` в отдельный каталог резервных копий: служба читает все JSON из своего каталога. Установите два новых файла:

   ```bash
   sudo install -m 0644 instructions/multiple_boards_web_config/board1_host_config.json /opt/voltbro/ethernet-can/board1.json
   sudo install -m 0644 instructions/multiple_boards_web_config/board2_host_config.json /opt/voltbro/ethernet-can/board2.json
   sudo systemctl enable ethernet-can.service
   sudo systemctl restart ethernet-can.service
   ```

7. Проверьте `systemctl status ethernet-can.service --no-pager`. В двух терминалах запустите `candump vcan1.0` и `candump vcan2.0`. При передаче CAN-устройствами должны появляться кадры. Ctrl+C завершает просмотр.

В host JSON нет `fdcan`: клиент ждёт сохранённых настроек каждой платы. Все платы должны использовать один IP компьютера, но разные IP плат и разные имена интерфейсов. При изменении включённых шин согласуйте карты интерфейсов; после смены classic/FD перезапустите службу.
