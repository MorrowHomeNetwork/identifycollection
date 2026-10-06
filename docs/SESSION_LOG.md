# Session log

What each working session delivered, newest first. One entry per session:
what changed, the state it left things in, what is still open, what comes
next. No personal details belong in this file.

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
