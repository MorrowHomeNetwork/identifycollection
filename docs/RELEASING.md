# Releasing

How a version of IdentifyCollection gets from a working copy to a zip a
museum can download. Terms are explained in [GLOSSARY.md](GLOSSARY.md).

The rule: **every working session ends committed, pushed and releasable.**
Work that exists on one disk does not exist.

## The short version

```bash
# 1. on the main branch, with everything committed
git push

# 2. wait for the build at
#    https://github.com/MorrowHomeNetwork/identifycollection/actions
#    to show a green tick

# 3. name the version and publish it
git tag -a v0.0.1 -m "IdentifyCollection 0.0.1"
git push origin v0.0.1
```

A few minutes after step 3 the zip appears at
<https://github.com/MorrowHomeNetwork/identifycollection/releases>.

## Before you push

1. **The version number is right.** It lives in one place, `app/VERSION`.
   A version that has been published is never reused; raise the number.
2. **`CHANGELOG.md` has an entry for that version**, headed exactly
   `## [0.0.1] - 2026-10-01` (with the real version and date). Its text
   becomes the release description, so write it for the people who will run
   the software.
3. **The tests pass:**

   ```bash
   cd app
   python manage.py test
   ```

4. **Optional but recommended, the zip builds and starts:**

   ```bash
   python packaging/build_portable.py
   python packaging/smoke_test.py dist/IdentifyCollection-0.0.1-windows-x64.zip
   ```

## What GitHub does on every push

The workflow in `.github/workflows/build.yml` runs on a Windows machine at
GitHub:

1. installs the pinned packages, verifying their checksums;
2. runs the automated tests;
3. builds the portable zip;
4. smoke-tests the zip through the real `Start IdentifyCollection.bat`:
   first start, creating an account, signing out and in, a second
   double-click, stop, restart;
5. keeps the zip with the build for 30 days (on the build's page, under
   "Artifacts", as `portable-windows-zip`).

You can download that artifact and try it yourself before tagging.

## What GitHub does when you push a version tag

Everything above, plus:

- it checks that the tag (`v0.0.1`) and `app/VERSION` (`0.0.1`) agree, and
  stops if they do not;
- if every step passed, a second job creates the GitHub Release, attaches
  the zip and `SHA256SUMS.txt`, and uses the changelog entry as the
  description;
- versions below `0.1.0`, and versions containing a hyphen such as
  `0.2.0-rc1`, are marked as pre-releases.

A tag pushed onto a build that fails publishes nothing.

## When something goes wrong

**The build is red.** Open it on the Actions page and read the first failing
step. Fix the problem, commit, push. Do not tag until it is green.

**You tagged, and the build failed.** Nothing was published. Remove the tag,
fix, and tag again:

```bash
git tag -d v0.0.1
git push origin :refs/tags/v0.0.1
```

**A release was published and turns out to be wrong.** Do not replace it.
People may already have downloaded it, and a version number must always
mean the same files. Raise the version, fix, and publish the new one. If the
bad release is harmful, mark it clearly on its release page or delete the
release there, but never reuse its number.

**The push is refused with a message about `workflow` scope.** GitHub is
protecting the automated build file. The login your Git is using lacks
permission to change workflows. Signing in through the browser window that
Git for Windows opens grants it. If you use a personal access token, create
one that includes the `workflow` permission, or push over SSH instead.

## Receiving work from a build session

A build session that cannot reach GitHub hands over its commits as a single
file, a "git bundle".

**The first time** (no local copy yet), after creating the empty repository
on GitHub:

```bash
git clone identifycollection-step0.bundle identifycollection
cd identifycollection
git remote set-url origin https://github.com/MorrowHomeNetwork/identifycollection.git
git push -u origin main
```

**Every later time**, from inside your existing `identifycollection` folder:

```bash
git pull /path/to/the-new.bundle main
git push
```

`git pull` checks that the bundle continues from the history you already
have, and refuses if it does not.

## Changing the bundled Python

`packaging/python-runtime.json` pins the exact Python that goes into the zip.
To move to a newer one, change the release, version, file name, address and
checksum together, replace `packaging/licenses/python-license.rst` with the
one from the matching Python version, update `THIRD-PARTY-NOTICES.md`, then
run the build and the smoke test. The build refuses a download whose checksum
does not match.

## Changing a Python package

Edit the version and checksum in `requirements.txt` together (the checksum of
each file is shown on the package's "Download files" page on pypi.org),
update `THIRD-PARTY-NOTICES.md`, reinstall, and run the tests, the build and
the smoke test.
