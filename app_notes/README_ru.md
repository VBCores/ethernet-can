# App notes Ethernet-CAN

Здесь собраны готовые сценарии конфигурации. Сначала прочитайте основной [README](../README_ru.md), чтобы понять модель устройства, затем выберите ближайший сценарий.

| Сценарий | Когда использовать |
| --- | --- |
| [Router DHCP Host Managed](./router_dhcp_host_managed/Router%20DHCP%20Host%20Managed_ru.md) | Рекомендуемый первый запуск. Роутер выдает плате адрес, host использует hostname платы, host JSON владеет FDCAN config. |
| [P2P Static](./p2p_static/P2P%20Static_ru.md) | Прямой кабель или изолированный Ethernet, без DHCP, фиксированные IP host и платы. |
| [Web Panel Runtime Config](./web_config_runtime/Web%20Panel%20Runtime%20Config_ru.md) | Пользователь один раз настраивает FDCAN через `/panel`; host только запускает listener. |
| [SD Locked Config](./sd_locked_config/SD%20Locked%20Config_ru.md) | FDCAN config должен быть зафиксирован на плате и защищен от изменений host/panel. |
| [Multiple Boards Web Config](./multiple_boards_web_config/Multiple%20Boards%20Web%20Config_ru.md) | Несколько плат с разными hostnames, настройка через web panels. |
| [Mixed Config](./mixed_config/Mixed%20Config_ru.md) | Один host service запускает и host-managed, и board-managed платы. |

В каждой папке лежат JSON-файлы, на которые ссылается note. Английская и русская версии используют одни и те же JSON examples.
