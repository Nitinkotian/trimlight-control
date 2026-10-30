# Contributing to Trimlight Control

Thanks for helping. Bug reports, fixes, documentation and new features are all welcome. This is a spare-time project, so reviews may take a while.

By sending a pull request, you agree that your contribution is licensed under the project's [MIT License](LICENSE).

---

## Ground rules

These keep the app safe and easy to install. Pull requests that break them won't be merged.

1. **Credentials go only to Trimlight.**
   - The Client ID and Client Secret may be sent only to Trimlight's API host (`trimlight.ledhue.com`), and only inside the signed request headers.
   - Never log the secret, put it in a URL, store it outside `.env`, or return it to the browser.
2. **Local only.** The server binds to `127.0.0.1`, checks the `Host` header, and requires the `X-Trimlight-App` header on every POST. Don't loosen any of these. No remote-access or "listen on all interfaces" options.
3. **Standard library only.** No third-party Python packages, no build step and no `requirements.txt`. The app must run with a plain Python 3.7+ install on Windows, macOS and Linux.
4. **No outside services.** No analytics, telemetry, CDNs, web fonts, or calls to any host other than Trimlight's API. The page must work with only the local server.
5. **Never touch someone's controller by surprise.** Anything that changes the controller needs a clear button and, if it's destructive, a confirmation. This includes saving, deleting, restoring, hardware settings and power.
6. **Keep personal data out of the repo.** Never commit `.env`, `festivals.json`, `snapshots/`, or real device IDs, credentials or pattern names from your own account.

---

## Getting set up

1. Fork the repository and clone your fork.
2. Install Python 3.7 or newer. See [README › Install Python](README.md#install-python).
3. Start the app and connect your own Trimlight account on its Home page:
   ```bash
   python3 webapp.py          # Windows: py -3 webapp.py
   ```
4. Check your setup:
   ```bash
   python3 webapp.py --check
   ```

### Project layout
| File | What's in it |
|---|---|
| `trimlight.py` | Trimlight API client: request signing, endpoints, command-line tool |
| `webapp.py` | Local web server: routes, validation, `.env` and `festivals.json` handling |
| `static/index.html` | The whole web page: HTML, CSS and JavaScript in one file, no framework |
| `tests/test_offline.py` | Offline tests (no network, no credentials) |
| `docs/API-NOTES.md` | Trimlight API behaviors found by testing |

---

## Making changes

- **Match the existing style.** Same naming, comment density and structure as the code around your change. Python follows PEP 8 loosely; JavaScript is plain modern browser JavaScript with no build tools.
- **Keep pull requests focused.** One fix or feature per pull request is much easier to review.
- **Add or update tests** in `tests/test_offline.py` for server or API-client changes. Tests must run offline: use the `FakeClient` or `unittest.mock`, never a real controller or real credentials.
- **Document what you learn.** If you find an undocumented Trimlight API behavior, add it to `docs/API-NOTES.md`. User-facing changes belong in `README.md`.
- **Keep it cross-platform.**
  - **Paths:** use `os.path`.
  - **Text files:** open them with an explicit `encoding="utf-8"`.
  - **Windows details:** console output and file locking behave differently, so keep them in mind.
  - **Launchers:** `start-windows.bat` must keep CRLF line endings. `.gitattributes` handles this.
- **Check phone and desktop widths.** If you touch the page, check it at about 375 px and 1440 px wide, in light and dark mode, with no sideways scrolling.

### Running the tests
```bash
python3 -m unittest discover tests -v     # Windows: py -3 -m unittest discover tests -v
```
Every pull request runs these automatically on Windows, macOS and Linux.

### Testing against a real controller
The offline tests can't catch everything. If you test on your own lights:
- **Throwaway data:** use clearly named test patterns (for example `zz Test`) and delete them afterwards.
- **Back up first:** take a cloud backup or a local snapshot.
- **Avoid risky features:** don't test Restore, hardware settings or clock sync unless your change is about them.

---

## Pull request checklist

- [ ] `python3 -m unittest discover tests` passes
- [ ] No new third-party dependencies, outside hosts or CDNs
- [ ] Credentials are still sent only to Trimlight, and never logged or returned to the page
- [ ] Anything that changes the controller is behind a clear action (and a confirmation if destructive)
- [ ] Works on Windows and macOS (or explain what you couldn't test)
- [ ] README / `docs/API-NOTES.md` updated if behavior changed
- [ ] No personal data (`.env`, device IDs, your pattern names) in the diff

---

## Reporting bugs and ideas

- **Bugs:** open an issue with the **Bug report** form. Include the output of `python3 webapp.py --check`, with secrets removed.
- **Ideas:** use the **Feature request** form.
- **Security problems:** don't open a public issue. See [SECURITY.md](SECURITY.md).

## For the maintainer: review notes

Look extra carefully at pull requests that:
- add or change any URL, host name, `urllib`/`socket` usage, or `fetch(` call;
- touch `make_token`, `TrimlightClient.request`, `.env` reading or writing, or the `/api/setup` routes;
- change the server's bind address, `ALLOWED_HOSTS`, or the `X-Trimlight-App` check;
- add `<script src=…>`, `<link href=…>`, or anything else loaded from the internet.
