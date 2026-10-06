# Decisions

What was decided, and why, in the order it was decided. When a decision is
changed, it is not erased: a new entry is added that says what replaced it.

Technical terms are explained in [GLOSSARY.md](GLOSSARY.md).

## Part 1: The shape of the project

These came from the planning phase, before any code was written.

### 1. One application, rendered on the server, with no build step for the interface

IdentifyCollection is a single Django application. Pages are assembled on the
server and sent to the browser as ordinary HTML. There is no separate
"front-end" project and no step that compiles the interface.

*Why:* one thing to install, one thing to understand, one thing to back up.
The people who will maintain a museum's copy are volunteers and
generalists, not web specialists.

### 2. Every library is stored with the project. Nothing is loaded from the internet

Fonts, scripts and styles live in this repository (this is called
"vendoring"). The app never fetches anything from a CDN, which is somebody
else's server that many websites borrow files from.

*Why:* it must work on a museum laptop with no connection, it must keep
working when some third-party server changes or disappears, and a visitor's
browser must not be reported to a third party just because they looked at a
photograph. An automated test (`app/tests/test_offline.py`) fails if this is
ever broken.

### 3. SQLite for the portable build, PostgreSQL for permanent installs

SQLite keeps the whole database in one file, which is what makes "the app and
its data are one folder" possible. Permanent server installs (phase 3) will
be able to use PostgreSQL instead, chosen by configuration.

### 4. Images: deep zoom with OpenSeadragon, marking with Annotorious, in the W3C Web Annotation format

A visitor zooms into a scan and draws a box around a person. The box is
stored in a published, open standard so that other tools can read it.
Smaller versions of large scans ("derivatives") are made with libvips.
*(Not built yet; arrives in phase 1.)*

### 5. Import from PastPerfect and from generic CSV; export approved identifications

The importer for PastPerfect exports will be written against a real export
file from the pilot museum. **The format is never guessed or invented.** A
generic CSV column-mapper covers everything else. Approved identifications,
and later withdrawals of them, are exported for the museum's catalog.
*(Not built yet; arrives in phase 1.)*

### 6. The record of what happened is permanent

Approving an identification creates an accession event. Withdrawing one
creates a deaccession event with who, when and why. Withdrawn material is
retired, not deleted, and a withdrawal can itself be reversed. The one
exception is a contributor's personal details, which can be purged on
request. Nothing is public and nothing reaches the catalog without a human
collections manager's approval.

### 7. Things this project will not do

- No central service that museums depend on.
- No account wall for visitors.
- No leaderboards. Light acknowledgement only.
- No face recognition before phase 5, and then only as suggestions a person
  must confirm.
- No feature work while the current drop is not committed, pushed and
  releasable.

### 8. Phases

| Phase | What it delivers |
|---|---|
| Step 0 | The delivery pipeline: a zip that starts with a double-click (this version) |
| 1 | Portable test build: import, gallery with zoom and marking, submissions with evidence, moderation, export |
| 2 | Kiosk mode, QR codes, acknowledgement, email digests, a hosted test installation |
| 3 | Permanent installs: Docker, PostgreSQL, feed standard, install documentation |
| 4 | A public reading app |
| 5 | Suggestion engines (optional, human-confirmed) |

## Part 2: Step 0 decisions (2026-10-01)

### 9. Licence: GNU AGPL, version 3

Anyone may use, copy and change IdentifyCollection. Anyone who changes it and
offers the changed version to others, including as a hosted service, must
share those changes under the same licence.

*Why:* improvements made for one museum stay available to all museums, and
nobody can turn the project into a closed product.
*Cost:* some institutions' lawyers are cautious about the AGPL. *Reversible?*
Easily, for as long as there is a single copyright holder; harder once
outside contributions are accepted.

### 10. The portable Python: python-build-standalone, pinned by checksum

The zip carries a complete copy of Python for Windows (currently 3.14.7) from
the python-build-standalone project. The exact file and its checksum are
recorded in `packaging/python-runtime.json`, and the build refuses any file
that does not match.

