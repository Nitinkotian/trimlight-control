#!/usr/bin/env python3
"""Local web app for the Trimlight Edge API.

Run:  python3 webapp.py [--port 8765]
Then open http://127.0.0.1:8765

The browser only talks to this server; the client secret never leaves it.
Standard library only (Python 3.7+).
"""
import sys

if sys.version_info < (3, 7):
    sys.exit("This app needs Python 3.7 or newer; you have {}. See README.md > Install Python.".format(sys.version.split()[0]))

import argparse
import json
import os
import re
import socket
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from trimlight import TrimlightClient, TrimlightError, backup_time, current_date, load_env

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "static", "index.html")
ENV_FILE = os.path.join(HERE, ".env")
# Festival groups are this app's own labels; the controller has no folders, so they live on this computer.
FESTIVALS_FILE = os.path.join(HERE, "festivals.json")
DEFAULT_FESTIVALS = [
    ("newyear", "New Year", "🎆", "#f59e0b"), ("valentine", "Valentine's Day", "❤️", "#e11d48"),
    ("stpatrick", "St. Patrick's Day", "☘️", "#16a34a"), ("easter", "Easter", "🐣", "#eab308"),
    ("mothers", "Mother's Day", "💐", "#db2777"), ("memorial", "Memorial Day", "🎖️", "#2563eb"),
    ("independence", "Independence Day", "🎇", "#1d4ed8"), ("canada", "Canada Day", "🍁", "#dc2626"),
    ("durga", "Durga Puja", "🌼", "#ea580c"), ("diwali", "Diwali", "🪔", "#f97316"),
    ("halloween", "Halloween", "🎃", "#c2410c"), ("thanksgiving", "Thanksgiving", "🦃", "#b45309"),
    ("christmas", "Christmas", "🎄", "#15803d"), ("birthday", "Birthdays", "🎂", "#9333ea"),
    ("everyday", "Everyday", "✨", "#64748b"),
]
FESTIVAL_LOCK = threading.Lock()
# Trimlight's own page where account holders get a Client ID and Client Secret.
APPLY_URL = "https://trimlight.ledhue.com/trimlight/v1/api-credentials/apply"
NO_CLIENT_ROUTES = {"catalog", "setup_status", "setup", "disconnect", "save_festival", "delete_festival"}
CREDENTIAL_KEYS = ("TRIMLIGHT_CLIENT_ID", "TRIMLIGHT_CLIENT_SECRET")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MONTH_DAY = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")  # work before credentials are set
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

COLORS = ["Red", "Green", "Blue", "Yellow", "Cyan", "Purple", "White"]
PAIRS = [(a, b) for i, a in enumerate(COLORS) for b in COLORS[i + 1:]]  # 21 pairs, spec order


def builtin_effects():
    """Built-in effect names, index == mode (0-179), per the spec appendix [4]."""
    n = ["Rainbow Gradual Chase", "Rainbow Comet", "Rainbow Segment", "Rainbow Wave", "Rainbow Meteor",
         "Rainbow Gradual", "Rainbow Jump", "Rainbow Stars", "Rainbow Fade In Out", "Rainbow Spin"]
    n += ["{} Stacking".format(c) for c in COLORS]
    n += ["Full Color Stack"] + ["{} to {} Stack".format(a, b) for a, b in zip(COLORS, COLORS[1:])]
    for kind in ("Comet", "Meteor", "Wave"):
        n += ["{} {}".format(c, kind) for c in COLORS]
    n += ["{} {} Wave".format(a, b) for a, b in PAIRS]
    n += ["{} Dot Pulse".format(c) for c in COLORS]
    n += ["{} {} Blank Pulse".format(a, b) for a, b in zip(COLORS[:-1], COLORS[1:])]
    n += ["Red with Purple Pulse", "Green with Cyan Pulse", "Blue with Yellow Pulse",
          "Yellow with Blue Pulse", "Cyan with Green Pulse", "Purple with Purple Pulse"]
    for kind in ("Comet Spin", "Dot Spin", "Segment Spin"):
        n += ["{} {}".format(c, kind) for c in COLORS]
    n += ["{} {} Gradual Snake".format(a, b) for a, b in PAIRS]
    n += ["{} White Blank Snake".format(c) for c in COLORS[:-1]]
    n += ["Green Yellow White Snake", "Red Green White Snake", "Red Yellow Snake",
          "Red White Snake", "Green White Snake"]
    n += ["{} Stars".format(c) for c in COLORS]
    n += ["{} Background Stars".format(c) for c in COLORS[:-1]]
    n += ["{} White Background Stars".format(c) for c in COLORS]
    n += ["{} Breath".format(c) for c in COLORS]
    n += ["Red Yellow Fire", "Red Purple Fire", "Green Yellow Fire", "Green Cyan Fire",
          "Blue Purple Fire", "Blue Cyan Fire"]
    n += ["{} Strobe".format(c) for c in COLORS] + ["Red Blue White Strobe", "Full Color Strobe"]
    assert len(n) == 180, len(n)
    return n


