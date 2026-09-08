# Install the Linux client

[Русский](install_ru.md)

[Choose a connection](../README.md)

Do this once on the computer that will receive CAN. Commands target Ubuntu/Debian with systemd. In a VM, the board's Ethernet adapter must be accessible inside the VM; use the VM's IP, not the macOS/Windows host IP.

1. Install dependencies:

   ```bash
   sudo apt update
   sudo apt install -y git build-essential cmake python3 python3-requests python3-tenacity python3-systemd can-utils iproute2 kmod curl libnss-mdns avahi-daemon
   sudo systemctl enable --now avahi-daemon
   ```

2. Download and build the client. If already cloned, enter the existing repository instead of cloning again.

   ```bash
   git clone --recurse-submodules https://github.com/VBCores/ethernet-can
   cd ethernet-can
   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
   cmake --build build -j2
   sudo cmake --install build
   ```

3. Install the service:

   ```bash
   sudo install -m 0644 /opt/voltbro/ethernet-can/systemd/ethernet-can.service /etc/systemd/system/ethernet-can.service
   sudo systemctl daemon-reload
   ```

4. Return to your connection guide and create its configuration before starting the service.

Run subsequent commands containing `instructions/...` from the repository root. The `host_config.json` files are templates; the working file for one board is `/opt/voltbro/ethernet-can/ethernetcan.json`.

The service reads **every `*.json`** directly in `/opt/voltbro/ethernet-can`. For one board, keep one working JSON there. Move old configurations and backups to a separate directory or the client will try to start them too. When switching scenarios, stop the service, replace the config and start it again. Do not run a second manual client simultaneously.
