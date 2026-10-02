# Third-party notices

IdentifyCollection itself is licensed under the GNU Affero General Public
License, version 3 (see `LICENSE`). It is built on, and its portable Windows
zip includes, the work of other open-source projects. Each remains under its
own licence, listed here. All of these licences allow the software to be
used, copied and redistributed, and all are compatible with distributing
IdentifyCollection under the AGPL.

Nothing in this list is downloaded when IdentifyCollection runs. Everything
is either stored in this repository or placed inside the zip when it is built.

## Included in the portable Windows zip

| Component | Version | What it does here | Licence | Full licence text inside the zip |
|---|---|---|---|---|
| Python (CPython), as built by the python-build-standalone project | 3.14.7 (build 20260929) | The programming language runtime the app runs on | Python Software Foundation License Version 2 | `runtime/LICENSE.txt` |
| Django | 6.1.1 | The web framework: pages, forms, accounts, database access | BSD-3-Clause | `runtime/Lib/site-packages/django-6.1.1.dist-info/licenses/` |
| asgiref | 3.12.1 | Required by Django | BSD-3-Clause | `runtime/Lib/site-packages/asgiref-3.12.1.dist-info/licenses/` |
| sqlparse | 0.6.0 | Required by Django | BSD-3-Clause | `runtime/Lib/site-packages/sqlparse-0.6.0.dist-info/licenses/` |
| tzdata | 2026.4 | The world's time-zone rules (Windows has no copy Python can use) | Apache-2.0 | `runtime/Lib/site-packages/tzdata-2026.4.dist-info/licenses/` |
| waitress | 3.0.2 | The small web server inside the portable build | ZPL-2.1 (Zope Public License) | `runtime/Lib/site-packages/waitress-3.0.2.dist-info/LICENSE.txt` |
| WhiteNoise | 6.12.0 | Serves the stylesheet, fonts and images | MIT | `runtime/Lib/site-packages/whitenoise-6.12.0.dist-info/licenses/` |

The Python runtime is itself assembled from other open-source components.
Their licence texts and copyright notices travel in the zip in two files:

- `runtime/LICENSE.txt`, supplied with the runtime: Python's own licence, the
  conditions for redistributing the Microsoft Visual C++ runtime libraries,
  and the notices for bzip2, Zstandard and Tcl/Tk. (The Tcl/Tk files
  themselves are removed from the zip; IdentifyCollection does not use them.)
- `runtime/LICENSES-incorporated-software.txt`: Python's official "History and
  License" document for this exact version, whose section "Licenses and
  Acknowledgements for Incorporated Software" covers OpenSSL (Apache-2.0),
  Expat (MIT), libffi (MIT), zlib (zlib licence), libmpdec (BSD-2-Clause),
  mimalloc (MIT) and the smaller pieces of code built into Python.

The runtime also includes SQLite, which is in the public domain, and XZ Utils'
liblzma, which is under the Zero-Clause BSD licence (earlier versions: public
domain); neither requires a notice.

The exact versions and checksums of the Python packages are recorded in
`requirements.txt`; the exact Python runtime is recorded in
`packaging/python-runtime.json`.

## Stored in this repository

| Component | Version | Where | Licence | Copyright |
|---|---|---|---|---|
| Besley (typeface, variable, Latin and Latin Extended subsets) | as packaged by Fontsource 5.3.0 | `app/static/fonts/besley/` | SIL Open Font License 1.1 (`OFL.txt` alongside) | Copyright 2020 The Besley Project Authors (https://github.com/indestructible-type) |
| Atkinson Hyperlegible Next (typeface, variable, Latin and Latin Extended subsets) | as packaged by Fontsource 5.3.0 | `app/static/fonts/atkinson-hyperlegible-next/` | SIL Open Font License 1.1 (`OFL.txt` alongside) | Copyright 2020-2024 The Atkinson Hyperlegible Next Project Authors (https://github.com/googlefonts/atkinson-hyperlegible-next) |

## Keeping this file honest

When a dependency is added, removed or upgraded, this file is updated in the
same commit. Libraries planned for later phases (OpenSeadragon, Annotorious,
libvips) are not listed because they are not included yet.
