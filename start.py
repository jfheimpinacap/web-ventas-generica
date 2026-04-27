"""Utility launcher for local monorepo development."""

from __future__ import annotations

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR
BACKEND_DIR = ROOT_DIR / 'backend'
FRONTEND_DIR = ROOT_DIR / 'frontend'
DEFAULT_FRONTEND_PORT = '5174'
DEFAULT_BACKEND_PORT = '8001'
DEFAULT_APP_OPEN_URL = f'http://localhost:{DEFAULT_FRONTEND_PORT}'


def run(command: list[str], cwd: Path | None = None) -> None:
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def run_or_exit(command: list[str], cwd: Path | None = None, error_message: str = '') -> None:
    try:
        run(command, cwd=cwd)
    except subprocess.CalledProcessError as exc:
        if error_message:
            print(error_message)
        raise SystemExit(exc.returncode) from exc


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


def ensure_backend_dependencies() -> None:
    print('Preparando backend...')
    print('Instalando dependencias Python...')
    run_or_exit(
        [python_cmd(), '-m', 'pip', 'install', '-r', 'requirements.txt'],
        cwd=BACKEND_DIR,
        error_message=(
            'Error instalando dependencias del backend. '
            'Revisa tu conexión/red, proxy o el archivo backend/requirements.txt.'
        ),
    )


def migrate() -> None:
    print('Aplicando migraciones...')
    run_or_exit(
        [python_cmd(), 'manage.py', 'migrate'],
        cwd=BACKEND_DIR,
        error_message='Error aplicando migraciones de Django.',
    )


def seed_catalog() -> None:
    print('Cargando catálogo demo...')
    run_or_exit(
        [python_cmd(), 'manage.py', 'seed_catalog'],
        cwd=BACKEND_DIR,
        error_message=(
            'Error ejecutando seed_catalog. '
            'Verifica que el comando exista y no tenga errores.'
        ),
    )


def seed_demo_user() -> None:
    print('Creando usuario demo...')
    run_or_exit(
        [python_cmd(), 'manage.py', 'seed_demo_user'],
        cwd=BACKEND_DIR,
        error_message=(
            'Error ejecutando seed_demo_user. '
            'Verifica que el comando exista y no tenga errores.'
        ),
    )


def backend_check() -> None:
    print('Verificando backend (manage.py check)...')
    run_or_exit(
        [python_cmd(), 'manage.py', 'check'],
        cwd=BACKEND_DIR,
        error_message='Error en validación de Django (manage.py check).',
    )


def ensure_frontend_dependencies() -> None:
    print('Preparando frontend...')
    print('Instalando dependencias npm...')
    npm_binary = ensure_node_and_npm()
    run_or_exit(
        [npm_binary, 'install'],
        cwd=FRONTEND_DIR,
        error_message=(
            'Error instalando dependencias del frontend con npm install. '
            'Revisa tu conexión/red, proxy o package.json.'
        ),
    )


def prepare() -> None:
    ensure_backend_dependencies()
    migrate()
    seed_catalog()
    seed_demo_user()
    backend_check()
    ensure_frontend_dependencies()


def setup() -> None:
    prepare()


def backend() -> None:
    run([python_cmd(), 'manage.py', 'runserver', f'127.0.0.1:{backend_port()}'], cwd=BACKEND_DIR)


def frontend() -> None:
    run([ensure_node_and_npm(), 'run', 'dev', '--', '--port', frontend_port()], cwd=FRONTEND_DIR)


def launch_windows_terminal(title: str, command: list[str]) -> None:
    quoted_command = subprocess.list2cmdline(command)
    subprocess.Popen(
        ['cmd', '/c', 'start', title, '/D', str(PROJECT_ROOT), 'cmd', '/k', quoted_command],
        cwd=PROJECT_ROOT,
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


def parse_simple_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def read_env_value(key: str) -> str | None:
    env_value = os.getenv(key)
    if env_value:
        return env_value

    dotenv_file = PROJECT_ROOT / '.env'
    if not dotenv_file.exists():
        return None

    for line in dotenv_file.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        parsed_key, value = stripped.split('=', 1)
        if parsed_key.strip() == key:
            parsed_value = parse_simple_dotenv_value(value)
            return parsed_value or None

    return None


def backend_port() -> str:
    return read_env_value('BACKEND_PORT') or DEFAULT_BACKEND_PORT


def frontend_port() -> str:
    return read_env_value('FRONTEND_PORT') or DEFAULT_FRONTEND_PORT


def app_open_url() -> str:
    return read_env_value('APP_OPEN_URL') or DEFAULT_APP_OPEN_URL


def open_app_browser() -> None:
    url = app_open_url()
    print(f'Abriendo navegador en {url} ...')
    webbrowser.open(url)


def dev() -> None:
    python_executable = python_cmd()
    backend_command = [python_executable, 'start.py', 'backend']
    frontend_command = [python_executable, 'start.py', 'frontend']

    print('Iniciando entorno de desarrollo...')
    ensure_node_and_npm()

    system = platform.system()
    if system == 'Windows':
        print('Abriendo terminal para backend...')
        launch_windows_terminal('Backend - web ventas', backend_command)
        print('Abriendo terminal para frontend...')
        launch_windows_terminal('Frontend - web ventas', frontend_command)
        open_app_browser()
        return

    if system == 'Darwin':
        print('Abriendo Terminal para backend...')
        backend_ok = launch_macos_terminal(backend_command)
        print('Abriendo Terminal para frontend...')
        frontend_ok = launch_macos_terminal(frontend_command)
        if backend_ok and frontend_ok:
            open_app_browser()
            return

    if system == 'Linux':
        print('Abriendo terminal para backend...')
        backend_ok = launch_linux_terminal('Backend', backend_command)
        print('Abriendo terminal para frontend...')
        frontend_ok = launch_linux_terminal('Frontend', frontend_command)
        if backend_ok and frontend_ok:
            open_app_browser()
            return

    print('No se pudo abrir terminales automáticamente en este sistema.')
    print('Ejecuta manualmente en terminales separadas:')
    print(f'  1) {python_executable} start.py backend')
    print(f'  2) {python_executable} start.py frontend')


def start() -> None:
    prepare()
    dev()


def main() -> None:
    parser = argparse.ArgumentParser(description='Monorepo starter commands')
    commands = {
        'setup': setup,
        'prepare': prepare,
        'backend': backend,
        'frontend': frontend,
        'dev': dev,
        'start': start,
    }
    parser.add_argument(
        'command',
        nargs='?',
        default='start',
        choices=commands.keys(),
        help='Comando a ejecutar (default: start).',
    )
    args = parser.parse_args()
    commands[args.command]()


if __name__ == '__main__':
    main()
