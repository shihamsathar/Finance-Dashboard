LEDGER & COMMISSION — FINANCE DASHBOARD (Web Application)
Software by O2 Nexus Global — otngqa@gmail.com
============================================================

WHAT THIS IS
------------
A real multi-user web app. One Flask server + one SQL database,
reachable at a single web address. Every admin and user signs in
from their own browser, on any computer, anywhere with internet —
no LAN, no synced folders, no per-computer data files. Everyone
sees the same live data, and changes appear for everyone within
about 5 seconds automatically (there's also a "Sync Now" button
for an instant refresh).

DATABASE: SQLITE BY DEFAULT, REAL POSTGRESQL IF YOU WANT IT
---------------------------------------------------------------
This now supports two SQL databases with the exact same code:
  - SQLite (default) — a single .db file, zero setup, works the
    moment you run it.
  - PostgreSQL — a real client-server SQL database. Just set an
    environment variable called DATABASE_URL to a Postgres
    connection string and the app automatically switches to it —
    same tables, same queries, nothing else to change.
The included render.yaml sets this up for you automatically (see
Option A below): it provisions a real managed Postgres database and
points the app at it, so you get a proper SQL database with zero
manual configuration.

WHAT I TESTED MYSELF BEFORE SENDING THIS
-------------------------------------------
I ran this app for real, end to end, in my own environment before
handing it to you:
  - created the admin account
  - added a user and set their commission %
  - tried adding a duplicate username and a duplicate service, and
    confirmed both are correctly rejected with a clear error instead
    of crashing
  - logged in as that user, created an order, added a 2nd payment,
    checked the running balance and commission calculated correctly
  - confirmed a regular user gets blocked (403) from admin-only
    routes, and that a signed-out request gets rejected (401)
  - logged in as admin and confirmed they can see that user's order
  - downloaded the admin backup export and confirmed it contains
    everything correctly

One honest limitation: I don't have a live PostgreSQL server in my
own environment to test against, so the Postgres code path is
carefully written and reviewed line by line, but not run live the
way the SQLite path was. The two paths share the exact same route
logic, table schema, and queries — only the low-level database
driver differs — so risk is low, but I'd rather tell you this than
imply I tested something I couldn't. Do one quick pass after you
deploy (create the admin account, add an order) and let me know if
anything looks off — I'll fix it immediately.


FILES IN THIS PACKAGE
----------------------
  app.py            Flask server: routes, database, auth
  dashboard.html     the dashboard interface, served by app.py
  requirements.txt   Python packages needed (includes the Postgres driver)
  Procfile           tells the host how to start the app
  render.yaml         one-file deployment blueprint for Render.com,
                      including a real managed Postgres database


OPTION A — DEPLOY ON RENDER.COM WITH REAL POSTGRESQL (recommended)
----------------------------------------------------------------------
1. Put all the files in this package into a GitHub repository
   (github.com — free account, "New repository", then "Add file"
   -> "Upload files", drag everything in, commit).
2. Go to https://render.com, sign up (free), then "New +" ->
   "Blueprint". Connect your GitHub account and pick the repo you
   just made. Render reads render.yaml automatically and provisions
   both a web service AND a real Postgres database, and wires them
   together via the DATABASE_URL environment variable — no manual
   setup needed.
3. Click "Apply". Wait a few minutes for the first deploy.
4. You'll get a URL like https://ledger-finance-dashboard.onrender.com
   — that's your live web app, backed by a real PostgreSQL database.
   Open it, create the admin account, and you're running.

A CAVEAT WORTH KNOWING: Render's free Postgres databases are free
for 30 days, after which Render asks you to upgrade to a paid plan
(a few dollars a month) to keep the data. If you want the database
to be permanent from day one without that 30-day clock, change
"plan: free" under "databases" in render.yaml to "plan: basic-256mb"
before deploying (a few dollars a month from the start).

Render's free WEB service tier (the app itself, not the database)
also "sleeps" after 15 minutes of no visits, causing the first
request after that to take 30-60 seconds to wake up — normal
free-tier behavior, not a bug.


OPTION B — DEPLOY FREE ON PYTHONANYWHERE (SQLite, no Postgres needed)
-------------------------------------------------------------------------
If you'd rather not touch Postgres at all, PythonAnywhere's free
tier works well with the default SQLite database — genuinely free,
persistent storage included.

1. Go to https://www.pythonanywhere.com and create a free "Beginner"
   account.
2. Open a Bash console from your dashboard. Upload app.py and
   dashboard.html into your home folder (the Files tab has an
   upload button).
3. In the console: pip3.10 install --user Flask Werkzeug
4. Go to the "Web" tab -> "Add a new web app" -> choose "Flask" ->
   point it at app.py in your uploaded folder.
5. Click the green "Reload" button on the Web tab. Your app is now
   live at https://your-username.pythonanywhere.com, using SQLite —
   no DATABASE_URL needed, it just works.


AFTER IT'S DEPLOYED (either option)
--------------------------------------
Visit your app's URL. First time, you'll be asked to create the
admin account — same flow as before. From then on, everyone signs
in from that same URL, on any device, anywhere with internet.

Use the "Sync Now" button any time for an instant refresh; the app
also quietly checks for updates every few seconds on its own.

A NOTE ON HTTPS
-----------------
Both Render and PythonAnywhere give you HTTPS automatically (the
padlock in the browser) — important since real passwords are being
sent over the connection. Don't deploy this behind plain HTTP on the
open internet.

STILL STUCK?
------------
Tell me the exact error message or what happened (e.g. "Render build
failed with X", "the app shows a 500 error after I set DATABASE_URL")
and I'll fix the actual cause rather than guess.
