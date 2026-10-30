# Security policy

Trimlight Control handles Trimlight API credentials (a Client ID and Client Secret) that can control someone's lights. Security reports are taken seriously.

## Reporting a vulnerability

**Please don't open a public issue for security problems.**

Report them privately through GitHub:
1. Go to this repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the problem, how to reproduce it, and what an attacker could do.

You'll get a reply as soon as possible. This is a spare-time project, so allow a few days. Please give a reasonable amount of time for a fix before disclosing publicly.

## What counts as a security issue

Examples:
- **Secret leaks:** the Client Secret is logged, shown in the page, put in a URL, or sent anywhere other than Trimlight's API.
- **Remote reach:** a page on another website (or another device on the network) can read data from the local app or send it commands, for example by getting around the `Host` check or the `X-Trimlight-App` header.
- **Server exposure:** the local server becomes reachable from other computers.
- **Unsafe files:** `.env` is created with permissions that let other users on the computer read it (Mac/Linux).
- **Supply chain:** something in the repository downloads or runs code from the internet.

Not security issues (please use a normal issue):
- Problems with Trimlight's own cloud service or phone app. Report those to Trimlight.
- Someone with access to your logged-in computer being able to read `.env`. That's expected for a local app, the same as any saved password file.

## If your credentials leak

If your Client Secret was exposed, for example committed to a public repository or shared by mistake:
1. Get new credentials from Trimlight's credentials page: <https://trimlight.ledhue.com/trimlight/v1/api-credentials/apply>
2. In the app, go to **Device → Trimlight account → Change credentials** and paste the new ones.
3. If the old secret is in a Git history, removing the file isn't enough; treat it as public and replace it.

## Supported versions

Only the latest version on the `main` branch gets security fixes.