*Why this one:* it is a normal, complete Python that needs no installation,
and the same file can be rehearsed on Linux through Wine, so the Windows path
is tested before every hand-over.
*Known weakness:* its program files are not digitally signed, so Windows may
ask for confirmation on first run, and a strict security policy could refuse
it. *Fallback if that happens on a real museum laptop:* switch to python.org's
"embeddable package", which is signed by the Python Software Foundation.
Only `packaging/` would change.

### 11. The bundled Python is sealed off from the rest of the computer

A file named `python314._pth` inside `runtime/` tells that Python to load
code only from inside the bundle. It ignores any other Python on the
computer, the Windows registry and environment variables.

*Why:* one museum's laptop must not behave differently from another's because
of something already installed on it.

### 12. One folder holds everything a museum creates

Database, uploaded files, logs, safety copies and the installation's secret
key all live in `data/`, next to the program. Back up that folder and
everything is backed up. Updating means extracting the new version and moving
`data/` across.

### 13. The launcher protects the data before anything else

`app/launch.py` is the program behind the double-click. Its rules:

- **Only this computer can connect.** It listens on the address `127.0.0.1`,
  which cannot be reached from the network. Nothing is exposed, and Windows
  has no reason to show a firewall question.
- **One copy at a time.** A second double-click finds the copy already
  running and just opens the browser on it. This uses a lock that the
  operating system releases by itself if the program dies, so a crash cannot
  leave the folder stuck.
- **A safety copy before every upgrade.** If a new version needs to change
  the database layout, the database is first copied to `data/backups/`.
- **Never run old code on newer data.** If the data folder was last used by a
  newer version, the launcher stops and says so, changing nothing.
- **Plain words on screen, details in a file.** Problems are explained in the
  launcher window in ordinary language; technical details go to
  `data/logs/`.

### 14. The first staff account is created in the browser

A fresh copy has no accounts. The first visit shows a "create the first staff
account" page; that account can do everything. The page stops working for
good the moment one account exists.

*Why:* the alternative is asking a registrar to type a command.
*Safe because:* the portable build is reachable only from the computer it
runs on. Server installs (phase 3) will be able to switch this page off
(`ALLOW_WEB_SETUP`).

### 15. Our own account model from day one

`accounts.User` extends Django's standard account without adding anything
yet. *Why:* Django makes it painful to change the account model after a
database exists, and cheap to start with your own.

### 16. Version numbers and releases

- The version is written in exactly one place: `app/VERSION`.
- `0.0.x` are scaffolding and test drops. `0.1.0` is the end of phase 1.
  After that, each phase raises the middle number.
- A release is published by pushing a tag named `v` + the version. The
  automated build checks that the tag and `app/VERSION` agree.
- Versions below `0.1.0`, and anything with a hyphen (`0.2.0-rc1`), are
  published as "pre-releases".
- **Order matters:** push `main`, wait for the build to pass, then tag.
  A tag pushed onto a failing build publishes nothing.

### 17. Every dependency is pinned and checksummed

`requirements.txt` gives the exact version and checksum of every package. The
installer refuses anything else. All current dependencies are "pure Python",
so the same files work on every operating system.

### 18. Tested three ways

1. **Automated tests** (`python manage.py test`): accounts, pages, the
   launcher's safety rules, the no-internet guard, release housekeeping.
2. **Smoke test** (`packaging/smoke_test.py`): takes the finished zip,
   extracts it into a folder with an awkward name, starts it through the real
   batch file, and walks the whole first-run journey.
3. **On real Windows**, automatically, on every push to GitHub.

### 19. Interface

Hand-written CSS, no framework. Colours from the collection store: grey
archival board, white photographic paper, cyanotype blue, pencil graphite,
and one yellow marking box. Yellow is reserved for the marking box and for
showing keyboard focus. Typefaces: Besley for headings, Atkinson Hyperlegible
Next (designed for low-vision readers) for everything else; both are stored
in the repository under the SIL Open Font License.

