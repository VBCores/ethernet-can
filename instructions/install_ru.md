# Установка клиента на Linux

[English](install.md)

[Выбор подключения](../README_ru.md)

Выполните один раз на компьютере, который будет принимать CAN. Команды рассчитаны на Ubuntu/Debian с systemd. В VM Ethernet-адаптер платы должен быть доступен самой VM; адрес macOS/Windows вместо адреса VM не подойдёт.

1. Установите зависимости:

   ```bash
   sudo apt update
   sudo apt install -y git build-essential cmake python3 python3-requests python3-tenacity python3-systemd can-utils iproute2 kmod curl libnss-mdns avahi-daemon
   sudo systemctl enable --now avahi-daemon
   ```

2. Скачайте и соберите клиент. Если репозиторий уже скачан, перейдите в его каталог вместо повторного `git clone`.

   ```bash
   git clone --recurse-submodules https://github.com/VBCores/ethernet-can
   cd ethernet-can
   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
   cmake --build build -j2
   sudo cmake --install build
   ```

3. Установите службу:

   ```bash
   sudo install -m 0644 /opt/voltbro/ethernet-can/systemd/ethernet-can.service /etc/systemd/system/ethernet-can.service
   sudo systemctl daemon-reload
   ```

4. Вернитесь к выбранной инструкции и создайте конфигурацию. Запускайте службу после этого.

Все дальнейшие команды с путями `instructions/...` выполняйте из корня скачанного репозитория. Файлы `host_config.json` — примеры, а рабочий файл одной платы — `/opt/voltbro/ethernet-can/ethernetcan.json`.

Служба читает **все `*.json`** непосредственно в `/opt/voltbro/ethernet-can`. Для одной платы оставьте там один рабочий JSON. Старые конфиги и резервные копии перенесите в отдельный каталог; иначе клиент попробует запустить и их. При смене сценария остановите службу, замените конфиг и запустите её снова. Не запускайте одновременно второй ручной клиент.
