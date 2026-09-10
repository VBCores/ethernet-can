"""Exercise installer failures and piped execution without running real APT."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"
MOCK = r'''#!/usr/bin/python3
import hashlib, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['INSTALL_LOG'], 'a') as log:
    log.write(name + ' ' + ' '.join(args) + '\n')
mode = os.environ.get('INSTALL_MODE', '')
if name == 'dpkg':
    print(os.environ.get('INSTALL_ARCH', 'arm64'))
elif name == 'sudo':
    if args != ['-v']:
        sys.exit(subprocess.call(args))
elif name == 'wget':
    assert args[-1].startswith('https://github.com/VBCores/ethernet-can/releases/latest/download/')
    if mode == 'download-fail': sys.exit(8)
    target = pathlib.Path(args[args.index('-O') + 1])
    if target.name == 'SHA256SUMS':
        digest = hashlib.sha256(b'package').hexdigest()
        if mode == 'bad-hash': digest = '0' * 64
        target.write_text(''.join(digest + '  ethernet-can-host_' + arch + '.deb\n'
                                 for arch in ('amd64', 'arm64')))
    else:
        target.write_bytes(b'package')
elif name == 'apt':
    assert sys.stdin.read() == '', 'APT must not consume the piped script'
    if mode == 'apt-fail': sys.exit(100)
elif name == 'mktemp':
    directory = subprocess.check_output(['/usr/bin/mktemp', *args], text=True).strip()
    with open(os.environ['INSTALL_DIR_LOG'], 'a') as log: log.write(directory + '\n')
    print(directory)
'''


class InstallerTests(unittest.TestCase):
    def run_installer(self, arch='arm64', mode='', piped=False, truncated=False):
        with tempfile.TemporaryDirectory(prefix='installer-test-') as directory:
            root = Path(directory)
            for name in ('dpkg', 'sudo', 'wget', 'apt', 'mktemp'):
                executable = root / name
                executable.write_text(MOCK)
                executable.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'],
                       INSTALL_LOG=str(root / 'calls'), INSTALL_DIR_LOG=str(root / 'dirs'),
                       INSTALL_ARCH=arch, INSTALL_MODE=mode)
            source = SCRIPT.read_text()
            if truncated:
                source = source[:source.index('    sha256sum --strict')]
            command = ['bash'] if piped or truncated else ['bash', str(SCRIPT)]
            result = subprocess.run(command, input=source if piped or truncated else '',
                                    text=True, capture_output=True, env=env)
            calls = (root / 'calls').read_text() if (root / 'calls').exists() else ''
            if (root / 'dirs').exists():
                for path in (root / 'dirs').read_text().splitlines():
                    self.assertFalse(Path(path).exists(), 'temporary downloads must be removed')
            return result, calls

    def test_architectures_and_pipe(self):
        for arch in ('amd64', 'arm64'):
            for piped in (False, True):
                with self.subTest(arch=arch, piped=piped):
                    result, calls = self.run_installer(arch=arch, piped=piped)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('apt update\n', calls)
                    self.assertIn(f'apt install -y ./ethernet-can-host_{arch}.deb\n', calls)

    def test_rejects_unsupported_architecture(self):
        result, calls = self.run_installer(arch='riscv64')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('wget ', calls)
        self.assertNotIn('apt ', calls)

    def test_download_and_checksum_fail_before_apt(self):
        for mode in ('download-fail', 'bad-hash'):
            with self.subTest(mode=mode):
                result, calls = self.run_installer(mode=mode, piped=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('apt ', calls)

    def test_apt_update_failure_stops_installation(self):
        result, calls = self.run_installer(mode='apt-fail')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('apt install', calls)

    def test_truncated_script_does_not_start_installation(self):
        result, calls = self.run_installer(truncated=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, '')


if __name__ == '__main__':
    unittest.main()
