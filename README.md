# Trimlight Control

A local web app for Trimlight Edge permanent lights. It runs on your own Mac or Windows PC and talks to your controller through Trimlight's official cloud API. It does everything the phone app does, plus:

- A **live preview** of each pattern on a house roofline, including lightning and snow effects
- A **pattern library** with search, filters and animated previews
- A **5-pattern rotation** that schedules can play
- **Daily schedules** and **calendar events**
- **Cloud backup and restore**, **clock sync**, **groups** and **hardware setup**

The app runs only on your computer and answers only to that computer. Your Trimlight secret stays in a private file on disk and is never sent to the browser.

---

## Contents

1. [What you need](#what-you-need)
2. [Install Python](#install-python)
3. [Get your Trimlight API credentials](#get-your-trimlight-api-credentials)
4. [Set up on a Mac](#set-up-on-a-mac)
5. [Set up on Windows](#set-up-on-windows)
6. [Check your setup](#check-your-setup)
7. [Using the app](#using-the-app)
8. [Command-line tool](#command-line-tool)
9. [Troubleshooting](#troubleshooting)
10. [Testing](#testing)
11. [Files](#files)
12. [Security](#security)
13. [Disclaimer](#disclaimer)
14. [Contributing](#contributing)
15. [License](#license)

---

## What you need

| | Requirement |
|---|---|
| Computer | macOS 10.15 or newer, or Windows 10/11 |
| Python | 3.7 or newer (3.11+ recommended). No extra packages: the app uses only Python's standard library |
| Browser | Chrome or Edge 111+, Safari 16.4+, or Firefox 113+ (any browser from 2023 onward) |
| Internet | Needed: the app reaches your controller through Trimlight's cloud |
| Trimlight | A Trimlight Edge controller on your Trimlight account, and API credentials (Client ID + Client Secret) |

The computer running the app needs to be on while you use it. You open the app in a browser on that same computer.

---

## Install Python

**Mac**

1. Open **Terminal** (Applications → Utilities) and type `python3 --version`.
2. If it prints `Python 3.7` or higher, you're set.
3. If not, install the latest Python from <https://www.python.org/downloads/macos/>.
4. **If you installed from python.org,** open **Applications → Python 3.x** and double-click **Install Certificates.command** once. Without this step, secure connections to Trimlight fail.

**Windows**

1. Download the latest Python from <https://www.python.org/downloads/windows/> and run the installer.
2. On the first screen, tick **"Add python.exe to PATH"**, then click **Install Now**.
3. Open **Command Prompt** and type `py --version`. It should print `Python 3.x`.

> Avoid the Microsoft Store "python" shortcut. If typing `python` opens the Store, use `py` instead, or install from python.org as above.

---

## Get your Trimlight API credentials

Each Trimlight owner gets their own **Client ID** and **Client Secret** from Trimlight. It takes about a minute:

1. Go to Trimlight's credentials page: **<https://trimlight.ledhue.com/trimlight/v1/api-credentials/apply>**
2. Sign in with the **email and password you use in the Trimlight Edge phone app**, or ask for an email code.
3. Copy the **Client ID** and **Client Secret** it shows.

Your controller must already be set up on that Trimlight account in the phone app.

You enter your Trimlight password only on Trimlight's own page, never in this app. Treat the Client Secret like a password, and don't share it or post it online.

---

## Set up on a Mac

1. [Download this project](#download) and unzip it somewhere convenient, for example `Documents/Trimlight`.
2. **Start the app:** double-click **`start-mac.command`**.
   - The first time, macOS may say it's from an unidentified developer. Right-click the file, choose **Open**, then **Open** again.
   - Or run it from Terminal:
     ```bash
     cd ~/Documents/Trimlight
     python3 webapp.py
     ```
3. Your browser opens at **http://localhost:8765** on the **Home** page.
4. **Connect your account:** follow the three setup steps on the Home page. Open Trimlight's credentials page, paste your Client ID and Client Secret, then click **Connect & save**. The app checks them with Trimlight and saves them in a private `.env` file in the app folder. You only do this once.
5. To stop the app, close the Terminal window or press **Ctrl + C** in it.

---

## Set up on Windows

1. [Download this project](#download) and unzip it somewhere convenient, for example `Documents\Trimlight`. Use **Extract All**; don't run it from inside the zip.
2. **Start the app:** double-click **`start-windows.bat`**.
   - If SmartScreen warns, click **More info → Run anyway**.
   - Or run it from Command Prompt:
     ```
     cd %USERPROFILE%\Documents\Trimlight
     py -3 webapp.py
     ```
3. Your browser opens at **http://localhost:8765** on the **Home** page.
4. **Connect your account** with the three setup steps on the Home page, as on a Mac.
5. To stop the app, close the window or press **Ctrl + C** in it.

The app only listens on your own computer (`127.0.0.1`), so Windows Firewall won't ask for permission.

### Download

- **With Git:** `git clone <this repository's URL>`
- **Without Git:** on the repository page, click **Code → Download ZIP**, then unzip it.

### Setting credentials by hand (optional)

If you'd rather not use the Home page:
1. Copy **`.env.example`** to **`.env`** in the app folder.
   - Mac: press **Cmd + Shift + .** in Finder to show hidden files.
   - Windows: turn on **View → Show → File name extensions** so it isn't saved as `.env.txt`.
2. Fill in:
   ```
   TRIMLIGHT_CLIENT_ID=your-client-id
   TRIMLIGHT_CLIENT_SECRET=your-client-secret
   ```
3. Start the app.

To check, change or remove credentials later, go to **Device → Trimlight account** (see [Device](#device)).

---

## Check your setup

Run the self-check after setting up, or whenever something seems wrong. It doesn't change anything on your controller.

```bash
python3 webapp.py --check
```

On Windows:

```
py -3 webapp.py --check
```

Example output:

```
Trimlight app self-check
  OK    Python version  (Python 3.12.1 on win32)
  OK    App files
  OK    Credentials in .env  (client ID ends in ...a1b2)
  OK    Secure connection to Trimlight  (trimlight.ledhue.com)
  OK    Trimlight API sign-in  (1 controller(s): Trimlight)
  OK    Local port  (port 8765)
  OK    Time zone for cloud backups  (EDT)
All checks passed.
```

**Start-up options**

| Option | What it does |
|---|---|
| `--port 8766` | Use a different port, if 8765 is taken |
| `--no-browser` | Don't open a browser tab on start |
| `--check` | Run the self-check and exit |

---

## Using the app

The app has six sections. It opens on **Home**: a welcome page with your controller's status, what your schedules will do tonight, and shortcuts to everything else. On first run, Home also walks you through connecting your Trimlight account. On a computer they're in a sidebar; on narrow windows they're in a tab bar along the bottom.

The header has:
- your controller;
- an online indicator;
- **power**: **On** (manual), **Off**, or **Schedule** (hand control back to your schedules);
- **refresh** (↻), which asks the controller for fresh data.

### Colors: create and edit patterns
- **Your patterns:** every saved pattern, in a **List** (sortable table), **Grid** or **Compact** view, with search. Click one to edit it, or click **+ New pattern**.
- **Festivals:** label patterns by occasion (🎃 Halloween, 🪔 Diwali, 🎄 Christmas and more), filter by festival, and group the list by festival.
  - **Set one:** click a pattern's festival label, or tick several patterns and use **Set festival…**.
  - **New festival:** add your own with an icon, color and optional season. In-season festivals are listed first.
  - **Manage…:** edit or delete festivals, or use **Auto-group by name** for a first guess from pattern names.
  - **Where they're kept:** festivals are saved on this computer in `festivals.json`. The controller has no folders, so they don't appear in the phone app.
- **Preview:** your pattern animating on a house roofline, with ⚡ lightning flashes or ❄ falling snow if set.
- **Color sequence:** blocks sized by pixel count. Click a block, then a color, to change it. Use the − / + steppers to set pixels, the trash icon to remove a color, and **+ Add color** to add one (up to 30).
- **Animation:** 17 animations in four groups:

  | Group | Animations |
  |---|---|
  | Steady | Static, Stars, Breath, Strobe, Solid Fade |
  | Chase | Forward, Backward, Middle to Out, Out to Middle |
  | Comet | Forward, Backward, Middle to Out, Out to Middle |
  | Wave | Forward, Backward, Middle to Out, Out to Middle |

- **Brightness**, **Speed**, and an **Overlay effect** (None, Lightning, Snow).
- **Action bar:**
  - **Cancel** discards your edits.
  - **Preview on lights** shows the colors and animation on your house without saving. Overlays only play once a pattern is saved.
  - **Save as new** creates a new pattern.
  - **Save changes** updates the open pattern.

### Effects: built-in animations
Search and preview the controller's 180 built-in effects, with brightness, speed, pixel length and direction.

### Library: all patterns at a glance
- **Pattern cards:** animated previews. Hover to see a pattern move, and click the preview to play it on your lights.
- **Card controls:** **+** adds a pattern to the **rotation** (up to 5). The dropdown sets its overlay. The buttons edit colors, rename or delete.
- **Rotation panel:** shows the order and when it plays. Change the minutes per pattern, then **Save**. Unsaved changes show a **Save rotation / Discard** bar.
- **Filters:** All, In rotation, Effects (lightning/snow), Scheduled.

### Schedule
- **Daily schedule 1 and 2:** on/off, repetition, pattern (or the rotation), start and off times.
- **Calendar events:** a pattern for a date range, such as a holiday week, up to 60 events.
- Schedules only run when power is set to **Schedule**.

### Device
- **Trimlight account:** shows the Client ID (last 4 characters only), whether the app is connected, and which controllers the account can see.
  - **Test connection:** signs in to Trimlight and reports what it found. Use it when lights stop loading, to tell a credentials problem from a cloud outage.
  - **Change credentials:** paste new ones, for example after Trimlight reissues them.
  - **Disconnect:** removes your Client ID and Secret from this computer and returns to the setup screen. Your lights, patterns and schedules aren't affected. Use it before giving away or sharing the computer.
- **Controller:** rename it, and see its status, now playing, firmware and patterns stored (max 60).
- **Clock:** the controller's clock with an in-sync badge, and **Sync clock**.
- **Cloud backup:**
  - **Back up now** replaces Trimlight's single saved backup.
  - **Restore** replaces all patterns and schedules, and asks you to type `RESTORE`.
- **Groups:** link two or more controllers.
- **Hardware setup (advanced):** color order, LED chip type, and pixel ranges for each port. Change these only if colors are wrong after installation.

### Good to know
- **Changes take a few seconds.** Saves wait until the controller confirms them, about 5–10 seconds.
- **Phone-app animations:** patterns made in the Trimlight phone app may use an animation outside the 17 above. It shows as "Mode N" and is kept unless you choose another.
- **"On" overrides schedules.** Playing or previewing a pattern switches the lights to **On**. Click **Schedule** to resume your schedules.

---

## Command-line tool

`trimlight.py` is a command-line client for the same API. It's useful for scripting.

```bash
python3 trimlight.py devices                      # list controllers
python3 trimlight.py device <deviceId>            # full details (patterns, schedules, ...)
python3 trimlight.py on|off|timer <deviceId>      # power: manual / off / schedule
python3 trimlight.py effect <deviceId> <id>       # play a saved pattern
python3 trimlight.py preview <deviceId> <mode>    # preview a built-in effect (0-179)
python3 trimlight.py solid <deviceId> "#FF0000"   # preview a solid color
python3 trimlight.py backup-info <deviceId>       # latest cloud backup
python3 trimlight.py raw POST /device/get '{"deviceId":"..."}'
python3 trimlight.py -h                           # all commands
```

On Windows, use `py -3` instead of `python3`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **Home page asks you to connect again** | The app didn't find `.env` in its folder. It may be named `.env.txt`, or you started a different copy of the app. Reconnect on the Home page, or see [Setting credentials by hand](#setting-credentials-by-hand-optional). |
| **"Trimlight didn't accept these credentials"** | Copy the Client ID and Secret again from Trimlight's credentials page, with no spaces. Make sure your computer's clock is right. |
| **`CERTIFICATE_VERIFY_FAILED`** (Mac) | Run **Install Certificates.command** from Applications → Python 3.x. Or set `TRIMLIGHT_CA_BUNDLE=/path/to/cacert.pem` in `.env`. |
| **`CERTIFICATE_VERIFY_FAILED`** (Windows) | Usually a company proxy or antivirus inspecting HTTPS. Ask IT for the proxy's certificate and set `TRIMLIGHT_CA_BUNDLE` to it in `.env`. |
| **"API error ..." on sign-in** | Check the Client ID and Secret for typos or extra spaces. Make sure your computer's clock is right, because requests are time-stamped. |
| **"Port 8765 is already in use"** | The app is probably already running, so open <http://localhost:8765>. Or start a second copy with `--port 8766`. |
| **`python` opens the Microsoft Store** (Windows) | Use `py -3`, or install Python from python.org with "Add to PATH" ticked. |
| **Double-clicking `start-mac.command` does nothing or is blocked** | Right-click → **Open**. If it opens in a text editor, run `chmod +x start-mac.command` in Terminal. |
| **Page says "Couldn't load … from Trimlight"** or error 12006 | Trimlight's cloud is briefly unavailable. Wait a minute and click **Retry** or ↻. |
| **A change doesn't show up** | Click ↻ in the header. The controller re-reports its data, which can take up to 30 seconds. |
| **"Trimlight backups need a US time zone"** | Trimlight's cloud only accepts US time zones for backups. Everything else works in any time zone. |
| **Page opened from a file shows a warning** | Don't open `static/index.html` directly. Start the app and use <http://localhost:8765>. |

Still stuck? Go to **Device → Trimlight account → Test connection**, or run the [self-check](#check-your-setup) and look for the first `FAIL` line.

---

## Testing

**Offline tests** need no internet and no credentials, and never touch a controller. They cover sign-in tokens against the spec's example, `.env` files saved by Notepad (BOM + CRLF), Windows time-zone names, and the local server's security checks.

```bash
python3 -m unittest discover tests        # Mac
py -3 -m unittest discover tests          # Windows
```

**Setup check:** confirms a real connection to Trimlight using your credentials. It's read-only.

```bash
python3 webapp.py --check
```

Supported screen sizes run from a 320 px phone to large desktop monitors, in light and dark mode.

---

## Files

| File | Purpose |
|---|---|
| `webapp.py` | The local web server (start this) |
| `trimlight.py` | Trimlight API client and command-line tool |
| `static/index.html` | The app's page (HTML, CSS and JavaScript in one file) |
| `start-mac.command` | Double-click launcher for macOS |
| `start-windows.bat` | Double-click launcher for Windows |
| `.env.example` | Template for setting credentials by hand |
| `.env` | Your credentials, created by the Home page setup (private; ignored by Git) |
| `tests/test_offline.py` | Offline tests |
| `LICENSE` | MIT license |
| `CONTRIBUTING.md` · `SECURITY.md` | How to contribute; how to report security problems privately |
| `.github/` | Issue and pull-request templates, and the automatic test workflow |
| `docs/API-NOTES.md` | Behaviors of the Trimlight API learned while building this |
| `festivals.json` | Your festival labels, created when you first use them (ignored by Git) |
| `snapshots/` | Optional local copies of controller data (ignored by Git) |

---

## Security

- **Local only.** The server listens only on `127.0.0.1`, so other computers and phones can't reach it.
- **Host check.** It ignores requests addressed to any other host name, which blocks DNS-rebinding attacks.
- **Request check.** Every change must carry a custom header, so other websites you visit can't send commands to it.
- **Secret stays on disk.** The Client Secret stays in `.env` on your computer (readable only by your user on Mac/Linux). It goes from the setup form to the local server once and is never sent back to the browser.
- **Password stays with Trimlight.** You type your Trimlight password only on Trimlight's own credentials page, never in this app.
- **Keep `.env` private.** Don't email it or put it in shared folders. If it leaks, get new credentials from Trimlight's credentials page and use **Change credentials**.
- **Remove them when you're done.** **Device → Trimlight account → Disconnect** deletes the credentials from `.env`. Other settings in the file stay. If you set `TRIMLIGHT_CLIENT_ID` / `TRIMLIGHT_CLIENT_SECRET` as system environment variables instead, remove them there too.

---

## Disclaimer

This is an independent, open-source project. It isn't made, endorsed or supported by Trimlight. It uses Trimlight's public Edge API. "Trimlight" and "Trimlight Edge" are trademarks of their owner. Use it at your own risk; your controller and Trimlight account remain subject to Trimlight's terms.

---

## Contributing

Bug reports, fixes and ideas are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules:
- standard library only;
- local-only server;
- credentials go only to Trimlight.

Every pull request is tested automatically on Windows, macOS and Linux.

Found a security problem? Please report it privately; see [SECURITY.md](SECURITY.md).

---

## License

[MIT](LICENSE) © 2026 Nitin Kotian. You're free to use, copy, modify and share this project, including commercially, as long as the copyright and license notice are kept. Contributions are accepted under the same license.
