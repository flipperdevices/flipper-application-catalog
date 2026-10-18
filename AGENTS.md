# AGENTS.md — Flipper Application Catalog

Guidance for AI coding assistants (and the people using them) preparing an application
submission to the **Flipper Application Catalog**. Follow these rules when creating or editing
an app and its `application.fam`, the catalog `manifest.yml`, the description/changelog,
screenshots, and icon. A submission that breaks any of these will be sent back for changes.

Authoritative reference: `documentation/Manifest.md`.
Always validate before submitting:

```
python3 tools/bundle.py --nolint applications/CATEGORY/APPID/manifest.yml bundle.zip
```

---

## 1. Manifest and paths

- Put the manifest at `applications/<Category>/<appid>/manifest.yml`. The file must be named
  **exactly `manifest.yml`** (not `.yaml` or anything else).
- The `<appid>` folder must be **all lowercase**, using only `[a-z0-9_]`, and it must **match**
  both the `id` in the manifest and the `appid` in `application.fam`.
- `<Category>` must be one of: `Sub-GHz, RFID, NFC, Infrared, GPIO, iButton, USB, Games, Media,
  Tools, Bluetooth`, and must match `category` / `fap_category`.
- Use the catalog schema — not any other format:

  ```yaml
  sourcecode:
    type: git
    location:
      origin: https://github.com/<user>/<repo>.git
      commit_sha: <full 40-character commit hash>   # NOT a short hash
      subdir: <path>          # optional, only if the app lives in a subfolder
  ```

  Do **not** use `source:`, `location.url`, `location.commit`, or a `fetcher:` block — those are
  not the catalog format and will fail.
- Required fields: `sourcecode`, `screenshots`, `changelog`, `short_description`, `description`,
  `name`, `id`, `category`, `version`. Prefer defining `name/appid/version/category/author/icon`
  in `application.fam` and keeping the manifest short. Where both exist, `name`, `id`, and
  `version` **must be identical** in the manifest and the fam.
- `version` / `fap_version`: use `major.minor` (e.g. `1.0`). Three-part versions are tolerated
  but two numbers are preferred.
- **One app per pull request.** Do not put two unrelated apps in a single PR.

## 2. Description and changelog (markdown)

`description` and `changelog` can load from a repo file with a leading `@`
(e.g. `description: "@README.md"`). **Without `@`, the value is literal inline text** — a bare
`changelog: changelog.md` will display the words "changelog.md", not the file.

Only a small markdown subset is allowed.

- **Allowed:** H1 and H2 headers, **bold**, _italic_, lists, links (inline and automatic).
- **Not allowed (fails validation):** H3+ headers, setext headers, inline code / backticks,
  code blocks / fenced code, images, raw HTML, HTML entities, blockquotes, horizontal rules,
  reference-style links, tables.

Do not point `description` at a full developer README full of install commands and code blocks —
it will be rejected. Write a short, catalog-specific description (inline, or a dedicated file
like `docs/description.md`) using only the allowed markdown.

## 3. Screenshots — READ CAREFULLY

- Provide **at least one** screenshot. Each must be **exactly 512×256**, **landscape**, and
  **exactly two colors: orange `(254,138,44)` and black `(0,0,0)`** — the qFlipper palette.
- **The correct way is qFlipper's built-in screenshot button.** Take the screenshot in qFlipper
  and commit the PNG **exactly as qFlipper saves it** — no editing, recoloring, resizing,
  rotating, cropping, or converting. The Flipper screen is 1-bit, so a genuine qFlipper export
  is always exactly those two colors.
- **Common rejections (all mean it was NOT a genuine qFlipper export — redo it):**
  - white + black `(255,255,255)+(0,0,0)` — screenshotted or converted somewhere else;
  - off-orange such as `(255,130,0)` — recolored;
  - many colors / anti-aliasing / gradients — recolored, upscaled, or AI-generated;
  - wrong resolution, e.g. `384×192` (that is a 3× scale; qFlipper exports at 4× = 512×256);
  - portrait orientation, e.g. `256×512` — rotated after capture.
