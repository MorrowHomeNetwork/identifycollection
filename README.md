# IdentifyCollection

**Somebody knows who this is.** IdentifyCollection puts a museum's
unidentified photographs in front of the people who might recognize them,
and lets the museum's own staff decide what joins the record.

Small history museums hold thousands of photographs of people nobody on staff
can name. The people who *can* name them are visitors, families and local
residents, and they are not getting younger. IdentifyCollection is a
moderated crowdsourcing tool for that cataloging backlog: a visitor marks a
face in a photograph, says who it is and how they know, and a collections
manager reviews the evidence and approves or declines it. Approved
identifications are exported back to the museum's catalog.

> ## Status: scaffolding only (version 0.0.1)
>
> **This version cannot import or identify anything yet.** It is "Step 0":
> a skeleton with a sign-in page, built to prove that the software can be
> delivered to a museum as a single zip file that starts with a double-click
> on a Windows computer, with nothing installed and no internet connection.
> The first build a museum can do real work with will be 0.1.0.

## What it will do

The first working version (phase 1) is planned to cover one complete loop:

1. **Import** a catalog export and a folder of scans.
2. **Show** the unidentified photographs in a gallery with deep zoom.
3. **Collect** identifications: a visitor draws a box around a person, names
   them, and attaches evidence (a document, a cross-reference, or their own
   testimony). No visitor account is needed.
4. **Moderate**: a collections manager approves, declines, or later
   withdraws each submission.
5. **Export** the approved identifications for the museum's catalog.

Later phases add a kiosk mode and QR codes for the gallery floor, a permanent
server install, a public reading app, and (last, and only as suggestions for
a human to check) automated similarity hints.

## Principles

These are fixed. They are why the tool is built the way it is.

- **The museum is in charge.** Nothing becomes public, and nothing enters the
  catalog, without a human collections manager's approval.
- **Each museum runs its own copy.** There is no central service, no account
  with us, and no data leaving the building unless the museum sends it.
- **It works offline.** Every font, script and style is inside the download.
  Nothing is fetched from the internet while it runs.
- **Visitors do not need accounts.** Helping should take a minute.
- **Nothing accepted is ever silently destroyed.** Withdrawn identifications
  are retired with a record of who, when and why. A contributor's personal
  details can be removed on request.
- **No leaderboards.** Recognition, yes; competition over the dead, no.
- **Face-matching software comes last, if at all,** and only ever as a
  suggestion that a person must confirm.

## Try the test build (Windows)

1. Open the [Releases page](https://github.com/MorrowHomeNetwork/identifycollection/releases)
   and download `IdentifyCollection-<version>-windows-x64.zip`.
2. Right-click the zip, choose **Extract All...**, and open the folder that
   creates.
3. Double-click **Start IdentifyCollection**.

A black window opens, then your web browser opens on IdentifyCollection. It
asks you to create the first staff account. To stop, close the black window.

Needs Windows 10 or 11 (64-bit). Nothing is installed. Everything it stores
goes into a `data` folder next to the program; to remove IdentifyCollection,
delete the folder. `READ ME FIRST.txt` inside the zip covers Windows warnings,
backups and updating.

## Working on the code

You need [Python](https://www.python.org/downloads/) 3.12 or newer and
[Git](https://git-scm.com/downloads). The commands below create a "virtual
environment" (a private set of Python packages for this project, so it cannot
disturb anything else on the computer).

**Windows (PowerShell)**

```powershell
git clone https://github.com/MorrowHomeNetwork/identifycollection.git
cd identifycollection
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements.txt
cd app
python manage.py test
python manage.py migrate
python manage.py runserver
```

**Linux or macOS**

```bash
git clone https://github.com/MorrowHomeNetwork/identifycollection.git
cd identifycollection
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
cd app
python manage.py test
python manage.py migrate
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>. Stop the server with Ctrl+C.

- `python manage.py test` runs the automated tests. All of them should pass
  before any change is committed.
- `python manage.py migrate` creates or updates the development database, in
  a `data` folder at the top of the repository (never committed).
- `python manage.py runserver` starts a development web server that only
  your own computer can reach.

### Opening it from another computer on your network

The development server normally answers only on the computer it runs on. To
run it on one machine (a spare PC, a virtual machine) and open it from
others on the same home or museum network, tell it which address people
will type, and let it listen on the network:

```bash
cd app
IDENTIFYCOLLECTION_EXTRA_HOSTS=192.168.1.20 python manage.py runserver 0.0.0.0:8000
```

Replace `192.168.1.20` with that machine's own address, then open
`http://192.168.1.20:8000/` from another computer. This is a development
server: it shows technical details when something goes wrong and must never
be reachable from the internet.

### Building the Windows zip

From the top of the repository, on Windows, Linux or macOS:

```bash
python packaging/build_portable.py
python packaging/smoke_test.py dist/IdentifyCollection-0.0.1-windows-x64.zip
```

The first command assembles the zip in `dist/`. The second extracts it into
a scratch folder, starts it, creates an account, signs in and out, restarts
it and checks that nothing was lost. On Windows the smoke test goes through
the real batch file and the Python inside the zip; elsewhere it checks the
app with your own Python (add `--runner wine` on Linux to rehearse the
Windows path through Wine).

Every push to GitHub runs the tests, the build and the smoke test on a real
Windows machine automatically. See [docs/RELEASING.md](docs/RELEASING.md) for
how a version is published.

## What is where

| Path | What it is |
|---|---|
| `app/` | Everything that ships: the Django project (`config/`), its parts (`accounts/`, `core/`), page templates, the stylesheet and fonts, and `launch.py`, the program behind the double-click |
| `app/VERSION` | The version number. The one place it is written down |
| `packaging/` | The scripts that build and smoke-test the Windows zip, the pinned Python runtime, and the files Windows users see |
| `.github/workflows/build.yml` | The automated build that GitHub runs on every push |
| `docs/DECISIONS.md` | What was decided, and why |
| `docs/GLOSSARY.md` | Plain-language meanings of the technical terms used here |
| `docs/RELEASING.md` | How to publish a version, step by step |
| `docs/SESSION_LOG.md` | What each working session delivered |
| `requirements.txt` | The exact Python packages used, with checksums |
| `CHANGELOG.md` | What changed in each version, for the people who use it |
| `THIRD-PARTY-NOTICES.md` | The open-source software this is built on, with licences |

## Licence

Copyright (C) 2026 MorrowHomeNetwork and IdentifyCollection contributors.

IdentifyCollection is free software: you can redistribute it and/or modify it
under the terms of the GNU Affero General Public License, version 3, as
published by the Free Software Foundation. It is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE)
for the full text.

In short: any museum may use, copy and change it freely. Anyone who changes
it and offers the changed version to others, including over a network, must
make their changes available under the same licence.

The software it is built on is listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
