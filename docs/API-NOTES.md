# Trimlight API notes

These are behaviors of the Trimlight Edge V2 API (docs version 1.4.0, <https://trimlight.ledhue.com/api-doc/v2/README.md>) that the official documentation doesn't spell out. Each one was found by testing against a real controller in October 2026. The app is built around them.

## Authentication
- **Headers:** every request carries `authorization`, `S-ClientId` and `S-Timestamp` (epoch milliseconds).
- **Token:** `base64(HMAC-SHA256("Trimlight|<clientId>|<timestamp>", clientSecret))`. The docs' example token (`z02N77Xy…`) is correct, and `tests/test_offline.py` checks against it.
- **Time:** requests are rejected if the computer's clock is far off.

## Creating vs. updating
- **Patterns** (`device/effect/save`):
  - `id: -1` creates a new pattern; the controller assigns the id.
  - An existing id updates that pattern.
- **Calendar events** (`device/calendar/save`):
  - `id: -1` creates a new event.
  - An existing id updates it.
  - An **unused** id, such as the docs' example `"id": 0`, returns `success` but **stores nothing**.

## Cloud lag
- **Writes aren't visible straight away.** They return `success` immediately, but `device/get` keeps returning the old data until the controller re-reports, usually 5–30 seconds later. This affects patterns, overlays, the rotation, daily schedules and calendar events.
- **What the app does:** after each write it calls `device/notify-update-shadow`, then polls `device/get` every 3 seconds (up to 30 seconds) until the change appears. Only then does the page refresh.
- **Edits right after a create:** an update sent right after a create can be refused as "no saved effect with that id" if the new pattern hasn't been reported yet. Waiting for the create to appear avoids this.

## Values outside the documented ranges
- **Animations:** the phone app saves custom patterns with modes **17–22**, while the docs list 0–16. The controller plays them, but their names aren't published. The app keeps them as "Mode N".
- **Pixel counts:** the phone app saves counts up to about 90, while the docs say 0–60. The app allows up to 255.
- **Port ids:** controllers report ports with ids **1–4**, while the docs say 0–3. The app sends back the ids the controller reports.
- **Weekday:** the controller's clock reported weekday 3 on a Wednesday. The docs say SUNDAY=1, which would make Wednesday 4. "Sync clock" uses the documented numbering, which only matters for "Weekdays"/"Weekends" schedules.

## Overlays (lightning / snow)
- **`device/effect/overlay` replaces the whole overlay list.** To change one pattern's overlay, read the current list, change the one entry, and send the full list back.
- **Overlay types:** `overlayType` 0 is Lightning and 1 is Snow.
- **Previews don't show overlays.** Overlays play only when a saved pattern runs.

## Other details
- **List requests:** `GET /devices` and the group endpoints take a JSON **body** on a GET request.
- **Device details:** `device/get` needs a `currentDate` object, in which the year counts from 2000.
- **Backups:** Trimlight keeps **one** cloud backup per controller, and each new backup replaces it. `backupTime` needs a US zone abbreviation (`EDT`, `PST`, …). Windows reports long zone names, so the app derives the abbreviation from the UTC offset.
- **Power:** playing or previewing a pattern switches the controller to manual mode (`switchState` 1).
- **Errors:** the cloud fails now and then with error **12006** ("Device data could not be parsed") or responds slowly. Retrying a minute later works.
- **Certificates:** Apple's built-in Python 3.7 has no CA certificates, so the client falls back to `/etc/ssl/cert.pem`.
