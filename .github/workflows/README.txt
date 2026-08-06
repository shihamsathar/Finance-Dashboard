LEDGER & COMMISSION — FINANCE DASHBOARD (Web Application)
AL SHAHEEN GROUPS — General Services
Software by O2 Nexus Global — otngqa@gmail.com
============================================================

BUILD VERSION: 2026-08-05.2
-----------------------------
This exact version number is printed at the bottom of the sign-in
screen and in the app's sidebar once you're logged in. After you
deploy, look for "Build 2026-08-05.2" in the app itself — if you see
it, you are 100% looking at this version. If you see an older build
number (or none at all), your deploy did not actually go live yet —
see the troubleshooting section at the end of this file.


WHAT THIS IS
------------
A real multi-user web app for AL SHAHEEN GROUPS. One Flask server +
one SQL database, reachable at a single web address. Every admin and
user signs in from their own browser, on any computer, anywhere with
internet. Everyone sees the same live data; changes appear for
everyone within a few seconds automatically.

EVERYTHING IN THIS BUILD (tested, 27/27 automated checks passing
before this was packaged):
  - Admin / User roles with hashed passwords (real security)
  - Orders with multiple payments per company ("1st payment",
    "2nd payment", etc.), auto-calculated remaining balance
  - Commission % — global default, per-user override, AND
    admin can edit the % on any individual order directly
  - Services / categories manager ("+ Add Service")
  - Comments on every order
  - WhatsApp / Email quick-action buttons per order (admin view)
  - Search by company name and category
  - Daily Income tile (today's collections, company-wide)
  - "This Month" — its own sidebar tab: 4 summary tiles, a
    per-user monthly breakdown, and every transaction for the
    current month. Automatically reads zero on day 1 of a new
    month and builds back up — nothing to reset by hand.
  - "Monthly Description" — a separate sidebar tab: Records,
    Total Amount, Amount in Advance (each order's 1st payment),
    Cash In (everything collected this month), and Balance —
    company-wide and broken down per user. Same automatic
    month-to-month reset, nothing to do by hand.
  - "More Tools" quick-link buttons for future platforms
    (invoice system, profit & loss, anything else)
  - AL SHAHEEN GROUPS branding and logo throughout
  - Admin backup export (downloads a JSON snapshot)
  - Password-protected reset tool (see below)
  - Works with SQLite (zero setup) or real PostgreSQL
    (set DATABASE_URL) — same code, either way


FILES IN THIS PACKAGE — ALL OF THEM GO IN YOUR REPO'S ROOT FOLDER
---------------------------------------------------------------------
  app.py             Flask server: routes, database, auth
  dashboard.html      the dashboard interface, served by app.py
  logo.png             your AL SHAHEEN GROUPS logo, served by app.py
  requirements.txt    Python packages needed
  Procfile            tells the host how to start the app
  render.yaml          one-file deployment blueprint for Render.com

IMPORTANT: all six files must sit directly in the main/root folder
of your GitHub repository — NOT inside a subfolder like
"web-app-package" or "ledger-web-app-package". If GitHub's upload
tool created a subfolder when you dragged files in before, that is
very likely why your changes weren't showing: Render looks for
app.py at the repo root, and if it's actually sitting one folder
deeper, Render either fails to build or keeps running an old cached
version. When you upload this time, drag the FILES themselves (not
the folder they came in) into the GitHub upload box.


HOW TO DEPLOY (FROM SCRATCH OR TO REPLACE WHAT'S THERE)
------------------------------------------------------------
1. Open your GitHub repository in a browser.
2. If old versions of these files already exist there, open each
   one and use the pencil/edit icon, or delete and re-add — either
   way, make sure the final result is these exact 6 files sitting
   at the repo's root.
3. Use "Add file" -> "Upload files", and drag in app.py,
   dashboard.html, logo.png, requirements.txt, Procfile, and
   render.yaml directly (not a folder containing them).
4. Scroll down and click "Commit changes".
5. Go to https://dashboard.render.com -> your web service.
6. Check the "Events" (or "Deploys") tab — a new deploy should start
   within a few seconds of your GitHub commit. If it doesn't start
   within a minute or two, click "Manual Deploy" -> "Deploy latest
   commit" yourself.
7. Wait for it to say "Live" (green).
8. Open your app's URL. Hard-refresh with Ctrl+Shift+R (Windows) or
   Cmd+Shift+R (Mac) to bypass any cached old page.
9. Look at the bottom of the sign-in screen: it should say
   "Build 2026-08-05.2". If it does, you are fully up to date.


RESETTING TO A FRESH ADMIN SETUP
-----------------------------------
1. In Render -> your web service -> Environment tab, add:
     Key: RESET_SECRET       Value: (anything you choose)
2. Save — Render redeploys automatically.
3. Visit: https://your-app.onrender.com/api/dev-reset?key=YOURVALUE
4. You'll see a confirmation message. Go to your app's normal URL —
   it will show "Create Admin Account" again, exactly like new.
5. Afterward, delete the RESET_SECRET variable so this can't be
   triggered again by anyone who finds the URL.


TROUBLESHOOTING "MY CHANGES AREN'T SHOWING"
-----------------------------------------------
Check these in order:

1. Open dashboard.html directly on GitHub (click it in your repo)
   and Ctrl+F / Cmd+F search for: Build 2026-08-05.2
   - Not found? The file wasn't actually uploaded/committed to the
     repo root. Re-upload it (see step 3 above).

2. On Render, check the "Events" tab for a deploy matching the time
   you committed. No matching entry? Auto-Deploy may be off, or the
   GitHub connection isn't linked — use "Manual Deploy" to trigger
   one yourself.

3. If a deploy ran and shows "Failed" (red), click into it, scroll
   to the error near the bottom of the build log, and send me that
   exact text — I'll fix the precise cause.

4. If it shows "Live" (green) but the site still looks old, hard-
   refresh (Ctrl+Shift+R / Cmd+Shift+R) or open the URL in a private/
   incognito window — this rules out a stale cached page.

5. Once loaded, check the build number at the bottom of the sign-in
   screen. If it says "Build 2026-08-05.2", everything worked.


DATABASE NOTES
-----------------
Uses SQLite automatically — no setup needed. For a real managed
PostgreSQL database instead, deploy via render.yaml (provisions one
automatically and links it via DATABASE_URL), or set that variable
yourself pointing at any Postgres database.

A NOTE ON HTTPS
-----------------
Render gives you HTTPS automatically. Don't run this behind plain
HTTP on the open internet — real passwords are sent over that
connection.

STILL STUCK?
------------
Send me the exact error text or exact screenshot description (e.g.
"Events tab shows nothing after I commit", "build log says X") and
I'll diagnose the specific cause rather than guess.
