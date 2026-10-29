#!/usr/bin/env python3
"""Clean up an Android TV / Google TV over ADB (Wi-Fi).

Requires `adb` on PATH and, on the TV: Developer options -> USB/Wireless debugging on.

  tvclean.py connect 192.168.1.50
  tvclean.py list [--all]
  tvclean.py bloat                 # pick from a list of known bloatware that is installed
  tvclean.py remove com.foo.bar    # uninstall/disable specific packages
  tvclean.py cache                 # trim caches / free storage
  tvclean.py home                  # reset home-screen recommendations

Everything asks for confirmation; pass --dry-run to only print the adb commands.
Uninstalls use `--user 0`, so system apps are removed for the current user only
and can be restored with `adb shell cmd package install-existing <pkg>`.
"""
import argparse
import subprocess
import sys

# Packages commonly safe to remove on Android TV / Google TV. Only those
# actually installed are offered. Review before confirming.
BLOAT = [
    "com.google.android.youtube.tvmusic",
    "com.google.android.videos",
    "com.google.android.play.games",
    "com.google.android.apps.mediashell.leanback",
    "com.netflix.ninja",
    "com.amazon.amazonvideo.livingroom",
    "com.disney.disneyplus",
    "com.hbo.hbonow",
    "com.spotify.tv.android",
    "com.google.android.tvrecommendations",
]

HOME_PKGS = [
    "com.google.android.tvrecommendations",
    "com.google.android.leanbacklauncher.recommendations",
]


def adb(*args, dry=False, check=True):
    cmd = ["adb", *args]
    if dry:
        print("[dry-run]", " ".join(cmd))
        return ""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.exit(f"adb failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


def packages(third_party_only=True):
    flag = "-3" if third_party_only else ""
    out = adb("shell", "pm", "list", "packages", *([flag] if flag else []))
    return sorted(line.split(":", 1)[1] for line in out.splitlines() if ":" in line)


def confirm(prompt, dry):
    if dry:
        return True
    return input(f"{prompt} [y/N] ").strip().lower() == "y"


def remove(pkg, dry):
    out = adb("shell", "pm", "uninstall", "--user", "0", pkg, dry=dry, check=False)
    if dry or "Success" in out:
        print(f"removed {pkg}")
        return
    # Some system apps refuse uninstall; fall back to disabling.
    adb("shell", "pm", "disable-user", "--user", "0", pkg, dry=dry, check=False)
    print(f"disabled {pkg}")


def pick(items, dry):
    for i, p in enumerate(items, 1):
        print(f"{i:3}. {p}")
    sel = input("Numbers to remove (e.g. 1 3 5, 'all', blank to cancel): ").strip()
    if not sel:
        return []
    if sel == "all":
        return items
    return [items[int(n) - 1] for n in sel.split() if n.isdigit() and 0 < int(n) <= len(items)]


def cmd_connect(a):
    host = a.host if ":" in a.host else f"{a.host}:5555"
    print(adb("connect", host))
    print("Accept the debugging prompt on the TV if it appears.")


def cmd_list(a):
    print("\n".join(packages(not a.all)))


def cmd_bloat(a):
    installed = set(packages(False))
    found = [p for p in BLOAT if p in installed]
    if not found:
        return print("No known bloatware found.")
    for p in pick(found, a.dry_run):
        if confirm(f"Remove {p}?", a.dry_run):
            remove(p, a.dry_run)


def cmd_remove(a):
    for p in a.packages:
        if confirm(f"Remove {p}?", a.dry_run):
            remove(p, a.dry_run)


def cmd_cache(a):
    if not confirm("Trim caches on the TV?", a.dry_run):
        return
    adb("shell", "pm", "trim-caches", "999G", dry=a.dry_run, check=False)
    print(adb("shell", "df", "/data", dry=a.dry_run))


def cmd_home(a):
    if not confirm("Reset home-screen recommendation data (apps stay installed)?", a.dry_run):
        return
    installed = set(packages(False))
    for p in HOME_PKGS:
        if p in installed:
            adb("shell", "pm", "clear", p, dry=a.dry_run, check=False)
            print(f"cleared {p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print adb commands without running")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("connect"); s.add_argument("host"); s.set_defaults(fn=cmd_connect)
    s = sub.add_parser("list"); s.add_argument("--all", action="store_true"); s.set_defaults(fn=cmd_list)
    sub.add_parser("bloat").set_defaults(fn=cmd_bloat)
    s = sub.add_parser("remove"); s.add_argument("packages", nargs="+"); s.set_defaults(fn=cmd_remove)
    sub.add_parser("cache").set_defaults(fn=cmd_cache)
    sub.add_parser("home").set_defaults(fn=cmd_home)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
