# Плата Ethernet-CAN

**[http://vbcores.com/products/ethernet-can](http://vbcores.com/products/ethernet-can)**

![Ethernet-CAN](./extra/images/ethernet-can.png)

## Что это за устройство

Ethernet-CAN - это IP-устройство с шестью логическими CAN-FD шинами. На плате два MCU:

- STM32H7 отвечает за Ethernet, HTTP REST, веб-панель, SD-конфиг и CAN-шины `0..2`.
- STM32G4 подключен к H7 по SPI и отвечает за CAN-шины `3..5`.

Плата работает как обычное IP-устройство. По умолчанию она может получить адрес через DHCP и быть доступной по mDNS имени, например `ethernetcan.local`. Если в сети нет DHCP или нужны фиксированные параметры, положите `config.json` на SD-карту и задайте там статический IP, hostname, MAC, netmask, gateway или другие сетевые поля.

Плата предоставляет:

- `GET /api/v1/status`: сеть, FDCAN, счетчики, reset/watchdog diagnostics, состояние SD persistence.
- `GET /api/v1/config`: текущий примененный runtime config.
- `PUT /api/v1/config`: применить runtime config и сохранить его как `runtime.json`.
- `/panel`: простая веб-панель статуса и настройки.

Сами CAN-данные идут по UDP. HTTP используется только для конфигурации и статуса.

## Модель host service

Linux host service создает канал данных между платой и SocketCAN. Ему нужны:

- IP адрес хоста;
- адрес платы, literal IPv4 или hostname;
- карта bus number -> Linux CAN interface.

Python launcher читает host JSON, готовит VCAN-интерфейсы, при необходимости конфигурирует плату через REST и запускает C++ data-plane процесс. C++ процесс не читает JSON и не конфигурирует плату; он только пересылает UDP CAN frames в SocketCAN и обратно.

Host поддерживает несколько плат за одним общим host IP. Для каждой платы нужен отдельный host JSON, а входящие UDP-пакеты различаются по source IP.

## Кто владеет FDCAN конфигом

Выберите один стиль для каждой платы.

| Стиль | Где живет FDCAN config | В host JSON есть `fdcan` | Когда использовать |
| --- | --- | --- | --- |
| Host-managed | Host JSON | Да | Самый простой вариант для правки через Linux/systemd config. Launcher отправляет REST config при старте и переотправляет его при healthcheck mismatch. |
| Web/panel-managed | `runtime.json` на плате | Нет | Пользователь один раз настраивает плату через `/panel`; дальше host только запускает listener. |
| SD-locked | SD `config.json` | Нет | Жестко зафиксированный конфиг на стороне платы. Явно заданные в `config.json` поля locked; конфликтующий REST config отклоняется. |

На SD-карте используются два файла в корне:

- `config.json`: пользовательский файл. Firmware читает его и никогда не перезаписывает.
- `runtime.json`: последний успешно примененный полный runtime config. Firmware создает и обновляет его после REST или panel config.

Если `runtime.json` валиден, плата применяет его при boot. Если файла нет, плата пытается собрать runtime config из defaults и locked-полей в `config.json`. Если результата недостаточно, REST и `/panel` все равно стартуют, но FDCAN не применяется до получения конфигурации.

Старые host INI и SD INI больше не используются.

## Рекомендуемый первый запуск

Для большинства случаев:

1. Положите на SD минимальный `config.json` с hostname и включенным DHCP.
2. Дайте роутеру выдать плате IP-адрес.
3. Используйте hostname платы как `network.device_ip` в host JSON.
4. Добавьте `fdcan` в host JSON, чтобы host service владел bitrate и period.

Полный пример: [Router DHCP Host Managed](./app_notes/router_dhcp_host_managed/Router%20DHCP%20Host%20Managed_ru.md).

Другие app notes покрывают прямое P2P-соединение со статическим IP, настройку через веб-панель, SD-locked config и несколько плат.

## Hardware

Запаяйте CAN-FD termination jumpers на обратной стороне платы так, как требуется вашей CAN-сети. Без правильной терминации CAN работать не будет.

Перед включением CAN-сети измерьте сопротивление между `CANH` и `CANL`. Должно быть около `60 Ohm`, если в сети стоят два терминатора по `120 Ohm`. Если получилось `120 Ohm`, один терминатор отсутствует.

CAN использует две сигнальные линии, но для стабильной работы также нужен общий ground reference между устройствами. Рекомендуемые цвета: `CANH` желтый, `CANL` зеленый, ground черный.

## Firmware

1. Используйте STM32CubeProgrammer и [ST-Link](https://vbcores.tilda.ws/products/vb-stlink).
2. Прошейте оба firmware image из release package: H7 и G4.
3. На G4 выставьте Option Byte `NSWBoot0` в `0` (unchecked в `OB -> Option Bytes`).

H7 firmware всегда запускает network, REST API и `/panel`, даже если FDCAN runtime config еще не доступен.

## SD-карта платы

Отформатируйте SD-карту как FAT и положите JSON-файлы в корень.

Минимальный `config.json`:

```json
{
  "network": {
    "hostname": "ethernetcan.local",
    "dhcp": true
  }
}
```

Сетевые поля в `config.json`:

- `hostname`: mDNS hostname, можно с `.local` или без.
- `dhcp`: по умолчанию `true`.
- `host_ip`: host UDP destination IP для data plane платы.
- `device_ip`, `netmask`, `gateway`: статическая адресация платы. Если задан `device_ip`, DHCP выключается.
- `mac_address`: опциональный MAC платы. Если поле не задано, firmware строит locally administered MAC из H7 hardware UID.
- `wake_on_lan_mac` или `wol_mac`: опциональная Wake-on-LAN цель.

Для locked FDCAN config в `config.json` можно добавить runtime-поля из `GET /api/v1/config`: `data_plane.host_ip`, `frames_integration_period_ns`, `buses`. Каждое явно указанное runtime-поле считается locked.

## Установка host software

Репозиторий рассчитан на сборку и установку на Linux host, который управляет одной или несколькими платами Ethernet-CAN.

Установите инструменты и runtime-компоненты:

```bash
sudo apt update
sudo apt install -y build-essential cmake libboost-program-options-dev python3 python3-systemd python3-requests python3-tenacity can-utils iproute2 kmod
```

Склонируйте, соберите и установите:

```bash
git clone --recurse-submodules https://github.com/VBCores/ethernet-can
cd ethernet-can
cmake -S . -B build
cmake --build build
sudo cmake --install build
```

Установленные файлы:

- `/opt/voltbro/ethernet-can/bin/ethernet-can`
- `/opt/voltbro/ethernet-can/bin/start_ethernet_can.py`
- `/opt/voltbro/ethernet-can/systemd/ethernet-can.service`

Host JSON configs автоматически не устанавливаются. Положите их в `/opt/voltbro/ethernet-can` или задайте `ETHERNET_CAN_CONFIGS_DIR` в systemd unit.

## Host JSON configuration

Используйте [`extra/configs/example.json`](./extra/configs/example.json) как host-managed template и [`extra/configs/example-board-managed.json`](./extra/configs/example-board-managed.json) как listener-only template.

Каждый host JSON описывает одну плату. Верхний уровень:

- `network`: обязательно.
- `fdcan`: опционально. Наличие секции означает host-managed FDCAN config.

Поля `network`:

- `host_ip`: IP Linux host для UDP data plane.
- `device_ip`: адрес платы, IPv4 или hostname вроде `ethernetcan.local`.
- `host_interface_map`: карта `bus0`..`bus5` в имена Linux CAN interfaces. Bus включен на host, если он есть в этой карте.

Поля `fdcan`:

- `period_ns`: период интеграции UDP frames в наносекундах.
- `nominal_kbit`: nominal bitrate FDCAN.
- `data_kbit`: data bitrate FDCAN. Значение `0` включает classic CAN mode.

Ручной debug start:

```bash
sudo /opt/voltbro/ethernet-can/bin/start_ethernet_can.py
```

Launcher опрашивает `GET /api/v1/status`, пока работает host data plane. В host-managed режиме он сравнивает config платы с ожидаемым JSON и отправляет `PUT /api/v1/config` после повторяющихся mismatch или no-response failures. В listener-only режиме он проверяет, что на плате есть совместимый applied config.

`ETHERNET_CAN_CONFIG_WAIT_TIMEOUT_SECONDS=-1` заставляет listener-only startup ждать board config бесконечно.

## Systemd service

Установите unit после того, как host JSON уже лежит на месте:

```bash
sudo install -m 0644 /opt/voltbro/ethernet-can/systemd/ethernet-can.service /etc/systemd/system/ethernet-can.service
sudo systemctl daemon-reload
sudo systemctl enable --now ethernet-can.service
```

Проверка логов:

```bash
systemctl status ethernet-can.service
journalctl -u ethernet-can.service -f
```

После старта launcher создает и настраивает интерфейсы из `network.host_interface_map`. Проверить данные можно так:

```bash
candump vcan1.0
```

## App notes

Конкретные сценарии лежат в [app_notes](./app_notes):

- DHCP через роутер и host-managed FDCAN config.
- Прямое point-to-point соединение со статической сетью.
- Runtime config через веб-панель.
- SD-locked board config.
- Несколько плат.
- Смешанный режим: одна плата host-managed, другая board-managed.

## Build notes для firmware developers

Host software собирается под Linux. Firmware лежит в `STM32H7-ETH-LWIP` и `STM32G4-SPI-CAN`.

H7 firmware построен вокруг STM32Cube и lwIP в superloop, без RTOS. Ethernet и первые три FDCAN-шины живут на H7. Companion G4 конфигурируется H7 по SPI и обслуживает остальные шины. Аккуратно меняйте H7 memory placement, DMA buffers, MPU/cache settings и linker scripts.

Основной путь сборки H7 - CMake. Если используете STM32CubeMX, сохраняйте user code blocks и проверяйте, что custom source files остались в проекте после regeneration.

## Troubleshooting

- `device_ip` может быть hostname. Host использует обычный Linux `getaddrinfo()`, поэтому mDNS resolution зависит от resolver setup на host, обычно `libnss-mdns`/Avahi.
- Если `/panel` открывается, но CAN не идет, проверьте `GET /api/v1/status`: `fdcan.config_applied`, bus state, queue drops и SD persistence errors.
- Если host-managed startup падает с HTTP `409`, значит SD `config.json` содержит locked-поля, конфликтующие с host JSON.
- Если listener-only startup ждет бесконечно, настройте плату через `/panel` или положите `runtime.json`/locked SD config.
- Если кадры приходят по сети, но не видны в `candump`, проверьте `network.host_interface_map`, имена интерфейсов и целевой интерфейс `candump`.
