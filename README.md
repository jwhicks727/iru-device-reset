# MDM Device Reset Automation
**Python · Selenium · JavaScript · Microsoft Edge**

---

## The Problem

At SOAR Charter Academy, wiping and re-enrolling iPads is an important part of daily device workflow -- as a troubleshooting step, at a teacher's request to get a "fresh start" with their class devices, at times for the whole fleet between school years. Accomplishing this is a multi-step manual
process through our MDM platform's web interface — open the device, navigate
menus, confirm multiple dialogs, select a Wi-Fi profile, type a confirmation
word, submit. Manageable for one device, but creates a time-expensive friction point for an entire
classroom, or campus-wide.

I built an automation to handle it.

---

## What It Does

Three scripts work together:

**erase_one_device.py** prompts for a serial number, finds the device, and runs
the full erasure sequence automatically — including Return to Service
configuration and Wi-Fi profile selection.

**erase_batch.py** reads a CSV exported manually from the MDM platform, shows
you the full device list before doing anything, asks you to type YES to confirm,
then processes each device in sequence.

**report_generator.py** is called automatically at the end of each batch run.
It builds all three output formats from the same run data and organizes them
into a timestamped folder — keeping automation logic and reporting logic cleanly
separated.

---

## How I Built It

This was my second Python project and the first using the Selenium framework.

The MDM platform presented three distinct technical challenges:

1. **Finding elements without clean identifiers** — some interactive elements
had no name or aria-label, so finding them required writing JavaScript that
searched by other means, like locating a button by its visible text.

2. **Getting interactions to register** — even when the right element was found, standard Selenium clicks and text input sometimes didn't work as expected. Typed text would appear then disappear. Dropdown clicks wouldn't open the menu. I worked through each failure by observing the specific behavior, researching the cause, and testing alternatives — ultimately using ActionChains for clicks that needed to simulate realistic mouse movement, and JavaScript for input fields that required a different approach to accept and retain values.

3. **Running efficiently without arbitrary delays** — page elements load at
unpredictable speeds, so a fixed wait is either too slow or occasionally too
fast. The solution was replacing fixed delays with polling loops that check for
the specific element needed every 100 milliseconds and move on the instant it's
ready — faster on good days, patient on slow ones.

I worked through these problems methodically: inspect the element, understand
what it's actually listening for, find the right approach, test it. I used AI
coding partners — Claude, GitHub Copilot, and ChatGPT at different points — as
a resource throughout. Managing those tools, evaluating conflicting suggestions,
and keeping the project moving when one got stuck is itself a skill I
refined during the work.

---

## What the Reports Look Like

Each run generates three files in a timestamped folder:

- A **CSV** with serial numbers, results, and notes — suitable for records and retests
- An **HTML report** with color-coded pass/fail rows and summary stats
- A **PDF** of the same report — easier to share with non-technical staff

When a device fails due to a known recoverable condition (the Wi-Fi profile
hadn't finished loading), it gets its own clearly labeled section in the report
with instructions to rerun rather than just appearing as a generic failure.

---

## Status

In active use at SOAR Charter Academy. Stress tested across several 4-device
batch runs, and now in use for full classes and fleet resets as necessary.

---

## Roadmap

Several improvements are planned for future versions:

**Dry run mode** — a flag that runs the full sequence for each device,
verifying it can find every element and navigate every step, but stops short
of the final confirmation. Allows a batch to be validated without actually
erasing anything.

**Retry queue** — devices that fail for recoverable reasons (Wi-Fi profile not
loaded, search timeout) could be automatically re-attempted at the end of the
run rather than requiring a manual rerun.

**Flexible CSV column handling** — currently the batch script expects a column 
amed exactly Serial in a fixed position. Replacing this with case-insensitive 
header matching and position-independent column detection would make the script 
more resilient to variations in how the CSV is exported or named.

**File picker dialog** — currently the batch script looks for a fixed
`devices.csv` in the project folder. A native macOS file picker dialog would
allow any CSV to be selected at runtime, making the workflow more flexible and
less dependent on file placement.

**Standalone application** — packaging the scripts as a self-contained desktop
application (macOS and potentially Windows) would allow a non-technical user to
run the automation without needing Python, a terminal, or any development
environment. Tools like PyInstaller or py2app make this possible from existing
Python code.

**Multi-organization support** — the school subdomain, Wi-Fi profile name, and
file paths are currently hardcoded constants. Abstracting these into a config
file would allow the script to work across multiple Iru organizations without
code changes.