CUSTOM_MODES = ["Static", "Chase Forward", "Chase Backward", "Chase Middle to Out", "Chase Out to Middle",
                "Stars", "Breath", "Comet Forward", "Comet Backward", "Comet Middle to Out",
                "Comet Out to Middle", "Wave Forward", "Wave Backward", "Wave Middle to Out",
                "Wave Out to Middle", "Strobe", "Solid Fade"]

# overlayType per API 1.4.0 (section 4.10).
OVERLAYS = {0: "Lightning", 1: "Snow"}
REPETITIONS = ["Today only", "Every day", "Weekdays", "Weekends"]

# Appendix [2] and [3].
COLOR_ORDERS = ["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"]
ICS = ["UCS1903", "DMX512"]

CATALOG = {"builtin": builtin_effects(), "custom": CUSTOM_MODES, "overlays": OVERLAYS,
           "repetitions": REPETITIONS, "colorOrders": COLOR_ORDERS, "ics": ICS}

DEVICE_ID = r"(?P<id>[A-Za-z0-9]+)"
ROUTES = [
    ("GET", r"/api/catalog$", "catalog"),
    ("GET", r"/api/setup$", "setup_status"),
    ("POST", r"/api/setup$", "setup"),
    ("POST", r"/api/setup/test$", "setup_test"),
    ("POST", r"/api/setup/disconnect$", "disconnect"),
    ("GET", r"/api/devices$", "devices"),
    ("GET", r"/api/device/" + DEVICE_ID + r"$", "device"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/switch$", "switch"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/preview$", "preview"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/effect$", "effect"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/effect/save$", "save_effect"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/effect/overlay$", "overlay"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/effect/rename$", "rename_effect"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/effect/delete$", "delete_effect"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/combined$", "combined"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/daily$", "daily"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/calendar$", "calendar"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/calendar/delete$", "delete_calendar"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/refresh$", "refresh"),
    ("GET", r"/api/device/" + DEVICE_ID + r"/festivals$", "festivals"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/festivals/assign$", "assign_festival"),
    ("POST", r"/api/festivals$", "save_festival"),
    ("POST", r"/api/festivals/delete$", "delete_festival"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/settings$", "settings"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/datetime$", "datetime"),
    ("GET", r"/api/device/" + DEVICE_ID + r"/backup$", "backup_info"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/backup$", "backup"),
    ("POST", r"/api/device/" + DEVICE_ID + r"/restore$", "restore"),
    ("GET", r"/api/groups$", "groups"),
    ("POST", r"/api/groups$", "add_group"),
    ("POST", r"/api/groups/update$", "update_group"),
    ("POST", r"/api/groups/rename$", "rename_group"),
    ("POST", r"/api/groups/delete$", "delete_group"),
    ("POST", r"/api/groups/sync$", "sync_group"),
]

COMBINED_EFFECT_ID = 200  # schedules use this id to mean "the combined (rotating) effect"
MAX_EFFECTS = 60
# The spec says custom modes 0-16 and pixel counts 0-60, but the Trimlight app saves
# modes up to 22 and counts up to 90, so allow wider ranges and let the device decide.
MAX_CUSTOM_MODE = 31
MAX_PIXEL_COUNT = 255


def custom_pixels(pixels):
    out = [{"index": i,
            "count": clamp(p.get("count", 1), 1, MAX_PIXEL_COUNT),
            "color": clamp(p["color"], 0, 0xFFFFFF),
            "disable": False}
           for i, p in enumerate(pixels[:30])]
    if not out:
        raise ValueError("at least one color is required")
    return out
EFFECT_FIELDS = ("id", "name", "category", "mode", "speed", "brightness", "pixelLen", "reverse", "pixels")


def schedule_time(t):
    return {"hours": clamp(t["hours"], 0, 23), "minutes": clamp(t["minutes"], 0, 59)}


def schedule_date(d):
    return {"month": clamp(d["month"], 1, 12), "day": clamp(d["day"], 1, 31)}


def clamp(value, lo, hi):
    return max(lo, min(hi, int(value)))


class UserError(ValueError):
    """A problem to show the user as-is (no "bad request:" prefix)."""


class Handler(BaseHTTPRequestHandler):
    client = None  # set in main()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, fmt % args))

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        # Blocks DNS-rebinding: only answer requests addressed to localhost.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ALLOWED_HOSTS

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden host"})
        path = self.path.split("?", 1)[0]
        if method == "GET" and path in ("/", "/index.html"):
            with open(INDEX, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        for m, pattern, name in ROUTES:
            match = re.match(pattern, path)
            if m == method and match:
                break
        else:
            return self._send(404, {"error": "not found"})

        body = {}
        if method == "POST":
            # A custom header can't be sent cross-site without a CORS preflight, which we never grant.
            if self.headers.get("X-Trimlight-App") != "1":
                return self._send(403, {"error": "missing app header"})
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(400, {"error": "invalid JSON"})
        if self.client is None and name not in NO_CLIENT_ROUTES:
            return self._send(503, {"error": "Add your Trimlight API credentials on the Home page first.", "setup": True})
        try:
            result = getattr(self, "api_" + name)(match.groupdict().get("id"), body)
        except TrimlightError as e:
            return self._send(502, {"error": str(e)})
        except UserError as e:
            return self._send(400, {"error": str(e)})
        except (KeyError, TypeError, ValueError) as e:
            return self._send(400, {"error": "bad request: {}".format(e)})
        self._send(200, result)

    # --- API handlers ---
    def api_catalog(self, _id, _body):
        return CATALOG

    def api_setup_status(self, _id, _body):
        cid = os.environ.get("TRIMLIGHT_CLIENT_ID") or ""
        return {"configured": self.client is not None, "clientIdHint": cid[-4:] if self.client else "", "applyUrl": APPLY_URL}

    def api_setup(self, _id, body):
        """Check new credentials against Trimlight, then save them to .env. The secret is never sent back."""
        cid, secret = str(body.get("clientId", "")).strip(), str(body.get("clientSecret", "")).strip()
        for label, value in (("Client ID", cid), ("Client Secret", secret)):
            if not value or len(value) > 128 or any(c.isspace() for c in value):
                raise UserError("Enter a valid {} (no spaces).".format(label))
        client = TrimlightClient(cid, secret)
        try:
            devices = client.list_devices(0)["payload"]["data"]
        except TrimlightError:
            raise UserError("Trimlight didn't accept this Client ID and Client Secret. Copy them again from "
                            "Trimlight's credentials page, without spaces, and try again.")
        save_env({"TRIMLIGHT_CLIENT_ID": cid, "TRIMLIGHT_CLIENT_SECRET": secret})
        os.environ["TRIMLIGHT_CLIENT_ID"], os.environ["TRIMLIGHT_CLIENT_SECRET"] = cid, secret
        Handler.client = client
        return {"configured": True, "clientIdHint": cid[-4:], "devices": [d.get("name") for d in devices]}

    def api_setup_test(self, _id, _body):
        """Sign in to Trimlight with the saved credentials and report what the account can see."""
        try:
            devices = self.client.list_devices(0)["payload"]["data"]
        except TrimlightError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "devices": [{"name": d.get("name"), "online": d.get("connectivity") == 1} for d in devices]}

    def api_disconnect(self, _id, _body):
        """Forget the credentials: remove them from .env (other settings stay) and from this running app."""
        remove_env_keys(CREDENTIAL_KEYS)
        for key in CREDENTIAL_KEYS:
            os.environ.pop(key, None)
        Handler.client = None
        return {"configured": False}

    def api_devices(self, _id, _body):
        return self.client.list_devices(0)["payload"]

    def api_device(self, device_id, _body):
        return self.client.get_device(device_id)["payload"]

    def api_switch(self, device_id, body):
        state = int(body["state"])
        if state not in (0, 1, 2):
            raise ValueError("state must be 0, 1 or 2")
        return self.client.update_device(device_id, switchState=state)

    def api_preview(self, device_id, body):
        speed = clamp(body.get("speed", 100), 0, 255)
        brightness = clamp(body.get("brightness", 100), 0, 255)
        if int(body["category"]) == 0:
            return self.client.preview_builtin(device_id, clamp(body["mode"], 0, 179), speed, brightness,
                                               clamp(body.get("pixelLen", 30), 1, 90),
                                               bool(body.get("reverse", False)))
        return self.client.preview_custom(device_id, clamp(body["mode"], 0, MAX_CUSTOM_MODE),
                                          custom_pixels(body["pixels"]), speed, brightness)

    def api_effect(self, device_id, body):
        return self.client.view_effect(device_id, int(body["id"]))

    def _sync(self, device_id, done, timeout=30):
        """Some writes only show in device details after the controller re-reports its data
        (5-30s in testing). Nudge it, then poll until done(payload) is true or we time out."""
        try:
            self.client.notify_update_shadow(device_id)
        except TrimlightError:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(3)
            try:
                if done(self.client.get_device(device_id)["payload"]):
                    return
            except TrimlightError:
                pass

    def _effects(self, device_id):
        return {e["id"]: e for e in self.client.get_device(device_id)["payload"].get("effects", [])}

    def api_save_effect(self, device_id, body):
        """Create (id null/-1) or update a custom (category 1) pattern."""
        name = str(body.get("name", "")).strip()[:32]
        if not name:
            raise ValueError("name is required")
        existing = self._effects(device_id)
        effect_id = body.get("id")
        effect_id = -1 if effect_id is None else int(effect_id)
        if effect_id == -1:
            if len(existing) >= MAX_EFFECTS:
                raise ValueError("the controller already holds {} patterns".format(MAX_EFFECTS))
        elif effect_id not in existing:
            raise ValueError("no saved effect with that id")
        effect = {
            "id": effect_id,
            "name": name,
            "category": 1,
            "mode": clamp(body["mode"], 0, MAX_CUSTOM_MODE),
            "speed": clamp(body.get("speed", 128), 0, 255),
            "brightness": clamp(body.get("brightness", 255), 0, 255),
            "pixels": custom_pixels(body["pixels"]),
        }
        result = self.client.save_effect(device_id, effect)
        saved_id = (result.get("payload") or {}).get("id", effect_id)
        # The cloud keeps reporting the old version for a few seconds; wait so the page doesn't reload stale values.
        want = {k: effect[k] for k in ("name", "mode", "speed", "brightness")}
        self._sync(device_id, lambda p: any(e["id"] == saved_id and all(e.get(k) == v for k, v in want.items())
                                            for e in p.get("effects", [])))
        if "overlay" in body:
            self._set_overlay(device_id, saved_id, body["overlay"])
        if effect_id != -1:  # an edit may rename the pattern; keep its festival label attached
            update_festivals(lambda data: rename_label(data, device_id, saved_id, name))
        return {"id": saved_id}

    def _set_overlay(self, device_id, effect_id, overlay_type):
        """Change one pattern's overlay; the API replaces the whole list, so merge first."""
        current = self.client.get_device(device_id)["payload"].get("overlayEffects") or []
        overlays = [o for o in current if o.get("targetEffect") != effect_id]
        if overlay_type is not None:
            if int(overlay_type) not in OVERLAYS:
                raise ValueError("overlay must be null, 0 (lightning) or 1 (snow)")
            overlays.append({"overlayType": int(overlay_type), "targetEffect": effect_id})
        result = self.client.set_overlays(device_id, overlays)
        key = lambda os_: sorted((o["overlayType"], o["targetEffect"]) for o in os_ or [])
        self._sync(device_id, lambda p: key(p.get("overlayEffects")) == key(overlays))
        return result

    def api_overlay(self, device_id, body):
        effect_id = int(body["id"])
        if effect_id not in self._effects(device_id):
            raise ValueError("no saved effect with that id")
        return self._set_overlay(device_id, effect_id, body.get("type"))

    def api_rename_effect(self, device_id, body):
        name = str(body["name"]).strip()[:32]
        if not name:
            raise ValueError("name is required")
        effect = self._effects(device_id).get(int(body["id"]))
        if effect is None:
            raise ValueError("no saved effect with that id")
        # Re-save the stored effect unchanged except for its name.
        payload = {k: effect[k] for k in EFFECT_FIELDS if k in effect}
        payload["name"] = name
        result = self.client.save_effect(device_id, payload)
        self._sync(device_id, lambda p: any(e["id"] == effect["id"] and e["name"] == name for e in p.get("effects", [])))
        update_festivals(lambda data: rename_label(data, device_id, effect["id"], name))
        return result

    def api_delete_effect(self, device_id, body):
        effect_id = int(body["id"])
        result = self.client.delete_effect(device_id, effect_id)
        self._sync(device_id, lambda p: all(e["id"] != effect_id for e in p.get("effects", [])))
        update_festivals(lambda data: data["patterns"].get(device_id, {}).pop(str(effect_id), None))
        return result

    # --- Festival groups (stored on this computer) ---
    def api_festivals(self, device_id, _body):
        data = read_festivals()
        return {"festivals": data["festivals"], "patterns": data["patterns"].get(device_id, {})}

    def api_save_festival(self, _id, body):
        f = body["festival"]
        name = str(f.get("name", "")).strip()[:32]
        if not name:
            raise UserError("Give the festival a name.")
        emoji = str(f.get("emoji") or "🎉")[:8]
        color = str(f.get("color") or "#7c3aed")
        if not HEX_COLOR.match(color):
            raise UserError("Pick a color.")
        season = {}
        for key in ("start", "end"):  # optional "MM-DD"
            value = f.get(key) or ""
            if value and not MONTH_DAY.match(value):
                raise UserError("Season dates must look like 10-31.")
            season[key] = value
        result = {}

        def change(data):
            festivals = data["festivals"]
            if any(x["name"].lower() == name.lower() and x["id"] != f.get("id") for x in festivals):
                raise UserError("There's already a festival called {}.".format(name))
            if f.get("id"):
                target = next((x for x in festivals if x["id"] == f["id"]), None)
                if target is None:
                    raise UserError("That festival no longer exists.")
            else:
                base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "festival"
                fid, n = base, 2
                while any(x["id"] == fid for x in festivals):
                    fid, n = "{}-{}".format(base, n), n + 1
                target = {"id": fid}
                festivals.append(target)
            target.update(name=name, emoji=emoji, color=color, **season)
            result.update(target)
        update_festivals(change)
        return result

    def api_delete_festival(self, _id, body):
        fid = str(body["id"])

        def change(data):
            data["festivals"] = [x for x in data["festivals"] if x["id"] != fid]
            for labels in data["patterns"].values():
                for key in [k for k, v in labels.items() if v.get("festival") == fid]:
                    del labels[key]
        update_festivals(change)
        return {"deleted": fid}

    def api_assign_festival(self, device_id, body):
        fid = body.get("festival")
        items = [(str(int(i["id"])), str(i.get("name", ""))[:32]) for i in body["patterns"]]

        def change(data):
            if fid is not None and not any(x["id"] == fid for x in data["festivals"]):
                raise UserError("That festival no longer exists.")
            labels = data["patterns"].setdefault(device_id, {})
            for key, name in items:
                if fid is None:
                    labels.pop(key, None)
                else:
                    labels[key] = {"festival": fid, "name": name}
        update_festivals(change)
        return {"assigned": len(items)}

    def api_combined(self, device_id, body):
        ids = [int(i) for i in body["effectIds"]]
        if not 1 <= len(ids) <= 5:
            raise ValueError("pick 1 to 5 patterns")
        missing = set(ids) - set(self._effects(device_id))
        if missing:
            raise ValueError("unknown effect ids: {}".format(sorted(missing)))
        interval = clamp(body["interval"], 1, 1440)
        result = self.client.save_combined_effect(device_id, ids, interval)
        want = {"effectIds": ids, "interval": interval}
        self._sync(device_id, lambda p: p.get("combinedEffect") == want)
        return result

    def api_daily(self, device_id, body):
        today = current_date()
        schedule = {
            "id": clamp(body["id"], 0, 1),
            "enable": bool(body["enable"]),
            "effectId": int(body["effectId"]),
            "repetition": clamp(body.get("repetition", 1), 0, 3),
            "startTime": schedule_time(body["startTime"]),
            "endTime": schedule_time(body["endTime"]),
        }
        result = self.client.save_daily(device_id, dict(schedule, currentDate={"month": today["month"], "day": today["day"]}))
        self._sync(device_id, lambda p: schedule in p.get("daily", []))
        return result

    def api_calendar(self, device_id, body):
        # New events must be sent with id -1 so the controller assigns a slot. Sending an unused
        # id (e.g. 0) returns "success" but stores nothing: an explicit id only updates an existing event.
        existing = {c["id"] for c in self.client.get_device(device_id)["payload"].get("calendar", [])}
        schedule_id = body.get("id")
        if schedule_id is None or int(schedule_id) == -1:
            if len(existing) >= 60:
                raise ValueError("all 60 calendar slots are used")
            schedule_id = -1
        elif int(schedule_id) not in existing:
            raise ValueError("no calendar event with that id")
        schedule = {
            "id": int(schedule_id),
            "effectId": int(body["effectId"]),
            "startDate": schedule_date(body["startDate"]),
            "endDate": schedule_date(body["endDate"]),
            "startTime": schedule_time(body["startTime"]),
            "endTime": schedule_time(body["endTime"]),
        }
        result = self.client.save_calendar(device_id, schedule)
        saved = dict(schedule, id=(result.get("payload") or {}).get("id", schedule["id"]))
        self._sync(device_id, lambda p: saved in p.get("calendar", []))
        return result

    def api_delete_calendar(self, device_id, body):
        schedule_id = clamp(body["id"], 0, 59)
        result = self.client.delete_calendar(device_id, schedule_id)
        self._sync(device_id, lambda p: all(c["id"] != schedule_id for c in p.get("calendar", [])))
        return result

    # --- Device settings, clock, backups ---
    def api_refresh(self, device_id, _body):
        """Ask the controller to re-report, then return its details once they arrive."""
        self.client.notify_update_shadow(device_id)
        time.sleep(3)
        return self.client.get_device(device_id)["payload"]

    def api_settings(self, device_id, body):
        payload = {}
        if "name" in body:
            name = str(body["name"]).strip()[:32]
            if not name:
                raise ValueError("name is required")
            payload["name"] = name
        if "colorOrder" in body:
            payload["colorOrder"] = clamp(body["colorOrder"], 0, len(COLOR_ORDERS) - 1)
        if "ic" in body:
            payload["ic"] = clamp(body["ic"], 0, len(ICS) - 1)
        if "ports" in body:
            ports = []
            for port in body["ports"]:
                start, end = clamp(port["start"], 1, 2048), clamp(port["end"], 1, 2048)
                if start > end:
                    raise ValueError("port start can't be after its end")
                # Controllers report port ids 1-4 although the spec says 0-3, so send back what they use.
                ports.append({"id": clamp(port["id"], 0, 4), "start": start, "end": end})
            payload["ports"] = ports
        if not payload:
            raise ValueError("nothing to change")
        result = self.client.update_device(device_id, **payload)
        self._sync(device_id, lambda p: all(p.get(k) == v for k, v in payload.items()))
        return result

    def api_datetime(self, device_id, _body):
        return self.client.sync_datetime(device_id)

    def api_backup_info(self, device_id, _body):
        # The page only needs the time; restores look the key up again server-side.
        latest = self.client.get_backup(device_id).get("payload") or {}
        return {"backupTime": latest.get("backupTime")}

    def api_backup(self, device_id, _body):
        return self.client.backup(device_id, backup_time())

    def api_restore(self, device_id, body):
        # Restore only the backup the user was shown, so a newer one can't be restored by surprise.
        latest = self.client.get_backup(device_id).get("payload") or {}
        if not latest.get("backupKey"):
            raise ValueError("this controller has no cloud backup")
        if body.get("backupTime") != latest.get("backupTime"):
            raise ValueError("the backup changed since this page loaded; refresh and try again")
        result = self.client.restore_backup(device_id, latest["backupKey"])
        self._sync(device_id, lambda p: True, timeout=6)
        return result

    # --- Groups ---
    def api_groups(self, _id, _body):
        return self.client.list_groups(0)["payload"]

    def _group_members(self, body):
        master = str(body["masterDevice"])
        devices = [str(d) for d in body["devices"]]
        if master not in devices:
            devices.insert(0, master)
        if len(devices) < 2:
            raise ValueError("a group needs at least two controllers")
        return master, devices

    def api_add_group(self, _id, body):
        name = str(body["name"]).strip()[:32]
        if not name:
            raise ValueError("name is required")
        master, devices = self._group_members(body)
        return self.client.add_group(name, master, devices)

    def api_update_group(self, _id, body):
        master, devices = self._group_members(body)
        return self.client.update_group(str(body["groupId"]), master, devices)

    def api_rename_group(self, _id, body):
        name = str(body["name"]).strip()[:32]
        if not name:
            raise ValueError("name is required")
        return self.client.rename_group(str(body["groupId"]), name)

    def api_delete_group(self, _id, body):
        return self.client.delete_group(str(body["groupId"]))

    def api_sync_group(self, _id, body):
        return self.client.sync_group(str(body["groupId"]))


def read_festivals():
    """Festival list and per-controller labels; created with common holidays on first use."""
    try:
        with open(FESTIVALS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("festivals", [{"id": i, "name": n, "emoji": e, "color": c, "start": "", "end": ""}
                                  for i, n, e, c in DEFAULT_FESTIVALS])
    data.setdefault("patterns", {})  # {deviceId: {effectId: {"festival": id, "name": pattern name}}}
    return data


def update_festivals(change):
    """Read, apply change(data), and save atomically; one writer at a time."""
    with FESTIVAL_LOCK:
        data = read_festivals()
        change(data)
        tmp = FESTIVALS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, FESTIVALS_FILE)


def rename_label(data, device_id, effect_id, name):
    label = data["patterns"].get(device_id, {}).get(str(effect_id))
    if label:
        label["name"] = name


def save_env(values):
    """Set keys in .env, keeping any other lines (e.g. TRIMLIGHT_CA_BUNDLE). Private to this user."""
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    pending = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in pending:
            lines[i] = "{}={}".format(key, pending.pop(key))
    lines += ["{}={}".format(k, v) for k, v in pending.items()]
    tmp = ENV_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


def remove_env_keys(keys):
    """Delete these keys from .env, keeping every other line; remove the file if nothing else is left."""
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    kept = [ln for ln in lines if not ("=" in ln and not ln.lstrip().startswith("#") and ln.split("=", 1)[0].strip() in keys)]
    if not any(ln.strip() and not ln.lstrip().startswith("#") for ln in kept):
        os.remove(ENV_FILE)
        return
    tmp = ENV_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(kept) + "\n")
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


def credentials():
    load_env(ENV_FILE)
    return os.environ.get("TRIMLIGHT_CLIENT_ID"), os.environ.get("TRIMLIGHT_CLIENT_SECRET")


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def run_checks(port):
    """--check: confirm this computer can run the app, without changing anything."""
    results = []

    def step(name, fn):
        try:
            detail = fn()
            results.append(True)
            print("  OK    {}{}".format(name, "  ({})".format(detail) if detail else ""))
        except Exception as e:  # report every failure, keep going
            results.append(False)
            print("  FAIL  {}  ->  {}".format(name, e))

    def python_ok():
        if sys.version_info < (3, 7):
            raise RuntimeError("Python 3.7 or newer is needed; this is {}".format(sys.version.split()[0]))
        return "Python {} on {}".format(sys.version.split()[0], sys.platform)

    def files_ok():
        if not os.path.exists(INDEX):
            raise RuntimeError("missing " + INDEX)
        return None

    def creds_ok():
        cid, secret = credentials()
        if not cid or not secret:
            raise RuntimeError("not set; start the app and add them on its Home page (or fill in .env)")
        return "client ID ends in ..." + cid[-4:]

    def tls_ok():
        from trimlight import BASE_URL, ssl_context
        host = BASE_URL.split("/")[2]
        with socket.create_connection((host, 443), timeout=10) as raw:
            with ssl_context().wrap_socket(raw, server_hostname=host):
                pass
        return host

    def api_ok():
        cid, secret = credentials()
        if not cid or not secret:
            raise RuntimeError("skipped: no credentials yet")
        devices = TrimlightClient(cid, secret).list_devices(0)["payload"]["data"]
        return "{} controller(s): {}".format(len(devices), ", ".join(d["name"] for d in devices) or "none")

    def port_ok():
        if port_free(port):
            return "port {}".format(port)
        try:  # is it this app?
            with urllib.request.urlopen("http://127.0.0.1:{}/api/catalog".format(port), timeout=5) as r:
                if "builtin" in json.loads(r.read()):
                    return "the app is already running at http://localhost:{}".format(port)
        except (OSError, ValueError):
            pass
        raise RuntimeError("port {} is used by another program; start with --port 8766".format(port))

    def zone_ok():
        try:
            return backup_time().split(" ", 2)[2]
        except TrimlightError:  # only cloud backups need a US zone; don't fail the whole check
            return "not a US time zone: cloud backups won't work, everything else will"

    print("Trimlight app self-check")
    step("Python version", python_ok)
    step("App files", files_ok)
    step("Credentials in .env", creds_ok)
    step("Secure connection to Trimlight", tls_ok)
    step("Trimlight API sign-in", api_ok)
    step("Local port", port_ok)
    step("Time zone for cloud backups", zone_ok)
    print("All checks passed." if all(results) else "Some checks failed; see README.md > Troubleshooting.")
    return 0 if all(results) else 1


def main():
    p = argparse.ArgumentParser(description="Trimlight local web app")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="don't open the app in a browser on start")
    p.add_argument("--check", action="store_true", help="check this computer can run the app, then exit")
    args = p.parse_args()

    if args.check:
        return run_checks(args.port)

    client_id, client_secret = credentials()
    # Without credentials the app still starts; its Home page walks you through adding them.
    Handler.client = TrimlightClient(client_id, client_secret) if client_id and client_secret else None
    # On Windows, SO_REUSEADDR lets a second copy bind the same port silently; fail loudly instead.
    ThreadingHTTPServer.allow_reuse_address = os.name != "nt"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        print("Port {} is already in use. The app may already be running at http://localhost:{}\n"
              "or start it on another port: python webapp.py --port 8766".format(args.port, args.port), file=sys.stderr)
        return 1
    url = "http://localhost:{}".format(args.port)
    print("Trimlight app running at {}  (press Ctrl+C to stop)".format(url), flush=True)
    if Handler.client is None:
        print("No credentials yet: open the app and follow the setup steps on its Home page.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
