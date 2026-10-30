#!/usr/bin/env python3
"""Trimlight Edge (V2 OAuth) API client and CLI.

Standard library only (works on Python 3.7+).
Credentials come from env vars TRIMLIGHT_CLIENT_ID / TRIMLIGHT_CLIENT_SECRET,
or from a .env file next to this script.
"""
import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "https://trimlight.ledhue.com/trimlight"
API = "/v1/oauth/resources"


class TrimlightError(Exception):
    pass


def load_env(path):
    """Load KEY=VALUE lines from a .env file into os.environ (without overriding)."""
    if not os.path.exists(path):
        return
    # utf-8-sig: Windows Notepad may save a byte-order mark at the start of the file.
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Backups need a US zone abbreviation (API 1.4.0, section 28). macOS and Linux report one
# ("EDT"), but Windows reports "Eastern Daylight Time", so derive it from the UTC offset instead.
US_ZONES = {-10: "H", -9: "AK", -8: "P", -7: "M", -6: "C", -5: "E"}


def backup_time():
    """Current local time as "YYYY-MM-DD HH:MM:SS EDT"; raises TrimlightError outside US time zones."""
    now = time.localtime()
    standard_offset = -time.timezone // 3600
    if standard_offset not in US_ZONES:
        raise TrimlightError("Trimlight backups need a US time zone; this computer is at UTC{:+d}".format(standard_offset))
    zone = US_ZONES[standard_offset] + ("DT" if now.tm_isdst > 0 else "ST")
    return time.strftime("%Y-%m-%d %H:%M:%S ", now) + zone


