# Session log

What each working session delivered, newest first. One entry per session:
what changed, the state it left things in, what is still open, what comes
next. No personal details belong in this file.

## 2026-10-06: Phase 1, the working loop (version 0.0.2)

### What changed

- New part of the app, `mysteries/`: photographs, visitors' answers with
  evidence, review with a permanent history, and the export.
- The front page is now the public gallery; staff pages moved under `/staff/`.
- Two new ingredients: Pillow (reads scans) and OpenSeadragon (zooming),
  both stored or pinned, neither loaded from the internet.
- The smoke test now performs the whole acceptance loop against the built
  zip: scan in, put on show, visitor identifies someone with evidence, staff
  accept, export file out.
- Decisions 22 to 27 record where this departs from the original plan
  (Pillow instead of libvips, our own marking tool instead of Annotorious)
  and why.

### State at the end of the session

- 83 automated tests pass on Python 3.12 and 3.14.
- The loop was walked in a real browser engine, including dragging a box
  around a face, with no script errors.
- The Windows zip (about 28 MB) passes the extended smoke test under Wine
  with the real Windows Python and the Windows build of Pillow.
- Published so far: v0.0.1, built and smoke-tested by GitHub on real Windows.
- **Not yet proven:** this version on GitHub's Windows machine (it has not
  been pushed yet); anyone's double-click on a Windows desktop; the pages on
  a real phone or a touch-screen kiosk.

### Open issues

1. Catalog import is not built. PastPerfect import is blocked until a real
   export file is available; the format will not be guessed.
2. No limit on how fast answers can be sent (fine offline and on a home
   network; needed before the internet).
3. The practice photographs are crude drawings.
4. Carried over: unsigned Python in the zip, no password reset, synced
   folders (OneDrive) untested.

### Next

1. Apply this drop, push, and tag `v0.0.2` once the build is green.
2. Try it: on the test server, and from the zip on the pilot laptop.
3. Catalog import, starting with generic CSV.

## 2026-10-05: First push, first green build, reachable on a network

### What changed

- The project moved to its own virtual machine and was pushed to GitHub from
  there.
- New setting `IDENTIFYCOLLECTION_EXTRA_HOSTS` (decision 21), with four tests,
  so the development server can be opened from other computers on the same
  network.

### State at the end of the session

- **The automated build passed on GitHub on its first run** (1 minute 19
  seconds): tests, zip build and smoke test on a real Windows machine,
  through the real batch file. This closes the "never run on GitHub" item
  from the previous entry.
- 52 automated tests pass.
- Still not proven: a person's double-click on a Windows desktop, and what
  Windows SmartScreen, Smart App Control or antivirus software say about the
  unsigned Python.

### Next

1. Tag `v0.0.1` to publish the first release, and try it on the pilot laptop.
2. Collect the items listed under 2026-10-01 from the pilot registrar.
3. Phase 1, drop 1: catalog import.

## 2026-10-01: Step 0, the delivery pipeline

### What changed

Everything; this is the first commit.

- **Skeleton application** (`app/`): a Django project with a first-run page
  that creates the first staff account, sign-in and sign-out, a placeholder
  home page showing where the data is kept, a health-check address, and
  Django's data-inspection screens.
- **Launcher** (`app/launch.py`): the program behind the double-click.
  Listens on this computer only, allows one running copy per data folder,
  makes a safety copy of the database before any upgrade, refuses to run
  against data from a newer version, explains problems in plain words.
- **Interface**: one hand-written stylesheet and two open-licensed typefaces
  stored in the repository. Nothing is loaded from the internet.
- **Packaging** (`packaging/`): `build_portable.py` assembles the Windows zip
  from a pinned, checksum-verified Python runtime and pinned packages;
  `smoke_test.py` starts a built zip and walks the first-run journey;
  `release_notes.py` turns the changelog entry into the release description;
  the batch file and read-me that Windows users see.
- **Automated build** (`.github/workflows/build.yml`): tests, build and
  smoke test on Windows for every push; a GitHub Release for every version
  tag.
- **Documents**: README, changelog, third-party notices, decisions,
  glossary, releasing guide, this log. Licence: AGPL-3.0.

### State at the end of the session

- 47 automated tests pass (Linux, Python 3.12).
- The zip builds: about 21 MB, about 59 MB extracted.
- The smoke test passes on Linux two ways: with the host's own Python, and
  with the real Windows Python and the real batch file running under Wine.
- Under Wine the first start took about 7 seconds and later starts about 2.
- **Not yet proven:** a double-click on real Windows; how Windows
  SmartScreen, Smart App Control or antivirus software treat the unsigned
  Python; the GitHub workflow itself, which has been checked for mistakes
  with a linter and by running its commands by hand but has never run on
  GitHub.

### Open issues

1. **Unsigned Python runtime.** Windows may ask for confirmation, and a
   strict policy could refuse it. Fallback: python.org's signed embeddable
   package (see decision 10).
2. **Synced folders.** If the folder is extracted somewhere that syncs to a
   cloud service (OneDrive often takes over Desktop and Documents), the sync
   program may interfere with the database file. Unverified; check on the
   pilot laptop.
3. **First-start time on a real laptop** has not been measured. If it is
   long, pre-compile the Python files in the zip.
4. **No password reset** in the portable build yet.
5. **Copyright holder name** in the README is a placeholder to confirm.

### Next

1. Push to GitHub and watch the first automated build run on real Windows.
2. Tag `v0.0.1` to publish the first release.
3. Try the released zip on the pilot Windows laptop and record what Windows
   says.
4. Collect from the pilot registrar: the PastPerfect edition, a real export
   file, how many scans and in what formats, how often moderation would
   happen, and any sensitivities that a privacy-policy template must cover.
5. Begin phase 1 with the import step, once a real export file is in hand.
