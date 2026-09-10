# Install the Linux client

[Русский](install_ru.md)

[Choose a connection](../README.md)

Packages target Ubuntu 22.04/24.04, amd64 and arm64. Internet access is needed for the package and APT dependencies. Release notes identify the combination actually tested on the stand.

## Package installation

For the latest stable release:

```bash
wget -qO- https://github.com/VBCores/ethernet-can/releases/latest/download/install.sh | bash
```

The script always installs the latest stable package, even when downloaded from
an older release. To install a specific version, download its `.deb` directly
from that release and run `sudo apt install ./package-name.deb`.
The script selects the architecture,
checks SHA-256, runs `apt update` and `apt install -y`, and removes temporary files
even on failure. Requires Bash, wget, standard Ubuntu utilities and sudo (or root).
RCs do not become `latest`; older RCs may not contain the script.

This command executes downloaded code. To inspect it first:

```bash
wget -O install.sh https://github.com/VBCores/ethernet-can/releases/latest/download/install.sh
less install.sh
bash install.sh
```

In automation, use `set -o pipefail` before the pipeline so a failed script
download also returns failure. If a VM has an obsolete `file:///cdrom` APT source,
disable that unavailable source first; the installer does not edit APT sources.

The service is installed but not started on first installation. Follow your connection guide to create a working configuration, then enable the service. To use examples without Git, copy the installed documents into a user-owned directory:

```bash
setup_dir=$(mktemp -d "$HOME/ethernet-can-setup.XXXXXX")
cp -R /opt/voltbro/ethernet-can/docs/. "$setup_dir/"
cd "$setup_dir"
```

Run guide commands containing `instructions/...` from this directory (or the repository root when building from source).

## Upgrade and removal

Repeat the download and `apt install` to upgrade. An active service restarts; an inactive service remains inactive. User JSON files are preserved. Regular `apt upgrade` does not discover GitHub releases.

`sudo apt remove ethernet-can-host` stops the service and removes the package; user JSON remains. The package does not reconfigure networking or system DNS.

The experimental `0.1.0` package shipped old scripts that disable the service during upgrade. Record the service state before upgrading from it and restore that state manually afterwards. This is a limitation of the old package.

## Build from source

```bash
sudo apt update
sudo apt install -y git build-essential cmake dpkg-dev python3 python3-requests python3-tenacity iproute2 kmod can-utils
git clone --recurse-submodules https://github.com/VBCores/ethernet-can
cd ethernet-can
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
(cd build && cpack -G DEB)
sudo apt install ./build/ethernet-can-host_$(dpkg --print-architecture).deb
```