### 20. Privacy in the repository

The public repository contains no names or personal details of the people
behind the pilot. They appear as "the pilot museum" and "the pilot
registrar".

### 21. Answering on a network is opt-in, by exact address (2026-10-05)

By default the app answers only on the computer it runs on. A copy meant to
be opened from other computers must be given the exact names or addresses to
answer on (`IDENTIFYCOLLECTION_EXTRA_HOSTS`). "Answer on anything" (`*`) is
refused.

*Why:* developing on a separate machine needs it, and so will kiosk and
server installs. Exact addresses keep the protection against a hostile web
page reaching the app under a made-up name. The portable Windows build does
not use the setting.

## Part 3: Phase 1 decisions (2026-10-06)

### 22. Pictures are made with Pillow for now, not libvips

Decision 4 named libvips for making browser-sized copies of scans. This
version uses Pillow instead.

*Why:* Pillow installs as one ordinary, checksum-pinned package on Windows
and Linux, and it is proven inside the portable zip by the smoke test.
libvips would add a large set of extra Windows program files to the zip for
no benefit at the sizes small museums scan at.
*Cost:* a scan is read into memory whole, so a truly enormous file (hundreds
of megapixels) is slow. *Reversible?* Yes. All picture-making is in one
file, `app/mysteries/images.py`. libvips remains the plan for server
installs if speed ever matters.

### 23. The marking tool is our own small script, not Annotorious

Decision 4 named Annotorious for drawing the box around a person. This
version uses about 150 lines of our own JavaScript on top of OpenSeadragon.

*Why:* one box per answer is all that is needed, and a small tool we wrote
can be worded and shaped for a first-time visitor on a kiosk or a phone.
*What was kept from decision 4:* the standard. Every box is stored as
fractions of the picture and exported in W3C Web Annotation notation, so
Annotorious or any other standard tool can be adopted later without touching
stored data.

### 24. Original scan files are not copied in

IdentifyCollection keeps a zoomable JPEG of each scan (4000 pixels on the
long side) and a thumbnail, plus the original's file name, size, dimensions
and fingerprint. It does not keep the original file.

*Why:* the museum already has its masters, and the data folder has to stay
small enough to back up easily and carry on a USB stick. Marked areas are
exported in pixels of the original scan, so nothing is lost by this.

### 25. The front page belongs to visitors

The site's front page is the public gallery. Staff pages live under
`/staff/` and require a staff sign-in. A photograph is visible to visitors
only after staff put it on show, and a name only after staff accept it.

### 26. Practice photographs are drawings, and removable

The built-in practice set is drawn by the program (plain silhouettes), so no
real person and nobody's copyrighted photograph ships with the software.
Practice material is flagged as such and is the only thing that can be
deleted outright, together with anything sent in about it.

### 27. One piece of evidence per answer, of three kinds

Personal knowledge (with agreement that the museum may keep the account), an
attached document or photograph (with confirmation of the right to share
it), or a pointer to another record. Attached files are stored under random
names and can be opened by staff only.

## Deferred on purpose

Not forgotten; each waits for the phase where it matters.

| Item | When |
|---|---|
| A way to reset a forgotten password in the portable build | Phase 1 |
| Importing a catalog file: PastPerfect (needs a real export file first) and generic CSV with column matching | Next in phase 1 |
| Limiting how fast one visitor can send answers | Before any install reachable from the internet |
| Deep-zoom tiles for scans larger than 4000 pixels | If visitors need to zoom further |
| Limiting repeated wrong-password attempts | Before any install reachable from a network (phase 2) |
| A Content-Security-Policy header (a browser-enforced version of the no-internet rule) | With the first JavaScript (phase 1) |
| Each museum's own time zone for displayed times | Phase 1 |
| Translations | When a museum asks |
| PostgreSQL | Phase 3 |
| Pre-compiling Python files in the zip, to shorten the first start | If the first start proves slow on real museum laptops |
| Code-signing the Windows files | If Windows warnings prove to be a real obstacle |
