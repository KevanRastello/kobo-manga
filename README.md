# kobo-manga

Automatic weekly delivery of the latest **One Piece** chapter to a **Kobo Elipsa 2E**.

Every Sunday, GitHub Actions:

1. downloads the newest chapter from **MANGA Plus** (Shueisha's official, free site),
2. converts it with **KCC** (Kindle Comic Converter) into a `.kepub.epub` sized for the Elipsa 2E,
3. uploads it to Google Drive → `Mangas/OP`,

and the Kobo picks it up from Google Drive.

```
MANGA Plus ──mloader──▶ chapter.cbz ──KCC──▶ One Piece 1180.kepub.epub ──rclone──▶ Drive: Mangas/OP ──▶ Kobo
```

Everything is in one file: [`.github/workflows/one-piece.yml`](.github/workflows/one-piece.yml).
The settings you might change are in its `env:` block at the top.

---

## Contents

1. [One-time setup](#1-one-time-setup)
2. [Using it](#2-using-it)
3. [How it works, step by step](#3-how-it-works-step-by-step)
4. [Why it is built this way (decisions)](#4-why-it-is-built-this-way-decisions)
5. [Settings you can change](#5-settings-you-can-change)
6. [Troubleshooting](#6-troubleshooting)
7. [To fix (open items)](#7-to-fix-open-items)
8. [Doing it by hand on Windows](#8-doing-it-by-hand-on-windows)

---

## 1. One-time setup

### 1.1 Get a Google Drive token (done on your PC)

The robot running on GitHub needs permission to write into your Google Drive. `rclone` creates that permission.

```powershell
winget install Rclone.Rclone
rclone authorize "drive"
```

A browser opens. Sign in with your Google account and click **Allow**.
The terminal then prints something like:

```
Paste the following into your remote machine --->
{"access_token":"ya29....","token_type":"Bearer","refresh_token":"1//0....","expiry":"2026-10-25T18:40:00-07:00"}
<---End paste
```

Copy only the `{...}` part, including both curly brackets.

### 1.2 Save it as a GitHub secret

1. Open this repo on github.com.
2. Go to **Settings** (the tab at the top of the repo, not your account settings).
3. In the left menu, open **Secrets and variables** → **Actions**.
4. Click **New repository secret**.
5. **Name:** `RCLONE_DRIVE_TOKEN` (exactly this, in capitals)
   **Secret:** paste the `{...}` text
6. Click **Add secret**.

GitHub stores it encrypted. Nobody can read it back, not even you, and it never appears in the logs.

> ⚠️ The token can read and write your **whole** Google Drive. Keep this repo **private**.
> If you ever think it leaked, remove "rclone" at <https://myaccount.google.com/permissions>,
> then repeat 1.1–1.2.

### 1.3 First test run

1. Open the repo's **Actions** tab.
2. If GitHub asks, click **"I understand my workflows, go ahead and enable them"**.
3. In the left list, click **One Piece weekly** → **Run workflow** → **Run workflow**.
4. Wait about 3–5 minutes. A green ✓ means success. Open the run to see each step's log.
5. Check Google Drive → `Mangas/OP`. You should see `One Piece <number>.kepub.epub`.

### 1.4 Kobo side (once)

On the Elipsa 2E, open Google Drive (Kobo menu → Google Drive; Kobo's guide is
[here](https://help.kobo.com/hc/en-us/articles/15335985512983-Add-books-to-your-eReader-using-Google-Drive)),
sign in, go to `Mangas/OP` and download the chapter.

---

## 2. Using it

| When | What happens |
|---|---|
| **Sunday 15:30 UTC** (08:30 Vancouver in summer, 07:30 in winter) | Main run, about 30 min after MANGA Plus releases the chapter |
| **Monday 03:00 UTC** (Sunday evening in Vancouver) | Retry, in case the release was late |
| Any time | Actions → One Piece weekly → **Run workflow** |

| Situation | Result |
|---|---|
| New chapter is out | Uploaded as `One Piece <n>.kepub.epub` |
| Break week, or chapter already in Drive | Run is green, nothing is uploaded |
| Chapter not free / MANGA Plus or mloader broken / token expired | Run goes **red** and GitHub **emails you** |

**Cost:** about 3–5 Actions minutes per run, around 30 minutes a month. Private repos get 2,000 free minutes a month.

---

## 3. How it works, step by step

The workflow runs on a fresh Ubuntu machine that GitHub lends you for a few minutes and then wipes.

### Step 1: Install tools

| Tool | What it is for |
|---|---|
| `p7zip-full` | Unzipping archives; KCC needs it to open `.cbz` files |
| `rclone` | Uploading to Google Drive |
| [`mloader`](https://pypi.org/project/mloader/) | Downloading chapters from MANGA Plus |
| [KCC](https://github.com/ciromattia/kcc) `v12.1.1` | Converting the comic for the e-reader. Pinned to a release so an update can't silently break it |
| `PySide6-Essentials` | KCC's command-line tool still imports one piece of its GUI library, so it is needed even without a screen |

### Step 2: Download the latest chapter

```bash
mloader https://mangaplus.shueisha.co.jp/titles/100020 --last -o raw
```

`100020` is One Piece (English) on MANGA Plus, and `--last` means "only the newest chapter".
The result is a file like `raw/One Piece/One Piece - d1180 (web) [Unknown].cbz`. A `.cbz` is just a zip of page images.

### Step 3: Convert for the Elipsa 2E

```bash
kcc-c2e.py -p KoE -m -u -f EPUB -r 0 -t "One Piece 1180" -o kcc_out "<file>.cbz"
```

| Flag | Meaning |
|---|---|
| `-p KoE` | Device profile "Kobo Elipsa": 1404×1872, 16 shades of grey. The Elipsa 2E has the same screen |
| `-m` | Manga mode: pages turn **right-to-left**, the Japanese order |
| `-u` | Upscale small pages to fill the screen |
| `-f EPUB` | EPUB output. With a Kobo profile, KCC names it `.kepub.epub` (Kobo's faster format) |
| `-r 0` | Double-page spreads are **split** into two pages. See [To fix](#7-to-fix-open-items) |
| `-t` | Book title shown on the Kobo |

The chapter number is read from mloader's file name (`d1180` → `1180`), and the result is renamed to `One Piece 1180.kepub.epub`.
If no `.cbz` was downloaded, the step stops with an error. That way a silent failure can't look like success.

### Step 4: Upload to Drive

```bash
rclone copy out gdrive: --ignore-existing
```

- rclone is configured entirely through `RCLONE_CONFIG_GDRIVE_*` environment variables, so no config file is needed.
- `ROOT_FOLDER_ID` points directly at the `Mangas/OP` folder (ID `1MLbtZhi0npGdKBkvJApSc_rJxz6vi9if`), so `gdrive:` means "inside OP".
- `--ignore-existing` skips files already in Drive. This is the only "memory" the system needs: re-running never creates duplicates.

---

## 4. Why it is built this way (decisions)

| Decision | Why | Alternative considered |
|---|---|---|
| **MANGA Plus** as the source | Official and free for the newest chapters, and `mloader` is a single command | **Suwayomi** (used on the PC). It is a full server (Java, extensions, a query API), heavy and fragile to start on every run. Its MANGA Plus extension uses the same source anyway. Pirate sources were rejected (legality, and GitHub can disable repos used for piracy) |
| **GitHub Actions** | Free minutes, runs while the PC is off, emails on failure | Windows Task Scheduler (needs the PC on) |
| **`.kepub.epub`** | Kobo's native variant of EPUB: faster page turns, better rendering of image books | Plain EPUB, CBZ, PDF |
| **rclone with your own Google login** | Works with a personal Drive | A Google *service account* can't create files in a personal "My Drive" (it has no storage quota) |
| **Dedupe with `--ignore-existing`** | No database or state file to maintain | Storing the last chapter number in the repo |
| **KCC pinned to `v12.1.1`** | Reproducible; `master` can change any day | Always using the latest code |
| **Two runs a week** | Covers delayed releases; a break week costs ~3 minutes | Running every hour |

Two quirks found while testing, which are already handled in the workflow:

- KCC fails with "Failed to open source file/directory" when given **relative** paths, so the workflow passes absolute paths (`$PWD/...`).
- KCC's CLI crashes without `PySide6`, even though its CLI requirements file doesn't list it. Hence `PySide6-Essentials`.

What was tested before the first real run:
- The conversion step was run on a dummy chapter. It produced `One Piece 1180.kepub.epub` at 1404×1872, right-to-left, with the double-page spread split and the title set.
- The "no chapter downloaded" case was checked: the step fails with a clear error.

The download and upload steps only run for real on GitHub.

---

## 5. Settings you can change

All of these are in the `env:` block of `.github/workflows/one-piece.yml`. Edit them on github.com with the pencil icon.

| Setting | Current value | Change it to… |
|---|---|---|
| `MANGAPLUS_TITLE` | One Piece | Another series: copy its `https://mangaplus.shueisha.co.jp/titles/<id>` URL |
| `DRIVE_FOLDER_ID` | `Mangas/OP` | Another Drive folder: the ID is the last part of its URL |
| `KCC_FLAGS` | `-p KoE -m -u -f EPUB -r 0` | Remove `-m` for left-to-right (Western) page order; `-r 1` rotate spreads, `-r 2` split **and** rotate; add `--nokepub` for plain `.epub` |
| `KCC_VERSION` | `v12.1.1` | A newer tag from [KCC releases](https://github.com/ciromattia/kcc/releases) |
| Schedule (`cron:` lines) | Sun 15:30 + Mon 03:00 UTC | Any time; [crontab.guru](https://crontab.guru) helps. Times are **UTC** |

Adding another series: copy `one-piece.yml` to a new file (for example `hxh.yml`), then change the name, the three settings above, and the `One Piece` text in the convert step.

---

## 6. Troubleshooting

Open the red run in **Actions**, click the failed step and read the last lines.

| Failed step | Likely cause | Fix |
|---|---|---|
| Download | Chapter not free right now, MANGA Plus changed its API, or MANGA Plus blocks GitHub's servers | Try "Run workflow" later. Check for a newer mloader: <https://pypi.org/project/mloader/> |
| Convert: "mloader produced no chapter" | Same as above | Same |
| Convert: other error | New KCC behaviour | Go back to the last working `KCC_VERSION` |
| Upload: `invalid_grant` / `401` | The Google token was revoked or expired | Redo 1.1–1.2, then overwrite the secret with **Update** |
| Upload: `directory not found` | The OP folder was moved or deleted | Update `DRIVE_FOLDER_ID` |

---

## 7. To fix (open items)

1. **Clean metadata for every chapter (existing + new).**
   Goal: consistent title, series name *One Piece*, series number = chapter number (so the Kobo groups the chapters in order), author *Eiichiro Oda*, chapter subtitle and cover.
   It must also be applied to the chapters already in `Mangas/OP`.
2. **Double-page spreads get cut on the Kobo.**
   Goal: find the KCC setting (`-r` split/rotate/both, `--spreadshift`, cropping `-c`) that shows spreads cleanly on the Elipsa 2E, then re-convert older chapters with it.

---

## 8. Doing it by hand on Windows

```powershell
pip install mloader
mloader https://mangaplus.shueisha.co.jp/titles/100020 --last -o raw
```

Then open the `.cbz` in the KCC app: profile **Kobo Elipsa**, **Manga mode** on, format **EPUB**.
Upload the result to `Mangas/OP` by hand.
