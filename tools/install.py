#!/usr/bin/env python3
"""Simple installer that runs update/upgrade steps."""

import subprocess


def run_update_upgrade() -> None:
    commands = [
        ["apt-get", "update"],
        ["apt-get", "-y", "upgrade"],
    ]
    for command in commands:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    run_update_upgrade()
