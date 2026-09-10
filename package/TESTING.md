# Debian package verification

2026-09-10: existing Ubuntu 24.04.3 arm64 VM only.

- Local CPack Release build: PASS; automatic shlibdeps verified.
- Published builds use Ubuntu 22.04 in CI; amd64 and arm64 builds passed.
- Launcher unit tests: 6/6 PASS.
- UDP/SocketCAN regression in isolated network namespace: 38/38 PASS (Release, no ASan).
- RC1 to RC2: active service restarted, enabled preserved.
- Reinstall stopped/enabled and stopped/disabled: both states preserved.
- Removal: service stopped, user JSON preserved.
- Install after removal: no automatic start or enable.
- DNS PID unchanged throughout new-package lifecycle tests.
- Maintainer scripts without systemd: PASS in private mount namespace with empty /run.
- policy-rc.d respected; restored after lifecycle tests.
- Final installed version: 0.3.0~rc2, service enabled/running.

User router.json SHA-256 unchanged:
1a34ec36dd85c7986b041f72975b151db41369567ae88bcfccef6cd399f79ccd.

The experimental 0.1.0 package's old scripts disable the service and restart
DNS during upgrade. Its obsolete DNS file is removed by dpkg. Initial migration
was backed up in /tmp/ethcan-before-rc.4sgaKb on the VM; original DNS file and
service state restored. Subsequent RC lifecycle tests have no such side effects.

Ubuntu 22.04 runtime and amd64 runtime are not tested; no additional VM created.
GitHub release v0.3.0-rc.2 is published as a prerelease, not latest.
Workflow: https://github.com/VBCores/ethernet-can/actions/runs/34480536755
The downloaded arm64 package passed SHA256SUMS verification and the full
lifecycle test on this VM; its installed binary passed UDP regression 38/38.
Its generated dependencies include libc6 >= 2.34 and libstdc++6 >= 11.
Downloaded arm64 SHA-256:
a21c4cc361e03bc123c864dc4bc148c9de13466884acd9149d5109c48eaa1ce5.
Evidence on the VM: /tmp/ethcan-github-rc2.inDiK7/udp-test/summary.json.
The original router.json hash is unchanged; service is enabled/running.
master remains 39cf304; stable latest remains 0.2.1.

Reproduce lifecycle checks on this configured test VM with:
sudo python3 tests/package_lifecycle.py /absolute/path/to/ethernet-can-host_arm64.deb

The lifecycle test mutates package/service state and restores policy and the
enabled/running service in finally. Do not run it on an unrelated machine.
