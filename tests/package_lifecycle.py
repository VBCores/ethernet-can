#!/usr/bin/env python3
"""Run explicitly on the existing test VM as root; restores policy and service."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

package = str(Path(sys.argv[1]).resolve())
assert Path(package).is_file()
def run(*args):
    return subprocess.check_output(args, text=True).strip()

def pid(unit):
    return run("systemctl", "show", unit, "-p", "MainPID", "--value")

config = Path("/opt/voltbro/ethernet-can/router.json")
digest = hashlib.sha256(config.read_bytes()).hexdigest()
dns_pid = pid("systemd-resolved.service")
policy = Path("/usr/sbin/policy-rc.d")
backup = Path(tempfile.mkdtemp(prefix="ethcan-policy-")) / "policy-rc.d"
had_policy = policy.exists()
if had_policy:
    policy.rename(backup)
try:
    run("systemctl", "enable", "--now", "ethernet-can.service")
    before = pid("ethernet-can.service")
    assert before != "0"
    run("apt-get", "install", "-y", "--reinstall", package)
    after = pid("ethernet-can.service")
    assert after not in ("0", before), (before, after)
    assert run("systemctl", "is-enabled", "ethernet-can.service") == "enabled"
    print("PASS active reinstall: PID changed, enabled preserved", flush=True)
    run("systemctl", "stop", "ethernet-can.service")
    run("apt-get", "install", "-y", "--reinstall", package)
    assert pid("ethernet-can.service") == "0"
    assert run("systemctl", "is-enabled", "ethernet-can.service") == "enabled"
    print("PASS inactive reinstall: stopped, enabled preserved", flush=True)
    run("systemctl", "disable", "ethernet-can.service")
    run("apt-get", "install", "-y", "--reinstall", package)
    assert pid("ethernet-can.service") == "0"
    assert subprocess.run(["systemctl", "is-enabled", "--quiet", "ethernet-can.service"]).returncode != 0
    print("PASS disabled reinstall: stopped, disabled preserved", flush=True)
    run("systemctl", "enable", "--now", "ethernet-can.service")
    run("apt-get", "remove", "-y", "ethernet-can-host")
    assert pid("ethernet-can.service") == "0"
    assert hashlib.sha256(config.read_bytes()).hexdigest() == digest
    print("PASS removal: stopped, user config retained", flush=True)
    run("apt-get", "install", "-y", package)
    assert pid("ethernet-can.service") == "0"
    assert subprocess.run(["systemctl", "is-enabled", "--quiet", "ethernet-can.service"]).returncode != 0
    assert hashlib.sha256(config.read_bytes()).hexdigest() == digest
    assert pid("systemd-resolved.service") == dns_pid
    print("PASS fresh install: no autostart, config and DNS PID unchanged", flush=True)
finally:
    if had_policy:
        backup.rename(policy)
    state = subprocess.run(["dpkg-query", "-W", "-f=${Status}", "ethernet-can-host"], capture_output=True, text=True)
    if state.stdout != "install ok installed":
        run("apt-get", "install", "-y", package)
    run("systemctl", "enable", "--now", "ethernet-can.service")
    print("Restored policy and enabled/running service", flush=True)
