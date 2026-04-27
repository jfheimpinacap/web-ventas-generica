"""Utility launcher for local monorepo development."""

from __future__ import annotations

import argparse
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / 'backend'
FRONTEND_DIR = ROOT_DIR / 'frontend'


def run(command: list[str], cwd: Path | None = None) -> None:
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def python_cmd() -> str:
    return sys.executable


def resolve_binary(*candidates: str) -> str | None:
    """Return the first binary available in PATH from the given candidates."""
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def node_cmd() -> str | None:
    if platform.system() == 'Windows':
        return resolve_binary('node.exe', 'node')
    return resolve_binary('node')


def npm_cmd() -> str | None:
    if platform.system() == 'Windows':
        return resolve_binary('npm.cmd', 'npm.exe', 'npm')
    return resolve_binary('npm')


def ensure_node_and_npm() -> str:
    node_binary = node_cmd()
    npm_binary = npm_cmd()

    if not node_binary or not npm_binary:
        raise SystemExit(
            'Node.js y npm no se encontraron en el PATH. '
            'Instala Node.js desde https://nodejs.org/ o agrega sus binarios al PATH de Windows.'
        )

    return npm_binary


def setup() -> None:
    run([python_cmd(), '-m', 'pip', 'install', '-r', 'requirements.txt'], cwd=BACKEND_DIR)
    run([python_cmd(), 'manage.py', 'migrate'], cwd=BACKEND_DIR)
    run([ensure_node_and_npm(), 'install'], cwd=FRONTEND_DIR)


def backend() -> None:
    run([python_cmd(), 'manage.py', 'runserver'], cwd=BACKEND_DIR)


def frontend() -> None:
    run([ensure_node_and_npm(), 'run', 'dev'], cwd=FRONTEND_DIR)


def launch_windows_terminal(title: str, command: list[str]) -> None:
    quoted_command = subprocess.list2cmdline(command)
    subprocess.Popen(
        ['cmd', '/c', 'start', title, 'cmd', '/k', quoted_command],
        cwd=ROOT_DIR,
    )


def launch_macos_terminal(command: list[str]) -> bool:
    if not shutil.which('osascript'):
        return False

    quoted_command = ' '.join(shlex.quote(part) for part in command)
    command_with_cd = f'cd {shlex.quote(str(ROOT_DIR))} && {quoted_command}'
    applescript = f'tell application "Terminal" to do script "{command_with_cd}"'
    subprocess.Popen(['osascript', '-e', applescript])
    return True


def launch_linux_terminal(title: str, command: list[str]) -> bool:
    quoted_command = ' '.join(shlex.quote(part) for part in command)
    terminals: list[tuple[str, list[str]]] = [
        ('x-terminal-emulator', ['-T', title, '-e', quoted_command]),
        ('gnome-terminal', ['--title', title, '--', 'bash', '-lc', quoted_command]),
        ('konsole', ['--new-tab', '-p', f'tabtitle={title}', '-e', 'bash', '-lc', quoted_command]),
        ('xterm', ['-T', title, '-e', quoted_command]),
    ]

    for binary, args in terminals:
        resolved = shutil.which(binary)
        if resolved:
            subprocess.Popen([resolved, *args], cwd=ROOT_DIR)
            return True

    return False


def dev() -> None:
    python_executable = python_cmd()
    backend_command = [python_executable, 'start.py', 'backend']
    frontend_command = [python_executable, 'start.py', 'frontend']

    print('Iniciando entorno de desarrollo...')

    system = platform.system()
    if system == 'Windows':
        print('Abriendo terminal para backend...')
        launch_windows_terminal('Backend', backend_command)
        print('Abriendo terminal para frontend...')
        launch_windows_terminal('Frontend', frontend_command)
        return

    if system == 'Darwin':
        print('Abriendo Terminal para backend...')
        backend_ok = launch_macos_terminal(backend_command)
        print('Abriendo Terminal para frontend...')
        frontend_ok = launch_macos_terminal(frontend_command)
        if backend_ok and frontend_ok:
            return

    if system == 'Linux':
        print('Abriendo terminal para backend...')
        backend_ok = launch_linux_terminal('Backend', backend_command)
        print('Abriendo terminal para frontend...')
        frontend_ok = launch_linux_terminal('Frontend', frontend_command)
        if backend_ok and frontend_ok:
            return

    print('No se pudo abrir terminales automáticamente en este sistema.')
    print('Ejecuta manualmente en terminales separadas:')
    print(f'  1) {python_executable} start.py backend')
    print(f'  2) {python_executable} start.py frontend')


def main() -> None:
    parser = argparse.ArgumentParser(description='Monorepo starter commands')
    commands = {
        'setup': setup,
        'backend': backend,
        'frontend': frontend,
        'dev': dev,
    }
    parser.add_argument(
        'command',
        nargs='?',
        default='dev',
        choices=commands.keys(),
        help='Comando a ejecutar (default: dev).',
    )
    args = parser.parse_args()
    commands[args.command]()


if __name__ == '__main__':
    main()
