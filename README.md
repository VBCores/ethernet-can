## Ethernet-CAN board

http://vbcores.com/products/ethernet-can

![Ethernet-CAN](./extra/images/ethernet-can.png)

### 1. Firmware

1. Use STM32CubeProgrammer with [ST-Link](https://vbcores.tilda.ws/products/vb-stlink) for flashing.
2. Firmware binaries: [download latest here](https://github.com/VBCores/ETH-FDCAN_firmware/releases) for BOTH H7 and G4
3. Flash BOTH H7 and G4. See named connectors on the board

### 2. Configure board SD card

1. Format an SD card as `FAT16`.
2. Put `ethernet.ini` into the SD-card root directory.
3. Use [`extra/SD-card/ethernet.ini`](./extra/SD-card/ethernet.ini) as the template.

### 3. Network configuration

TODO

### 4. Build and install on the target Linux host

> This repository is intended to be built and installed on a Linux embedded host that controls the Ethernet-CAN board.

Install required tools and runtime components:

```bash
sudo apt update
sudo apt install -y build-essential cmake libboost-program-options-dev python3 python3-systemd can-utils iproute2 kmod
```

Clone with submodules:

```bash
git clone --recurse-submodules https://github.com/VBCores/ethernet-can
cd ethernet-can
```

Build and install:

```bash
cmake -S . -B build
cmake --build build
sudo cmake --install build
```

Installed files:

- `/opt/voltbro/ethernet-can/bin/ethernet-can`
- `/opt/voltbro/ethernet-can/bin/start_ethernet_can.py`
- `/opt/voltbro/ethernet-can/example.ini`
- `/opt/voltbro/ethernet-can/systemd/ethernet-can.service`

### 5. Host INI configuration

Prefer storing host runtime `.ini` files in:

```bash
/opt/voltbro/ethernet-can
```

Use [`extra/configs/example.ini`](./extra/configs/example.ini) as the runtime template.

Manual start for debugging (runs one `ethernet-can` process per `*.ini` file in the config directory):

```bash
sudo /opt/voltbro/ethernet-can/bin/start_ethernet_can.py
```

### 6. Install and enable systemd unit

> This is a final step. You can always undo/update this, but it helps to re-check all configs, unit files, etc. in `/opt/voltbro/ethernet-can` at this point to avoid confusion

Install the unit to system from the installed location:

```bash
sudo install -m 0644 /opt/voltbro/ethernet-can/systemd/ethernet-can.service /etc/systemd/system/ethernet-can.service
sudo systemctl daemon-reload
sudo systemctl enable --now ethernet-can.service
```

Check status/logs:

```bash
systemctl status ethernet-can.service
journalctl -u ethernet-can.service -f
```

After startup, the service creates and configures `vcan0..vcan4`.

### Used libraries

- https://github.com/metayeti/mINI
