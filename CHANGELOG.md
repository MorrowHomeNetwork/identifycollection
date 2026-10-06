# Changelog

What changed in each version of IdentifyCollection, newest first, written for
the people who run it rather than the people who build it.

Version numbers: `0.0.x` are scaffolding and test drops. `0.1.0` will be the
first build a museum can do real work with (phase 1). The text under each
version heading becomes the description of that version's GitHub Release.

## [Unreleased]

- For people running the code on a server or a virtual machine: the setting
  `IDENTIFYCOLLECTION_EXTRA_HOSTS` lists the extra names or addresses the app
  should answer on, so it can be opened from other computers on the same
  network. The portable Windows build is unchanged and still answers only on
  the computer it runs on.

## [0.0.1] - 2026-10-01

The first test build. **It cannot import or identify anything yet.** Its only
job is to prove that IdentifyCollection can reach a museum's computer and
start there.

### What it does

- Arrives as one zip file. Extract it, double-click
  **Start IdentifyCollection**, and it opens in the web browser.
- Needs nothing installed and no internet connection. Python, the database
  and every font and style are inside the folder.
- Asks you to create the first staff account on first start, then lets you
  sign in and out.
- Keeps everything it stores in one `data` folder next to the program.
- Can only be reached from the computer it is running on.

### What to tell us

This build exists to find problems early. Please report:

- any warning Windows showed before it would start, and exactly what it said;
- how long the first start took, and the second;
- anything on the screen that was confusing.

### Known limits

- Windows 10 or 11, 64-bit only.
- There is no "forgot my password" yet. Write the password down.
- The copy of Python inside the zip is not digitally signed, so Windows may
  ask for confirmation the first time it runs.
