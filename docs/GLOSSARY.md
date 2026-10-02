# Glossary

Plain-language meanings of the technical terms used in this project, grouped
by where you meet them. If a term is used anywhere in this repository and is
not explained here, that is a mistake worth fixing.

## Keeping track of the code (Git and GitHub)

| Term | Meaning |
|---|---|
| **Git** | A program that records every change made to a set of files, so any earlier state can be recovered and several people can work without overwriting each other. |
| **Repository ("repo")** | A project folder that Git is tracking, together with its entire history. |
| **GitHub** | A website that stores repositories online so they can be shared and backed up. |
| **Commit** | One recorded change: a snapshot of the files plus a message saying what changed and why. |
| **Push** | Send your commits from your computer up to GitHub. |
| **Pull** | Bring commits from GitHub (or another copy) down to your computer. |
| **Clone** | Make a full copy of a repository, history included. |
| **Branch** | A line of work. This project's finished work lives on the branch called `main`. |
| **Tag** | A permanent name attached to one commit, such as `v0.0.1`. "This exact state is version 0.0.1." |
| **Release** | A GitHub page for one tag, with a description and files to download. This is where a museum gets the zip. |
| **Pre-release** | A release marked as not yet finished. GitHub shows it with a warning label. |
| **Git bundle** | A single file that carries commits from one place to another without going through GitHub. Used to hand work from a build session to the home PC. |

## The automated build (GitHub Actions)

| Term | Meaning |
|---|---|
| **GitHub Actions** | A GitHub feature that runs commands on GitHub's own computers whenever something is pushed. |
| **CI ("continuous integration")** | The practice of automatically testing every change as soon as it is pushed. Here, GitHub Actions does it. |
| **Workflow** | The file that tells GitHub Actions what to run: `.github/workflows/build.yml`. |
| **Job** | One part of a workflow that runs on one machine. This project has two: `build` and `release`. |
| **Artifact** | A file produced by a workflow and kept with that run, here the built zip. |
| **Green / red** | A build that passed / failed, from the tick or cross GitHub shows next to it. |

## How the application is put together (Django)

| Term | Meaning |
|---|---|
| **Python** | The programming language IdentifyCollection is written in. |
| **Django** | A widely used, long-established Python toolkit for building websites. It supplies accounts, forms, database access and much else. |
| **App** (in Django) | One self-contained part of a Django project. Ours so far: `accounts` and `core`. |
| **Settings** | The one file that configures the application: `app/config/settings.py`. |
| **Model** | The description of one kind of record kept in the database, for example a staff account. |
| **Migration** | A numbered, recorded change to the database's layout. Applying migrations is how a new version upgrades an existing database without losing what is in it. |
| **View** | The code that answers one kind of request and returns a page. |
| **Template** | An HTML page with blanks that the view fills in. |
| **URL / path** | A web address / the part of it after the site name, such as `/login/`. |
| **Static files** | The fixed files a page needs: stylesheets, fonts, images, scripts. |
| **collectstatic** | The Django step that gathers all static files into one folder when the zip is built. |
| **Session / cookie** | How the browser stays signed in between pages: a small token kept by the browser. |
| **CSRF token** | A hidden one-time code in each form that stops another website from submitting that form in your name. |
| **Admin** | Django's built-in screens for inspecting stored data, at `/admin/`. Kept as a behind-the-scenes tool. |

## Dependencies

| Term | Meaning |
|---|---|
| **Dependency / package** | Somebody else's code that this project uses. |
| **pip** | Python's tool for installing packages. |
| **Virtual environment ("venv")** | A private set of installed packages for one project, so projects cannot disturb each other. |
| **requirements.txt** | The list of packages this project needs. |
| **Pinned** | Fixed to one exact version, so every build uses the same code. |
| **Checksum (SHA-256)** | A long fingerprint calculated from a file's contents. If one byte changes, the fingerprint changes. Used to confirm a download is exactly the expected file. |
| **Vendored** | Stored inside this repository instead of being downloaded when needed. |
| **CDN** | Somebody else's server that websites borrow fonts and scripts from. This project uses none. |

## The portable Windows build

| Term | Meaning |
|---|---|
| **Portable build** | A version that runs from its own folder with nothing installed. Delete the folder and it is gone. |
| **Runtime** | The copy of Python that travels inside the zip, in the `runtime` folder. |
| **Batch file (`.bat`)** | A small Windows script. `Start IdentifyCollection.bat` is what gets double-clicked. |
| **Launcher** | `app/launch.py`: the program the batch file runs. It prepares the database, starts the web server and opens the browser. |
| **Web server** | The program that answers the browser's requests. In the portable build it runs on the same computer as the browser. |
| **waitress** | The small web server used in the portable build. |
| **WSGI** | The standard plug that lets any Python web server run any Python web application. |
| **WhiteNoise** | The package that lets the app serve its own static files. |
| **SQLite** | A database that lives in a single file. No separate database program to install. |
| **PostgreSQL** | A full database server, planned for permanent installs. |
| **127.0.0.1 ("localhost")** | The address that always means "this same computer". A program listening only there cannot be reached from the network. |
| **Port** | A numbered door on a computer. IdentifyCollection prefers door 8765, so its address is `http://127.0.0.1:8765/`. |
| **Data folder** | The `data` folder next to the program: database, logs, backups. The only thing a museum needs to back up. |
| **Mark of the Web** | A hidden label Windows puts on files downloaded from the internet. It is why Windows asks for confirmation before running them. "Unblock" in the file's Properties removes it. |
| **SmartScreen** | The Windows feature behind the blue "Windows protected your PC" box. |
| **Code signing** | A digital signature on a program proving who published it. Signed programs trigger fewer Windows warnings. |

## Testing

| Term | Meaning |
|---|---|
| **Automated test** | A small program that uses the app the way a person would and checks the result. Run with `python manage.py test`. |
| **Smoke test** | Switching the finished product on and checking nothing catches fire. Here: `packaging/smoke_test.py`, which starts the real zip and walks through first use. |
| **Wine** | A program that runs Windows programs on Linux. Used to rehearse the Windows zip where no Windows machine is available. A rehearsal, not proof. |

## Museum terms as this project uses them

| Term | Meaning |
|---|---|
| **Mystery** | A photograph, or a person in one, that the museum cannot yet identify. |
| **Submission** | One visitor's proposed identification, with their evidence. |
| **Evidence** | What supports a submission: a document, a cross-reference to another record, or personal testimony. |
| **Accession** (of an identification) | A collections manager's approval, after which the identification is part of the record. |
| **Deaccession** (of an identification) | Withdrawing an approved identification, with a recorded reason. The history is kept. |
| **Moderation queue** | The list of submissions waiting for a collections manager's decision. |
