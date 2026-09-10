#!/usr/bin/env bash
# Install the latest stable release, regardless of where this script came from.
main() (
    set -euo pipefail
    if (( $# != 0 )); then
        echo 'Usage: bash install.sh' >&2
        exit 1
    fi
    for command in dpkg wget sha256sum mktemp apt; do
        command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
    done
    arch=$(dpkg --print-architecture)
    case "$arch" in
        amd64|arm64) ;;
        *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
    esac
    privilege=()
    if (( EUID != 0 )); then
        command -v sudo >/dev/null || { echo 'sudo is required' >&2; exit 1; }
        sudo -v </dev/null
        privilege=(sudo)
    fi
    install_dir=$(mktemp -d /tmp/ethernet-can-install.XXXXXX)
    trap 'rm -rf -- "$install_dir"' EXIT
    cd "$install_dir"
    asset="ethernet-can-host_${arch}.deb"
    url='https://github.com/VBCores/ethernet-can/releases/latest/download'
    echo "Installing latest stable ethernet-can-host (${arch})"
    wget -q -O "$asset" "$url/$asset"
    wget -q -O SHA256SUMS "$url/SHA256SUMS"
    sha256sum --strict --ignore-missing -c SHA256SUMS
    "${privilege[@]}" apt update </dev/null
    "${privilege[@]}" apt install -y "./$asset" </dev/null
    echo 'Installed. For first setup, follow /opt/voltbro/ethernet-can/docs/README.md.'
)

# Keep invocation last: Bash must parse the complete function before installing.
main "$@"