- **HID / USB-takeover apps (the important exception):** some apps take over the USB while
  running (USB HID keyboard, CCID smart-card reader, BLE-to-HID bridges, etc.), so qFlipper
  cannot connect to take a screenshot at that moment. For these apps you MAY produce the
  screenshot another way, **but it must use the exact qFlipper palette: only orange
  `(254,138,44)` and black `(0,0,0)`, exactly two colors, 512×256, landscape.** It must be
  indistinguishable from a real qFlipper export: **no white background, no grey/anti-aliased
  edges, no extra colors, no borders, no added text or annotations.** If you render the 128×64
  frame yourself, scale it ×4 with nearest-neighbor and map pixel-on → `(254,138,44)`,
  pixel-off → `(0,0,0)`.

## 4. Icon

- `fap_icon` must be a **10×10, 1-bit PNG**, **black and white only**. No transparency, no greys,
  no anti-aliasing, no other colors.

## 5. App code rules

- **Save paths:** the app may write its files ONLY to its own data directory —
  `APP_DATA_PATH("...")` or `/ext/apps_data/<appid>/...`. Never write to `/ext/apps/...` (that
  folder is for installed `.fap` binaries), to a custom top-level folder (e.g. `/ext/ham`), or
  into another app's directory. Reading shared folders (`/ext/subghz`, `/ext/nfc`,
  `/ext/infrared`) **read-only** is fine when that is the app's purpose (e.g. a Sub-GHz
  analyzer); a dedicated file editor may write back to the folder its files naturally live in.
- **Radio transmit (Sub-GHz, etc.):** any app that transmits MUST gate every transmission on
  `furi_hal_region_is_frequency_allowed(freq)` **and** `furi_hal_subghz_is_frequency_valid(freq)`
  before keying up, and refuse otherwise. Receive-only apps have no region requirement.
- **Crypto:** `furi_hal_crypto` is acceptable as long as you do NOT provision (add) new keys
  into the device secure enclave. If you use it for encryption, be careful which key you use:
  - Reading the **factory-provisioned keys** to derive an encryption key is **unsafe** — those
    keys are identical on every Flipper, so it gives no real protection (anyone can reproduce the
    same key on any device).
  - Instead, check whether the device's **unique U2F key** exists and use that — it is present on
    only that one device and cannot be extracted, so it binds the encrypted data to that single
    device and is reasonably secure (sort of).
  Software crypto (e.g. mbedtls) with a key derived from a user PIN/password is also fine.
- **No destructive or foreign file operations:** only delete or rename files the app itself
  created in its own data directory. Never remove unrelated user files.
- **No memory leaks:** free everything you allocate. Every `*_alloc()` needs a matching
  `*_free()` on the exit path — watch for multiple `storage_file_alloc()`, views, `FuriString`s,
  message queues, etc. (a common bug is allocating two `File`s and freeing only one).
- **English UI by default:** all on-screen text must be English by default; other languages are
  allowed only as a user-selectable option. Use plain ASCII for displayed strings — the Flipper
  font cannot render non-ASCII lookalike glyphs, em-dashes (`—`), ellipses (`…`), accented or
  decorative characters; they show as blank boxes on the device.
- **No dead code or debug leftovers in shipped sources.** "Dead code" here does not mean only
  commented-out code — it also means **live leftover development cruft that was never cleaned
  up**: piles of debug logging left in from development (e.g. lots of verbose `FURI_LOG_D` /
  trace logs), placeholder/example code, dead branches, and unused stubs in the sources that get
  built. Remove or reduce them before submitting. A documented developer template kept in its own
  separate folder (and not compiled into the app) is fine.

## 6. Pull request

- Fill out the Author Checklist and the AI usage disclosure honestly (keep the one option that
  applies to you and delete the others).
- **Do not remove the Reviewer Checklist** or any other section from the PR template.
