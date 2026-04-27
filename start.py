"""Utility launcher for local monorepo development."""

from __future__ import annotations

import argparse
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


def setup() -> None:
    run([python_cmd(), '-m', 'pip', 'install', '-r', 'requirements.txt'], cwd=BACKEND_DIR)
    run([python_cmd(), 'manage.py', 'migrate'], cwd=BACKEND_DIR)
    run(['npm', 'install'], cwd=FRONTEND_DIR)


def backend() -> None:
    run([python_cmd(), 'manage.py', 'runserver'], cwd=BACKEND_DIR)


def frontend() -> None:
    run(['npm', 'run', 'dev'], cwd=FRONTEND_DIR)


def dev() -> None:
    print('Inicia backend y frontend en terminales separadas:')
    print('  1) py start.py backend')
    print('  2) py start.py frontend')


def main() -> None:
    parser = argparse.ArgumentParser(description='Monorepo starter commands')
    parser.add_argument('command', choices=['setup', 'backend', 'frontend', 'dev'])
    args = parser.parse_args()

    commands = {
        'setup': setup,
        'backend': backend,
        'frontend': frontend,
        'dev': dev,
    }
    commands[args.command]()


if __name__ == '__main__':
    main()
