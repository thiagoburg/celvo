import subprocess


def list_sources():
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def find_system_monitor():
    sources = list_sources()

    for line in sources.splitlines():
        if ".monitor" in line:
            return line.split()[1]

    return None
