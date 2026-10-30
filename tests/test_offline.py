"""Offline tests: no internet, no credentials, never touch a controller.

Run from the project folder on Mac or Windows:
    python3 -m unittest discover tests        (Mac)
    py -3 -m unittest discover tests          (Windows)
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import trimlight  # noqa: E402
import webapp  # noqa: E402


class AuthTests(unittest.TestCase):
    def test_token_matches_spec_example(self):
        # API docs, "Authentication > 3. Example".
        self.assertEqual(trimlight.make_token("tester", "test_secret", 1713166849256),
                         "z02N77XySuOwv5OSUe0vrPwprRITb656xKPulS9ooXI=")

    def test_headers(self):
        h = trimlight.TrimlightClient("id", "secret")._headers()
        self.assertEqual(h["S-ClientId"], "id")
        self.assertTrue(h["S-Timestamp"].isdigit() and len(h["S-Timestamp"]) == 13)

    def test_current_date_format(self):
        d = trimlight.current_date()
        self.assertTrue(0 <= d["year"] < 100 and 1 <= d["month"] <= 12 and 1 <= d["weekday"] <= 7)


class EnvFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.saved = {k: os.environ.pop(k, None) for k in ("TL_A", "TL_B", "TL_C")}

    def tearDown(self):
        shutil.rmtree(self.dir)
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def write(self, data):
        path = os.path.join(self.dir, ".env")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_windows_notepad_file(self):
        # UTF-8 with a byte-order mark and CRLF line endings, as Notepad can save it.
        trimlight.load_env(self.write(b'\xef\xbb\xbfTL_A=one\r\n# comment\r\nTL_B="two"\r\n\r\n'))
        self.assertEqual((os.environ["TL_A"], os.environ["TL_B"]), ("one", "two"))

    def test_mac_file_and_no_override(self):
        os.environ["TL_C"] = "from-env"
        trimlight.load_env(self.write(b"TL_A=x\nTL_C=from-file\n"))
        self.assertEqual((os.environ["TL_A"], os.environ["TL_C"]), ("x", "from-env"))

    def test_missing_file_is_fine(self):
        trimlight.load_env(os.path.join(self.dir, "nope"))


class BackupTimeTests(unittest.TestCase):
    """Windows reports long zone names ("Eastern Daylight Time"); the abbreviation comes from the offset."""

    def at(self, timezone_seconds_west, dst):
        t = time.localtime()
        fake = time.struct_time(t[:8] + (1 if dst else 0,))
        with mock.patch.object(trimlight.time, "timezone", timezone_seconds_west), \
                mock.patch.object(trimlight.time, "localtime", return_value=fake):
            return trimlight.backup_time()

    def test_us_zones(self):
        for west, dst, zone in [(18000, True, "EDT"), (18000, False, "EST"), (21600, True, "CDT"), (25200, False, "MST"),
                                (28800, True, "PDT"), (32400, False, "AKST"), (36000, False, "HST")]:
            self.assertTrue(self.at(west, dst).endswith(" " + zone), zone)

    def test_format(self):
        value = self.at(18000, True)
        time.strptime(value[:19], "%Y-%m-%d %H:%M:%S")

    def test_outside_us_is_refused(self):
        with self.assertRaises(trimlight.TrimlightError):
            self.at(-3600, False)  # UTC+1


class HelperTests(unittest.TestCase):
    def test_catalog(self):
        self.assertEqual(len(webapp.CATALOG["builtin"]), 180)
        self.assertEqual(len(webapp.CATALOG["custom"]), 17)

    def test_custom_pixels(self):
        px = webapp.custom_pixels([{"color": 0xFF0000, "count": 999}, {"color": 1}])
        self.assertEqual(px[0]["count"], webapp.MAX_PIXEL_COUNT)
        self.assertEqual(px[1], {"index": 1, "count": 1, "color": 1, "disable": False})
        with self.assertRaises(ValueError):
            webapp.custom_pixels([])

    def test_parse_color(self):
        for v in ("#ff0000", "FF0000", "0xff0000", "16711680"):
            self.assertEqual(trimlight.parse_color(v), 0xFF0000)


class FakeClient:
    """Stands in for the Trimlight cloud so the server can be exercised offline."""

    def __init__(self):
        self.calls = []

    def list_devices(self, page):
        return {"payload": {"data": [{"deviceId": "dev1", "name": "Test", "connectivity": 1}]}}

    def get_device(self, device_id):
        return {"payload": {"effects": [{"id": 1, "name": "A", "category": 1, "mode": 0}], "overlayEffects": [],
                            "calendar": [], "daily": [], "switchState": 2}}

    def update_device(self, device_id, **payload):
        self.calls.append(("update", payload))
        return {"code": 0}

    def delete_effect(self, device_id, effect_id):
        self.calls.append(("delete", effect_id))
        return {"code": 0}

    def notify_update_shadow(self, device_id):
        raise trimlight.TrimlightError("offline")  # makes the server skip its wait-for-sync loop


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        webapp.Handler.client = FakeClient()
        webapp.Handler.log_message = lambda *a: None
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def req(self, method, path, body=None, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, method=method, headers=h)) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_page(self):
        status, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>Trimlight Control</title>", body)

    def test_reads(self):
        self.assertEqual(self.req("GET", "/api/catalog")[0], 200)
        self.assertEqual(json.loads(self.req("GET", "/api/devices")[1])["data"][0]["deviceId"], "dev1")
        self.assertEqual(self.req("GET", "/api/device/dev1")[0], 200)

    def test_foreign_host_refused(self):
        self.assertEqual(self.req("GET", "/api/catalog", headers={"Host": "evil.example"})[0], 403)

    def test_post_needs_app_header(self):
        self.assertEqual(self.req("POST", "/api/device/dev1/switch", {"state": 2})[0], 403)
        self.assertEqual(webapp.Handler.client.calls, [])

    def test_post_with_header(self):
        status, _ = self.req("POST", "/api/device/dev1/switch", {"state": 2}, {"X-Trimlight-App": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(webapp.Handler.client.calls[-1], ("update", {"switchState": 2}))

    def test_validation(self):
        app = {"X-Trimlight-App": "1"}
        self.assertEqual(self.req("POST", "/api/device/dev1/switch", {"state": 9}, app)[0], 400)
        self.assertEqual(self.req("POST", "/api/device/dev1/settings", {}, app)[0], 400)
        self.assertEqual(self.req("GET", "/api/nope")[0], 404)


class SetupTests(unittest.TestCase):
    """First run: no credentials yet, then adding them from the Home page."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.env = os.path.join(cls.dir, ".env")
        with open(cls.env, "w") as f:
            f.write("# keep me\nTRIMLIGHT_CA_BUNDLE=/x/ca.pem\nTRIMLIGHT_CLIENT_ID=old\n")
        cls.patches = [mock.patch.object(webapp, "ENV_FILE", cls.env), mock.patch.object(webapp.Handler, "client", None)]
        for p in cls.patches:
            p.start()
        webapp.Handler.log_message = lambda *a: None
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        for p in cls.patches:
            p.stop()
        for k in ("TRIMLIGHT_CLIENT_ID", "TRIMLIGHT_CLIENT_SECRET"):
            os.environ.pop(k, None)
        shutil.rmtree(cls.dir)

    req = ServerTests.req

    def test_1_needs_setup(self):
        status, body = self.req("GET", "/api/setup")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["configured"])
        status, body = self.req("GET", "/api/devices")
        self.assertEqual(status, 503)
        self.assertTrue(json.loads(body)["setup"])

    def test_2_rejects_bad_input(self):
        app = {"X-Trimlight-App": "1"}
        self.assertEqual(self.req("POST", "/api/setup", {"clientId": "", "clientSecret": "x"}, app)[0], 400)
        self.assertEqual(self.req("POST", "/api/setup", {"clientId": "a b", "clientSecret": "x"}, app)[0], 400)
        with mock.patch.object(webapp.TrimlightClient, "list_devices", side_effect=trimlight.TrimlightError("API error 401")):
            self.assertEqual(self.req("POST", "/api/setup", {"clientId": "id1", "clientSecret": "bad"}, app)[0], 400)
        with open(self.env) as f:
            self.assertIn("TRIMLIGHT_CLIENT_ID=old", f.read())  # nothing saved on failure

    def test_3_saves_and_connects(self):
        fake = {"payload": {"data": [{"deviceId": "d1", "name": "Porch"}]}}
        with mock.patch.object(webapp.TrimlightClient, "list_devices", return_value=fake):
            status, body = self.req("POST", "/api/setup", {"clientId": "NewId1234", "clientSecret": "s3cret"}, {"X-Trimlight-App": "1"})
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertEqual((res["devices"], res["clientIdHint"]), (["Porch"], "1234"))
        self.assertNotIn(b"s3cret", body)  # the secret is never sent back
        with open(self.env) as f:
            text = f.read()
        self.assertIn("# keep me", text)
        self.assertIn("TRIMLIGHT_CA_BUNDLE=/x/ca.pem", text)
        self.assertIn("TRIMLIGHT_CLIENT_ID=NewId1234", text)
        self.assertIn("TRIMLIGHT_CLIENT_SECRET=s3cret", text)
        self.assertNotIn("=old", text)
        if os.name != "nt":
            self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)
        self.assertTrue(json.loads(self.req("GET", "/api/setup")[1])["configured"])

    def test_4_setup_needs_app_header(self):
        self.assertEqual(self.req("POST", "/api/setup", {"clientId": "x", "clientSecret": "y"})[0], 403)

    def test_5_test_connection(self):
        app = {"X-Trimlight-App": "1"}
        fake = {"payload": {"data": [{"deviceId": "d1", "name": "Porch", "connectivity": 1}]}}
        with mock.patch.object(webapp.TrimlightClient, "list_devices", return_value=fake):
            res = json.loads(self.req("POST", "/api/setup/test", {}, app)[1])
        self.assertEqual(res, {"ok": True, "devices": [{"name": "Porch", "online": True}]})
        with mock.patch.object(webapp.TrimlightClient, "list_devices", side_effect=trimlight.TrimlightError("network down")):
            res = json.loads(self.req("POST", "/api/setup/test", {}, app)[1])
        self.assertFalse(res["ok"])
        self.assertIn("network down", res["error"])

    def test_6_disconnect(self):
        status, body = self.req("POST", "/api/setup/disconnect", {}, {"X-Trimlight-App": "1"})
        self.assertEqual(status, 200)
        with open(self.env) as f:
            text = f.read()
        self.assertNotIn("TRIMLIGHT_CLIENT_ID", text)
        self.assertNotIn("TRIMLIGHT_CLIENT_SECRET", text)
        self.assertIn("TRIMLIGHT_CA_BUNDLE=/x/ca.pem", text)  # other settings are kept
        self.assertFalse(json.loads(self.req("GET", "/api/setup")[1])["configured"])
        self.assertEqual(self.req("GET", "/api/devices")[0], 503)
        self.assertEqual(self.req("POST", "/api/setup/test", {}, {"X-Trimlight-App": "1"})[0], 503)

    def test_7_disconnect_removes_env_with_only_credentials(self):
        with open(self.env, "w") as f:
            f.write("TRIMLIGHT_CLIENT_ID=a\nTRIMLIGHT_CLIENT_SECRET=b\n")
        self.req("POST", "/api/setup/disconnect", {}, {"X-Trimlight-App": "1"})
        self.assertFalse(os.path.exists(self.env))

    def test_8_disconnect_needs_app_header(self):
        self.assertEqual(self.req("POST", "/api/setup/disconnect", {})[0], 403)


