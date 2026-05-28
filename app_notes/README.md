# Ethernet-CAN App Notes

These notes show complete configuration scenarios. Start with the main [README](../README.md) for the device model, then pick the closest setup here.

| Scenario | Use when |
| --- | --- |
| [Router DHCP Host Managed](./router_dhcp_host_managed/Router%20DHCP%20Host%20Managed.md) | Recommended first setup. Router gives the board an address, host uses the board hostname, host JSON owns FDCAN config. |
| [P2P Static](./p2p_static/P2P%20Static.md) | Direct cable or isolated Ethernet link, no DHCP, fixed host and board IP addresses. |
| [Web Panel Runtime Config](./web_config_runtime/Web%20Panel%20Runtime%20Config.md) | User configures FDCAN once through `/panel`; host only starts the listener. |
| [SD Locked Config](./sd_locked_config/SD%20Locked%20Config.md) | FDCAN config must be fixed on the board and protected from host or panel changes. |
| [Multiple Boards Web Config](./multiple_boards_web_config/Multiple%20Boards%20Web%20Config.md) | Several boards use different hostnames and are configured through their web panels. |
| [Mixed Config](./mixed_config/Mixed%20Config.md) | One host service runs both host-managed and board-managed boards. |

Each scenario folder contains the JSON files referenced by the note. English and Russian notes use the same JSON examples.
