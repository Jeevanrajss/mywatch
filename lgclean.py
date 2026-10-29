#!/usr/bin/env python3
"""Connect to an LG webOS TV (2018-2021, webOS 4-6) over Wi-Fi and remove apps.

  pip install aiowebostv
  lgclean.py connect <tv-ip>        # pair; accept the prompt on the TV
  lgclean.py list <tv-ip>           # installed apps (id, title)
  lgclean.py remove <tv-ip> <id>... # try to uninstall apps by id

On the TV: Settings -> General -> Network -> LG Connect Apps (or "Mobile TV On")
must be enabled. LG's built-in apps usually cannot be removed remotely; remove
those on the TV itself (Home -> edit mode). Cache/storage cleanup is only
available on the TV: Settings -> General -> Storage.
"""
import argparse
import asyncio
import pathlib
import sys

from aiowebostv import WebOsClient

KEY_FILE = pathlib.Path.home() / ".lgclean_keys"


def load_key(host):
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            h, _, k = line.partition(" ")
            if h == host:
                return k
    return None


def save_key(host, key):
    lines = []
    if KEY_FILE.exists():
        lines = [l for l in KEY_FILE.read_text().splitlines() if not l.startswith(host + " ")]
    KEY_FILE.write_text("\n".join(lines + [f"{host} {key}"]) + "\n")
    KEY_FILE.chmod(0o600)


async def connect(host):
    client = WebOsClient(host, client_key=load_key(host))
    try:
        await client.connect()
    except Exception as e:
        sys.exit(f"Could not connect to {host}: {e!r}\nCheck the IP, that the TV is on, and that "
                 "LG Connect Apps is enabled. Accept the pairing prompt on the TV.")
    if client.client_key:
        save_key(host, client.client_key)
    return client


async def cmd_connect(a):
    client = await connect(a.host)
    print(f"Connected to {a.host}.")
    await client.disconnect()


async def cmd_list(a):
    client = await connect(a.host)
    for app in sorted(await client.get_apps_all(), key=lambda x: x["title"].lower()):
        print(f"{app['id']:45} {app['title']}")
    await client.disconnect()


async def cmd_remove(a):
    client = await connect(a.host)
    titles = {x["id"]: x["title"] for x in await client.get_apps_all()}
    for app_id in a.ids:
        name = titles.get(app_id)
        if not name:
            print(f"skip {app_id}: not installed")
            continue
        if input(f"Remove {name} ({app_id})? [y/N] ").strip().lower() != "y":
            continue
        try:
            await client.request("com.webos.appInstallService/remove", {"id": app_id})
            print(f"removed {name}")
        except Exception as e:
            print(f"could not remove {name}: {e!r} (remove it on the TV instead)")
    await client.disconnect()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("connect", cmd_connect), ("list", cmd_list)):
        s = sub.add_parser(name); s.add_argument("host"); s.set_defaults(fn=fn)
    s = sub.add_parser("remove"); s.add_argument("host"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=cmd_remove)
    a = ap.parse_args()
    asyncio.run(a.fn(a))


if __name__ == "__main__":
    main()