class FestivalTests(unittest.TestCase):
    """Festival labels live in festivals.json on this computer."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.patch = mock.patch.object(webapp, "FESTIVALS_FILE", os.path.join(cls.dir, "festivals.json"))
        cls.patch.start()
        webapp.Handler.client = FakeClient()
        webapp.Handler.log_message = lambda *a: None
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.patch.stop()
        shutil.rmtree(cls.dir)

    req = ServerTests.req
    APP = {"X-Trimlight-App": "1"}

    def get(self, device="dev1"):
        return json.loads(self.req("GET", "/api/device/%s/festivals" % device)[1])

    def test_1_defaults(self):
        data = self.get()
        ids = [f["id"] for f in data["festivals"]]
        self.assertIn("halloween", ids)
        self.assertIn("diwali", ids)
        self.assertEqual(data["patterns"], {})

    def test_2_create_and_validate(self):
        status, body = self.req("POST", "/api/festivals", {"festival": {"name": "Lunar New Year", "emoji": "🧧", "color": "#e11d48",
                                                                       "start": "01-20", "end": "02-20"}}, self.APP)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["id"], "lunar-new-year")
        for bad in ({"name": ""}, {"name": "lunar new year"}, {"name": "X", "color": "red"}, {"name": "Y", "start": "13-40"}):
            self.assertEqual(self.req("POST", "/api/festivals", {"festival": bad}, self.APP)[0], 400, bad)

    def test_3_assign_per_controller(self):
        self.req("POST", "/api/device/dev1/festivals/assign", {"patterns": [{"id": 1, "name": "A"}], "festival": "halloween"}, self.APP)
        self.assertEqual(self.get()["patterns"]["1"], {"festival": "halloween", "name": "A"})
        self.assertEqual(self.get("dev2")["patterns"], {})  # other controllers unaffected
        self.assertEqual(self.req("POST", "/api/device/dev1/festivals/assign",
                                  {"patterns": [{"id": 1, "name": "A"}], "festival": "nope"}, self.APP)[0], 400)

    def test_4_delete_pattern_drops_label(self):
        self.req("POST", "/api/device/dev1/festivals/assign", {"patterns": [{"id": 1, "name": "A"}], "festival": "diwali"}, self.APP)
        self.assertEqual(self.req("POST", "/api/device/dev1/effect/delete", {"id": 1}, self.APP)[0], 200)
        self.assertNotIn("1", self.get()["patterns"])

    def test_5_delete_festival_clears_labels(self):
        self.req("POST", "/api/device/dev1/festivals/assign", {"patterns": [{"id": 1, "name": "A"}], "festival": "lunar-new-year"}, self.APP)
        self.assertEqual(self.req("POST", "/api/festivals/delete", {"id": "lunar-new-year"}, self.APP)[0], 200)
        data = self.get()
        self.assertNotIn("lunar-new-year", [f["id"] for f in data["festivals"]])
        self.assertNotIn("1", data["patterns"])

    def test_6_unassign(self):
        self.req("POST", "/api/device/dev1/festivals/assign", {"patterns": [{"id": 1, "name": "A"}], "festival": "easter"}, self.APP)
        self.req("POST", "/api/device/dev1/festivals/assign", {"patterns": [{"id": 1, "name": "A"}], "festival": None}, self.APP)
        self.assertEqual(self.get()["patterns"], {})


class LauncherTests(unittest.TestCase):
    def test_windows_launcher_uses_crlf(self):
        with open(os.path.join(ROOT, "start-windows.bat"), "rb") as f:
            data = f.read()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""), "batch files need CRLF line endings")

    def test_files_present(self):
        for name in ("README.md", "LICENSE", ".env.example", "start-mac.command", "start-windows.bat", "static/index.html"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)), name)


if __name__ == "__main__":
    unittest.main()
