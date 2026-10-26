# kobo-manga

Automatic weekly delivery of the latest **One Piece** chapter to a **Kobo Elipsa 2E**.

Every Sunday, GitHub Actions:

1. downloads the newest chapter from **MANGA Plus** (Shueisha's official, free site),
2. adds clean metadata (series, chapter number, chapter title, author),
3. converts it with **KCC** (Kindle Comic Converter) into a `.kepub.epub` sized for the Elipsa 2E, with double-page spreads shown split **and** whole,
4. uploads it to Google Drive → `Mangas/OP`,

and the Kobo picks it up from Google Drive.

```
MANGA Plus ─manga-downloader─▶ .cbz ─metadata.py─▶ .cbz + ComicInfo.xml ─KCC─▶ One Piece 1196 - <title>.kepub.epub ─rclone─▶ Drive: Mangas/OP ─▶ Kobo
```

| File | Role |
|---|---|
| [`.github/workflows/one-piece.yml`](.github/workflows/one-piece.yml) | The whole routine. The settings you might change are in its `env:` block at the top |
| [`tools/metadata.py`](tools/metadata.py) | Writes the metadata before and after KCC |

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
| New chapter is out | Uploaded as `One Piece <n> - <chapter title>.kepub.epub` |
| Several chapters were missed | All of them are fetched in the next run |
| Break week, or nothing newer than Drive | Run is green with the notice "No new chapter this time" |
| MANGA Plus or downloader broken / token missing or expired | Run goes **red** and GitHub **emails you** |

Each run's summary page (Actions → click the run) lists short **notices**, for example:
`Drive has up to chapter 1195; looking for chapter 1196 and later` → `downloaded One Piece 1196 - The Love of the Suicidal is Worthless.cbz` →
`… number=1196 title='…' spreads=0` → `converted …` → `uploaded …`.

### Redo chapters (clean up old ones, or re-convert after a settings change)

Actions → **One Piece weekly** → **Run workflow** → in the box **"Redo these chapters"** type a number or range, for example `1196` or `1190-1195` → **Run workflow**.

- Those chapters are downloaded again and converted with the current settings and metadata.
- Any older copy of the same chapter, under another name (for example `Chapter 1195_ Veakness.kepub.epub` from Suwayomi), is **moved** to `OP/_old`. **Nothing is deleted**; empty `_old` yourself once you're happy.
- A copy with exactly the same name is overwritten.
- Leave the box empty for a normal run (new chapters only).
- On the Kobo, delete the old copy from the library and download the new file again.

**Cost:** about 3–5 Actions minutes per run, around 30 minutes a month. Private repos get 2,000 free minutes a month.

---

## 3. How it works, step by step

The workflow runs on a fresh Ubuntu machine that GitHub lends you for a few minutes and then wipes.

### Step 1: Install tools

| Tool | What it is for |
|---|---|
| `7zip` | Unzipping archives; KCC needs it to open `.cbz` files |
| `rclone` | Uploading to Google Drive |
| [`manga-downloader`](https://github.com/elboletaire/manga-downloader) (latest release) | Downloading chapters from MANGA Plus. It always takes the newest release, because scrapers need fixes quickly when a site changes |
| [KCC](https://github.com/ciromattia/kcc) `v12.1.1` | Converting the comic for the e-reader. Pinned to a release so an update can't silently break it |
| `PySide6-Essentials` | KCC's command-line tool still imports one piece of its GUI library, so it is needed even without a screen |

### Step 2: Download the new chapters

First, the workflow asks Drive for the **highest chapter number already in `Mangas/OP`**:

```bash
rclone lsf gdrive: | grep -oP '^(?:One Piece|Chapter) \K\d+' | sort -n | tail -1
```

This recognises the new names (`One Piece 1196 - <title>.kepub.epub`) and the older Suwayomi names (`Chapter 1195_ Veakness.kepub.epub`).
If the folder has none, it starts at `FIRST_CHAPTER`.
Then it downloads every chapter **after** that one. In redo mode it downloads the range you typed instead.

```bash
manga-downloader https://mangaplus.shueisha.co.jp/titles/100020 1197-99999 --language en -o raw \
  -t "One Piece {{.Number}}{{if .SiteTitle}} - {{.SiteTitle}}{{end}}"
```

- `100020` is One Piece on MANGA Plus, and `--language en` picks the English edition.
- `1197-99999` means "1197 and everything after". Normally that's one chapter, but a missed week catches up by itself.
- If nothing new exists, the tool says `No chapters found for the specified ranges`. The workflow treats that as a normal break week and the run stays green.
- MANGA Plus only answers the full chapter list to a registered app. manga-downloader registers an **anonymous device** by itself on each run, so no account is needed.
- `-t` sets the file name **including the chapter title**: `raw/One Piece 1196 - The Love of the Suicidal is Worthless.cbz`. A `.cbz` is just a zip of page images.

### Step 3: Metadata, then convert for the Elipsa 2E

**3a. Metadata in.** [`tools/metadata.py`](tools/metadata.py) `comicinfo` reads the file name and writes a `ComicInfo.xml` (the standard comic metadata file) into the `.cbz`:

| Field | Value |
|---|---|
| Series | One Piece |
| Number | 1196 |
| Title | The Love of the Suicidal is Worthless |
| Writer / Penciller | Eiichiro Oda |
| Manga | YesAndRightToLeft |

It also counts **double-page spreads** (pages wider than tall) and reports them in a notice (`spreads=…`).

**3b. Convert.**

```bash
kcc-c2e.py -p KoE -m -u -f EPUB -r 2 --metadatatitle 1 -o kcc_out "<file>.cbz"
```

| Flag | Meaning |
|---|---|
| `-p KoE` | Device profile "Kobo Elipsa": 1404×1872, 16 shades of grey. The Elipsa 2E has the same screen |
| `-m` | Manga mode: pages turn **right-to-left**, the Japanese order |
| `-u` | Upscale small pages to fill the screen |
| `-f EPUB` | EPUB output. With a Kobo profile, KCC names it `.kepub.epub` (Kobo's faster format) |
| `-r 2` | Each double-page spread appears **twice**: split into two halves (read normally), **then** as one full page rotated 90° (turn the Kobo sideways to see the whole spread uncut). This happens automatically for every wide page |
| `--metadatatitle 1` | Book title = series + number + chapter title from `ComicInfo.xml`: **`One Piece #1196: The Love of the Suicidal is Worthless`** |

From `ComicInfo.xml`, KCC writes into the e-book: the title, the author (*Eiichiro Oda*, instead of "KCC"), and the EPUB3 series tags (`belongs-to-collection` = One Piece, `group-position` = 1196).

**3c. Metadata out.** `tools/metadata.py calibre` adds the same series as Calibre tags (`calibre:series`, `calibre:series_index`).
Readers and tools understand one or the other format, so having both gives the Kobo the best chance to group the chapters as a series, in order.

Each step writes short **notices** (downloaded / metadata / converted / uploaded). They appear on the run's summary page.
`python tools/metadata.py test` is a self-check, and it runs on every run.

### Step 4: Upload to Drive

```bash
rclone copy out gdrive: --ignore-existing
```

- rclone is configured entirely through `RCLONE_CONFIG_GDRIVE_*` environment variables, so no config file is needed.
- `ROOT_FOLDER_ID` points directly at the `Mangas/OP` folder (ID `1MLbtZhi0npGdKBkvJApSc_rJxz6vi9if`), so `gdrive:` means "inside OP".
- `--ignore-existing` skips a file whose name already exists in Drive. This is a second safety net on top of step 2.
- In redo mode, older copies of the redone chapters are first moved to `OP/_old` with `rclone moveto`, then the new files are uploaded, overwriting any copy with the same name.
- The Drive folder itself is the system's only "memory": no database, no state file.

---

## 4. Why it is built this way (decisions)

| Decision | Why | Alternative considered |
|---|---|---|
| **MANGA Plus** as the source | Official and free for the newest chapters, and `manga-downloader` is a single command | **Suwayomi** (used on the PC). It is a full server (Java, extensions, a query API), heavy and fragile to start on every run. Its MANGA Plus extension uses the same source anyway. Pirate sources were rejected (legality, and GitHub can disable repos used for piracy) |
| **GitHub Actions** | Free minutes, runs while the PC is off, emails on failure | Windows Task Scheduler (needs the PC on) |
| **`.kepub.epub`** | Kobo's native variant of EPUB: faster page turns, better rendering of image books | Plain EPUB, CBZ, PDF |
| **rclone with your own Google login** | Works with a personal Drive | A Google *service account* can't create files in a personal "My Drive" (it has no storage quota) |
| **"What's new" = highest chapter in Drive** | No database or state file to maintain. Deleting a chapter from Drive does *not* re-download it unless it was the highest one | Storing the last chapter number in the repo. A fixed range like `1100-99999`: the anonymous device sees **all** chapters, so that would download ~97 chapters every week |
| **KCC pinned to `v12.1.1`** | Reproducible; `master` can change any day | Always using the latest code |
| **Two runs a week** | Covers delayed releases; a break week costs ~3 minutes | Running every hour |
| **Metadata from the file name** | The downloader names the file `One Piece <n> - <title>` but writes no metadata file, so the name is the one reliable source | Typing metadata by hand; Calibre (a large GUI app) |
| **Spreads: `-r 2` (split + rotated)** | With the old `-r 0`, a spread was only shown as two halves, cutting the drawing in the middle. Now the halves keep reading smooth, and the rotated full page shows the spread whole | `-r 1` (rotated only: you'd turn the Kobo for every spread); `-r 0` (halves only) |
| **Redo moves old files to `_old`, never deletes** | Reversible; you decide when to empty it | Deleting old copies |
| **manga-downloader**, not `mloader` | MANGA Plus now gives the chapter list only to registered app clients. `mloader` (v1.1.12) doesn't register, so it got **zero chapters** and still exited "successfully". That was the cause of the first failed run on 2026-10-25. manga-downloader registers an anonymous device automatically and is actively maintained | `mloader` |

Quirks found while testing, which are already handled in the workflow:

- KCC fails with "Failed to open source file/directory" when given **relative** paths, so the workflow passes absolute paths (`$PWD/...`).
- KCC's CLI crashes without `PySide6`, even though its CLI requirements file doesn't list it. Hence `PySide6-Essentials`.

- manga-downloader doesn't create the output folder, and fails with `no such file or directory` without it. The workflow runs `mkdir -p raw` first.

### Test history (2026-10-25)

| Run | Result | What we learned / changed |
|---|---|---|
| Dummy chapter, run by hand | ✓ | KCC gives 1404×1872, right-to-left, spread split, title set |
| 1st GitHub run (mloader) | ✗ | mloader got 0 chapters → switched to manga-downloader |
| 2nd–3rd | ✗ | Output folder missing → `mkdir -p raw`. The log showed chapters 1182–1196 all available |
| 4th | ✓ | Drive had up to 1195 → **One Piece 1196** downloaded, converted (9.3 MB) and uploaded |
| 5th | ✗ → fixed | Nothing new → "No chapters found" was treated as an error |
| 6th | ✓ | Nothing new → green run, "No new chapter this time" |
| Metadata + `-r 2`, by hand | ✓ | Dummy chapter with a spread: title `One Piece #1196: …`, author Eiichiro Oda, EPUB3 + Calibre series tags, spread split **and** rotated |
| 7th: redo `1196` | ✓ | `One Piece 1196 - The Love of the Suicidal is Worthless.kepub.epub` uploaded; old `One Piece 1196.kepub.epub` moved to `_old`. That chapter has 0 spreads |

---

## 5. Settings you can change

All of these are in the `env:` block of `.github/workflows/one-piece.yml`. Edit them on github.com with the pencil icon.

| Setting | Current value | Change it to… |
|---|---|---|
| `MANGAPLUS_TITLE` | One Piece | Another series: copy its `https://mangaplus.shueisha.co.jp/titles/<id>` URL |
| `DRIVE_FOLDER_ID` **and** `RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID` | `Mangas/OP` | Another Drive folder: the ID is the last part of its URL. Change both lines |
| `FIRST_CHAPTER` | `1196` | Where to start when the Drive folder has no numbered chapter yet |
| `NAME_TEMPLATE` | `One Piece {{.Number}} - {{.SiteTitle}}` | Another series name. Keep `<name> <number> - <title>`, because the metadata is read from it |
| `KCC_FLAGS` | `-p KoE -m -u -f EPUB -r 2 --metadatatitle 1` | Remove `-m` for left-to-right (Western) page order; spreads `-r 0` halves only, `-r 1` rotated only; add `--nokepub` for plain `.epub`. Then use **Redo** to re-convert older chapters |
| `KCC_VERSION` | `v12.1.1` | A newer tag from [KCC releases](https://github.com/ciromattia/kcc/releases) |
| Schedule (`cron:` lines) | Sun 15:30 + Mon 03:00 UTC | Any time; [crontab.guru](https://crontab.guru) helps. Times are **UTC** |

Adding another series: copy `one-piece.yml` to a new file (for example `hxh.yml`), then change the name, the three settings above, and the `One Piece` text in the convert step.

---

## 6. Troubleshooting

Open the red run in **Actions**, click the failed step and read the last lines.

| Failed step | Likely cause | Fix |
|---|---|---|
| Download | MANGA Plus changed something, or it blocks GitHub's servers | Try "Run workflow" later. The workflow already takes the newest manga-downloader release; check its [issues](https://github.com/elboletaire/manga-downloader/issues) |
| Green but a chapter is missing | A chapter with a *higher* number is already in Drive, so the missing one is never asked for | Run with **Redo** = that chapter number |
| Spread still looks cut | The chapter was converted before `-r 2`, or MANGA Plus served that spread as two separate pages (then `spreads=0` in the notice) | Redo the chapter. If the notice says `spreads=0`, see [To fix](#7-to-fix-open-items) |
| Upload: "Secret RCLONE_DRIVE_TOKEN is missing" | Step 1.2 not done, or the name is misspelled | Redo 1.2 |
| Convert: other error | New KCC behaviour | Go back to the last working `KCC_VERSION` |
| Upload: `invalid_grant` / `401` | The Google token was revoked or expired | Redo 1.1–1.2, then overwrite the secret with **Update** |
| Upload: `directory not found` | The OP folder was moved or deleted | Update `DRIVE_FOLDER_ID` |

---

## 7. To fix (open items)

1. **Clean metadata for every chapter**: ✅ done for new chapters (step 3) and for 1196.
   Still to do: run **Redo** on the older chapters (for example `1190-1195`) to replace the Suwayomi files.
   Still to check on the Kobo: does it group the chapters under the series *One Piece*? Both standard series tags are written, but Kobo's support for series in sideloaded books isn't confirmed.
2. **Double-page spreads get cut on the Kobo**: ✅ `-r 2` (split + rotated full page) applies automatically to every wide page.
   Still to check: whether MANGA Plus delivers spreads as one wide image (then this fixes it) or as two separate pages (then `spreads=0` and KCC can't see them).
   Watch the `spreads=` notices while redoing older chapters, and compare with a chapter where you saw a cut spread.

---

## 8. Doing it by hand on Windows

Install manga-downloader on Windows (see [its README](https://github.com/elboletaire/manga-downloader#command-line)), then:

```powershell
manga-downloader https://mangaplus.shueisha.co.jp/titles/100020 1196 --language en -o raw -t "One Piece {{.Number}} - {{.SiteTitle}}"
```

(`1196` = the chapter you want; `1190-1196` for several.) Then run `python tools/metadata.py comicinfo "<file>.cbz"` and open the `.cbz` in the KCC app: profile **Kobo Elipsa**, **Manga mode** on, format **EPUB**, spreads "split and rotate".
Easier: use **Redo** in the Actions tab (section 2).
Upload the result to `Mangas/OP` by hand.
