# Changelog

What changed in each version of IdentifyCollection, newest first, written for
the people who run it rather than the people who build it.

Version numbers: `0.0.x` are scaffolding and test drops. `0.1.0` will be the
first build a museum can do real work with (phase 1). The text under each
version heading becomes the description of that version's GitHub Release.

## [0.0.2] - 2026-10-06

The first build that does the real work, start to finish. Catalog import is
still to come; everything else in the loop is here to try.

### What you can do now

- **Add photographs.** Choose scans, or a whole folder of them, from your
  computer. JPEG, TIFF (including 16-bit archival scans) and PNG all work.
  Nothing is shown to visitors until you put it on show.
- **Show them.** Visitors see a gallery of the photographs on show and can
  zoom right into each one. They do not need an account.
- **Collect answers.** A visitor marks a face by dragging a box around it,
  says who it is and how sure they are, and gives one piece of evidence:
  their own knowledge, an attached document or photograph, or a pointer to
  another record. They agree to the museum keeping it, and may leave their
  name and contact details or stay anonymous.
- **Review.** Each answer waits in a review list. Accept it and the name
  appears on the photograph; decline it and nothing becomes public. An
  accepted name can be withdrawn later, with a reason, and reinstated; the
  history of every decision is kept. A contributor's personal details can be
  erased on request without losing the identification.
- **Export.** Download one spreadsheet (CSV) of everything accepted, and
  everything later withdrawn, with the marked area given in pixels of your
  original scan.
- **Practise first.** One button adds six made-up practice photographs, and
  one removes them and everything sent in about them.

### Good to know

- Your original scan files are not copied into IdentifyCollection. It keeps
  a zoomable JPEG (up to 4000 pixels on the long side) and the original's
  file name, size and fingerprint.
- For people running the code on a server or virtual machine: the setting
  `IDENTIFYCOLLECTION_EXTRA_HOSTS` lists extra addresses the app answers on.
  The portable Windows build is unchanged and answers only on its own
  computer.

### Not built yet

- Importing a catalog file (PastPerfect or CSV). For now, the object ID,
  title and date of each photograph are typed in by hand.
- A "forgot my password" button.

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
