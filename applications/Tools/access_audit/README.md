# Flipper Access Audit

A Flipper Zero app for **defensive auditing of NFC and RFID access-control credentials**.

Tap a card, get an instant risk score and plain-English advice. Save a named session report to SD.

> **Authorized use only.** This tool is intended for security professionals, system owners, and researchers assessing systems they own or are permitted to test.

---

## Features

- **Deep card classification** — MIFARE Classic 1K/4K/Mini, DESFire EV1/EV2/EV3/Light, MIFARE Plus SL1/SL2/SL3, Ultralight C, NTAG203/213/215/216, NTAG I2C, ISO14443-A/B, ISO15693, FeliCa, SLIX, ST25TB; 125 kHz RFID: EM4100, HID H10301, HID Generic, Indala; HID iCLASS (Legacy) 2k/16k/32k
- **Instant risk score** — 0–100 score with HIGH RISK / MODERATE / LOW RISK / SECURE label
- **Per-card advice** — plain-English recommendation written to every report entry
- **Multi-scan sessions** — scan up to 20 cards per session with a live counter
- **Named sessions** — optionally label a session before saving using an on-screen QWERTY keyboard
- **SD card reports** — timestamped `.txt` report saved to `/ext/apps_data/access_audit/` with per-card advice and session-level advisory
- **On-device report viewer** — browse and scroll saved reports without leaving the app
- **NFC + RFID + iCLASS** — Left/Right cycles between 13.56 MHz NFC, 125 kHz RFID, and HID iCLASS scanning

---

## Installation

### From release (recommended)

1. Download `access_audit.fap` from the [latest release](https://github.com/matthewkayne/flipper-access-audit/releases/latest)
2. Copy it to `apps/Tools/` on your Flipper's SD card via qFlipper or USB
3. Launch from **Apps → Tools → Access Audit**

### Build from source

Requires [uFBT](https://github.com/flipperdevices/flipperzero-ufbt).

```sh
ufbt
# FAP is written to dist/access_audit.fap
```

---

## Usage

| Screen        | Controls                                                                                       |
| ------------- | ---------------------------------------------------------------------------------------------- |
| Scan          | Tap/hold card · **Left/Right** cycle NFC → RFID → iCLASS · **Up** view reports · **Back** exit |
| Result        | **OK** rescan · **Back** save session and proceed to naming                                    |
| Name session  | QWERTY keyboard · **OK key** save with name · **Back** skip naming / backspace                 |
| Reports list  | **Up/Down** scroll · **OK** open · **Back** return to scan                                     |
| Report viewer | **Up/Down** scroll lines · **Back** return to list                                             |

### Score interpretation

| Label     | Score  | Meaning                                                                               |
| --------- | ------ | ------------------------------------------------------------------------------------- |
| HIGH RISK | 35–100 | Legacy family (MIFARE Classic, EM4100, HID iCLASS, Plus SL1) or static-replay pattern |
| MODERATE  | 20–34  | Risk indicators present — review recommended                                          |
| LOW RISK  | 10–19  | Minor concerns, e.g. incomplete metadata                                              |
| SECURE    | 0–9    | Modern crypto family with no major findings                                           |

### Card classification depth

| Family                   | Sub-types detected                                                     |
| ------------------------ | ---------------------------------------------------------------------- |
| MIFARE Classic           | 1K · 4K · Mini (via SAK byte)                                          |
| MIFARE DESFire           | EV1 · EV2 · EV3 · Light (via GetVersion)                               |
| MIFARE Plus              | SL1 · SL2 · SL3 (via security level response)                          |
| MIFARE Ultralight / NTAG | Ultralight C · NTAG203/213/215/216 · NTAG I2C                          |
| HID iCLASS               | Legacy 2k · Legacy 16k · Legacy 32k (via ACTALL/IDENTIFY/READ block 1) |
| 125 kHz RFID             | EM4100 · HID H10301 · HID Generic · Indala · generic 125 kHz           |

---

## How it works

1. The NFC scanner detects which protocols the card supports.
2. The richest available poller is started (DESFire → Plus → Ultralight → ISO14443-3a).
3. The poller reads the UID and card-specific metadata without authentication — no sectors are unlocked, no data is modified.
4. For HID iCLASS, a proprietary ACTALL → IDENTIFY → SELECT → READ block 1 exchange runs over the ISO15693 RF channel to obtain the CSN and memory variant.
5. The observation is scored against six named rules (see [docs/rules.md](docs/rules.md)).
6. Results are displayed on screen and appended to the session buffer.
7. On save, the session is written as a `.txt` report with per-card advice and a session-level advisory.

---

## Development

- Platform: Flipper Zero (official firmware, Momentum)
- Language: C (uFBT / Flipper SDK)
- CI: GitHub Actions — builds against official release, official dev, Momentum release, and Momentum dev SDKs on every push

```
core/
  observation.h           — data model (TechType, CardType, AccessObservation)
  observation_provider.c  — NFC scan pipeline (scanner + poller state machine)
  rfid_provider.c         — RFID 125 kHz scan pipeline (LFRFIDWorker)
  iclass_provider.c       — HID iCLASS scan pipeline (ISO15693 poller + proprietary exchange)
  rules.c                 — named audit rules
  scoring.c               — score calculator + card-type strings
  session.c               — multi-scan session buffer
  report.c                — SD card save + report listing/loading
access_audit.c            — app loop, screens, input handling
```

---

## Roadmap

- [x] NFC card scan and classification
- [x] Risk scoring with named rules
- [x] Result screen with prominent risk label
- [x] Multi-scan session buffer
- [x] SD card report saving
- [x] Card sub-type detection (Classic 1K/4K/Mini, NTAG213/215/216)
- [x] On-device report viewer
- [x] RFID 125 kHz support (EM4100, HID H10301/Generic, Indala, and more)
- [x] Session summary stats (high/medium/low counts per report)
- [x] Named scan sessions (optional QWERTY keyboard on save)
- [x] DESFire EV1/EV2/EV3/Light detection (via GetVersion)
- [x] MIFARE Plus SL1/SL2/SL3 detection (via security level)
- [x] Per-card advice and session-level advisory in reports
- [x] v1.0.0 stable release
- [x] HID iCLASS scanning with memory variant detection
- [x] Flipper App Catalog submission

---

## License

[MIT](LICENSE)