def make_token(client_id, client_secret, timestamp_ms):
    """accessToken = base64(HMAC-SHA256("Trimlight|<clientId>|<timestamp>", clientSecret))."""
    message = "Trimlight|{}|{}".format(client_id, timestamp_ms).encode()
    digest = hmac.new(client_secret.encode(), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def ssl_context():
    """System certificates, plus TRIMLIGHT_CA_BUNDLE if set (e.g. a company proxy's certificate).

    Some Pythons ship with no certificates (Apple's Python 3.7, python.org's macOS installer before
    "Install Certificates" is run); for those, fall back to macOS's /etc/ssl/cert.pem.
    """
    ctx = ssl.create_default_context()
    extra = os.environ.get("TRIMLIGHT_CA_BUNDLE")
    if extra:
        ctx.load_verify_locations(extra)
    elif not ctx.cert_store_stats().get("x509_ca") and os.path.exists("/etc/ssl/cert.pem"):
        ctx.load_verify_locations("/etc/ssl/cert.pem")
    return ctx


def current_date():
    """Device-format date: year is relative to 2000, weekday is SUNDAY=1 .. SATURDAY=7."""
    now = datetime.datetime.now()
    return {
        "year": now.year - 2000,
        "month": now.month,
        "day": now.day,
        "weekday": (now.isoweekday() % 7) + 1,
        "hours": now.hour,
        "minutes": now.minute,
        "seconds": now.second,
    }


class TrimlightClient:
    def __init__(self, client_id, client_secret, base_url=BASE_URL, timeout=20, verbose=False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verbose = verbose
        self.ssl_context = ssl_context()

    def _headers(self):
        ts = int(time.time() * 1000)
        return {
            "authorization": make_token(self.client_id, self.client_secret, ts),
            "S-ClientId": self.client_id,
            "S-Timestamp": str(ts),
            "Content-Type": "application/json",
        }

    def request(self, method, path, body=None):
        url = self.base_url + API + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        if self.verbose:
            print(">>", method, url, json.dumps(body) if body is not None else "", file=sys.stderr)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            raise TrimlightError("HTTP {} {}: {}".format(e.code, e.reason, e.read().decode(errors="replace")))
        except urllib.error.URLError as e:
            raise TrimlightError("Network error: {}".format(e.reason))
        if self.verbose:
            print("<<", raw, file=sys.stderr)
        try:
            result = json.loads(raw)
        except ValueError:
            raise TrimlightError("Non-JSON response: {}".format(raw[:500]))
        if "error" in result and "code" not in result:  # OAuth-style rejection, e.g. unknown Client ID/Secret
            raise TrimlightError("Trimlight rejected the credentials ({})".format(result.get("error_description") or result["error"]))
        if result.get("code") != 0:
            raise TrimlightError("API error {}: {}".format(result.get("code"), result.get("desc")))
        return result

    def _device(self, path, device_id, payload, method="POST"):
        return self.request(method, path, {"deviceId": device_id, "payload": payload})

    # --- Devices ---
    def list_devices(self, page=0):
        # Spec documents GET with a JSON body; page 0/null returns all devices.
        return self.request("GET", "/devices", {"page": page})

    def get_device(self, device_id):
        return self.request("POST", "/device/get", {"deviceId": device_id, "currentDate": current_date()})

    def notify_update_shadow(self, device_id):
        return self.request("GET", "/device/notify-update-shadow",
                            {"deviceId": device_id, "currentDate": current_date()})

    def update_device(self, device_id, **payload):
        """switchState (0 off, 1 manual, 2 timer), name, colorOrder, ic, or ports."""
        return self._device("/device/update", device_id, payload)

    # --- Effects ---
    def preview_builtin(self, device_id, mode, speed=100, brightness=100, pixel_len=30, reverse=False):
        return self._device("/device/effect/preview", device_id, {
            "category": 0, "mode": mode, "speed": speed, "brightness": brightness,
            "pixelLen": pixel_len, "reverse": reverse,
        })

    def preview_custom(self, device_id, mode, pixels, speed=100, brightness=100):
        return self._device("/device/effect/preview", device_id, {
            "category": 1, "mode": mode, "speed": speed, "brightness": brightness, "pixels": pixels,
        })

    def save_effect(self, device_id, effect):
        """effect dict per spec; id -1/None creates a new effect."""
        return self._device("/device/effect/save", device_id, effect)

    def view_effect(self, device_id, effect_id):
        return self._device("/device/effect/view", device_id, {"id": effect_id})

    def delete_effect(self, device_id, effect_id):
        return self._device("/device/effect/delete", device_id, {"id": effect_id})

    def set_overlays(self, device_id, overlays):
        """Replace ALL overlays: list of {"overlayType": 0 lightning | 1 snow, "targetEffect": id} (API 1.4.0)."""
        return self._device("/device/effect/overlay", device_id, {"overlayEffects": overlays})

    def backup(self, device_id, backup_time):
        """backup_time like "2024-09-26 16:20:26 PDT" (API 1.4.0)."""
        return self._device("/device/data/backup", device_id, {"backupTime": backup_time})

    def get_backup(self, device_id):
        return self.request("POST", "/device/data/backup/get", {"deviceId": device_id})

    def restore_backup(self, device_id, backup_key):
        """Overwrite the controller's patterns and schedules with a cloud backup (API 1.4.0)."""
        return self._device("/device/data/backup/restore", device_id, {"backupKey": backup_key})

    def sync_datetime(self, device_id):
        """Set the controller clock to this computer's local time (API 1.4.0)."""
        return self.request("POST", "/device/datetime/sync", {"deviceId": device_id, "currentDate": current_date()})

    def save_combined_effect(self, device_id, effect_ids, interval):
        return self._device("/device/combined-effect/save", device_id,
                            {"effectIds": effect_ids, "interval": interval})

    # --- Schedules ---
    def save_daily(self, device_id, schedule):
        return self._device("/device/daily/save", device_id, schedule)

    def save_calendar(self, device_id, schedule):
        return self._device("/device/calendar/save", device_id, schedule)

    def delete_calendar(self, device_id, schedule_id):
        return self._device("/device/calendar/delete", device_id, {"id": schedule_id})

    # --- Groups (spec documents these as GET with JSON bodies) ---
    def list_groups(self, page=0):
        return self.request("GET", "/groups", {"page": page})

    def add_group(self, name, master_device, devices):
        return self.request("GET", "/group/add", {"name": name, "masterDevice": master_device, "devices": devices})

    def update_group(self, group_id, master_device, devices):
        return self.request("GET", "/group/update",
                            {"groupId": group_id, "masterDevice": master_device, "devices": devices})

    def rename_group(self, group_id, name):
        return self.request("GET", "/group/rename", {"groupId": group_id, "name": name})

    def delete_group(self, group_id):
        return self.request("GET", "/group/delete", {"groupId": group_id})

    def sync_group(self, group_id):
        return self.request("GET", "/group/sync", {"groupId": group_id})


def parse_color(value):
    """Accept '#FF0000', 'FF0000', '0xFF0000' or a decimal int string."""
    v = value.strip().lower()
    if v.startswith("#"):
        return int(v[1:], 16)
    if v.startswith("0x"):
        return int(v, 16)
    if len(v) == 6 and all(c in "0123456789abcdef" for c in v):
        return int(v, 16)
    return int(v)


def build_parser():
    p = argparse.ArgumentParser(description="Trimlight Edge API CLI")
    p.add_argument("-v", "--verbose", action="store_true", help="print raw requests and responses")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("token", help="print a fresh auth header set (offline, no request)")

    s = sub.add_parser("devices", help="list devices")
    s.add_argument("--page", type=int, default=0)

    s = sub.add_parser("device", help="get device details")
    s.add_argument("device_id")

    s = sub.add_parser("refresh", help="ask device to report latest shadow data")
    s.add_argument("device_id")

    for name, state, desc in (("off", 0, "turn lights off"), ("on", 1, "manual mode (on)"),
                              ("timer", 2, "timer/schedule mode")):
        s = sub.add_parser(name, help=desc)
        s.add_argument("device_id")
        s.set_defaults(switch_state=state)

    s = sub.add_parser("rename", help="rename a device")
    s.add_argument("device_id")
    s.add_argument("name")

    s = sub.add_parser("preview", help="preview a built-in effect (mode 0-179)")
    s.add_argument("device_id")
    s.add_argument("mode", type=int)
    s.add_argument("--speed", type=int, default=100)
    s.add_argument("--brightness", type=int, default=100)
    s.add_argument("--pixel-len", type=int, default=30)
    s.add_argument("--reverse", action="store_true")

    s = sub.add_parser("solid", help="preview a static solid color (custom mode 0)")
    s.add_argument("device_id")
    s.add_argument("color", help="e.g. #FF0000")
    s.add_argument("--brightness", type=int, default=100)

    s = sub.add_parser("effect", help="view (run) a saved effect by id")
    s.add_argument("device_id")
    s.add_argument("effect_id", type=int)

    s = sub.add_parser("backup", help="back up device data to the Trimlight cloud (API 1.4.0)")
    s.add_argument("device_id")

    s = sub.add_parser("backup-info", help="show the latest cloud backup")
    s.add_argument("device_id")

    s = sub.add_parser("groups", help="list groups")
    s.add_argument("--page", type=int, default=0)

    s = sub.add_parser("raw", help="send any request: raw METHOD PATH [JSON]")
    s.add_argument("method")
    s.add_argument("path", help="path after /v1/oauth/resources, e.g. /devices")
    s.add_argument("json", nargs="?")
    return p


def main(argv=None):
    load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    args = build_parser().parse_args(argv)
    if not args.cmd:
        build_parser().print_help()
        return 1

    client_id = os.environ.get("TRIMLIGHT_CLIENT_ID")
    client_secret = os.environ.get("TRIMLIGHT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Set TRIMLIGHT_CLIENT_ID and TRIMLIGHT_CLIENT_SECRET (env or .env).", file=sys.stderr)
        return 2

    c = TrimlightClient(client_id, client_secret, verbose=args.verbose)
    try:
        if args.cmd == "token":
            result = c._headers()
        elif args.cmd == "devices":
            result = c.list_devices(args.page)
        elif args.cmd == "device":
            result = c.get_device(args.device_id)
        elif args.cmd == "refresh":
            result = c.notify_update_shadow(args.device_id)
        elif args.cmd in ("off", "on", "timer"):
            result = c.update_device(args.device_id, switchState=args.switch_state)
        elif args.cmd == "rename":
            result = c.update_device(args.device_id, name=args.name)
        elif args.cmd == "preview":
            result = c.preview_builtin(args.device_id, args.mode, args.speed, args.brightness,
                                       args.pixel_len, args.reverse)
        elif args.cmd == "solid":
            pixels = [{"index": 0, "count": 1, "color": parse_color(args.color), "disable": False}]
            result = c.preview_custom(args.device_id, 0, pixels, brightness=args.brightness)
        elif args.cmd == "effect":
            result = c.view_effect(args.device_id, args.effect_id)
        elif args.cmd == "backup":
            result = c.backup(args.device_id, backup_time())
        elif args.cmd == "backup-info":
            result = c.get_backup(args.device_id)
        elif args.cmd == "groups":
            result = c.list_groups(args.page)
        elif args.cmd == "raw":
            body = json.loads(args.json) if args.json else None
            result = c.request(args.method.upper(), args.path, body)
    except TrimlightError as e:
        print("Error:", e, file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
