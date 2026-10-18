# Telink SWS

Catalog entry for [ngxson/flipper-telink](https://github.com/ngxson/flipper-telink),
with application sources in `telink_sws/`.

The name, app ID, category, version, short description, and icon are inherited
from `application.fam`. The description and changelog are inline in the catalog
manifest, so the developer README's HTML and code formatting are not imported.

## Screenshots

The user's original qFlipper exports are copied unchanged into the app's
`screenshots/` directory:

- `screenshot1.png`: CONTACT OK, chip 5562 running; the catalog preview image.
- `screenshot0.png`: NO CONTACT, automatic CPU halt disabled.

Both are 512 by 256 pixels and use exactly black and orange RGB (254, 138, 44).
Both files are included in the pinned source commit.

## Draft status

The manifest currently pins source commit
`9e1f192d417cf23a7bffa23e679fc52f5261854c`. It is a local draft, not a validated
submission. Before submitting:

- Add an explicit open-source license covering the app and permitting binary
  distribution. The current app source has no license file.
- Save `telink_sws/sws-icon.png` as a 1-bit black-and-white PNG without
  transparency, preserving the user's artwork. The current image is a
  two-color paletted PNG.
- Build and test with the latest official Release or Release Candidate SDK.
  The existing verified build uses Unleashed API 87.8. Use a separate SDK
  directory so the hardware-matched project SDK is preserved.
- Make dump output comply with the catalog's app-data rule. The current CLI
  accepts arbitrary output paths; catalog output must stay under
  `/ext/apps_data/telink_sws/`.
- After any further source changes are published, update `commit_sha`
  to the full commit containing them. Do not submit a manifest referencing
  assets that exist only in a local working tree.

## Validation

From the catalog repository root, with its Python requirements installed:

```sh
UFBT_HOME=/tmp/telink-sws-catalog-sdk python3 tools/bundle.py --nolint \
  applications/GPIO/telink_sws/manifest.yml /tmp/telink-sws-catalog-bundle.zip
```

The bundler fetches the pinned GitHub commit and updates its selected SDK.
Both referenced screenshots are present in the pinned source commit.
Follow [the catalog contribution guide](../../../documentation/Contributing.md)
and [manifest requirements](../../../documentation/Manifest.md).
