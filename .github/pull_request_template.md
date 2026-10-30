## What does this change?
<!-- One or two sentences. Link the issue it fixes, e.g. "Fixes #12". -->

## How did you test it?
<!-- Offline tests, and anything you checked by hand. Which OS and browser? Did you try it on a real controller? -->

## Checklist
- [ ] `python3 -m unittest discover tests` passes (Windows: `py -3 -m unittest discover tests`)
- [ ] No new third-party dependencies, outside hosts, CDNs or analytics
- [ ] Credentials are still sent only to Trimlight's API and are never logged, shown or returned to the page
- [ ] The server still listens only on `127.0.0.1` with the Host and `X-Trimlight-App` checks unchanged
- [ ] Anything that changes the controller is behind a clear action (with a confirmation if destructive)
- [ ] Works on Windows and macOS, or I've noted what I couldn't test
- [ ] README / `docs/API-NOTES.md` updated if behavior changed
- [ ] No personal data in the diff (`.env`, controller IDs, your own pattern names)

By submitting this pull request, I agree that my contribution is licensed under the project's MIT License.
