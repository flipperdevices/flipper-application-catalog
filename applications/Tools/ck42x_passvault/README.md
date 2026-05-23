# CK42X PassVault

Catalog manifest for [CK42X PassVault](https://github.com/lordbuffcloud/flipper-ck42x-passvault), a Flipper Zero external app for PIN-gated encrypted password storage, RNG password generation, and explicit opt-in USB HID password typing.

Security note: v0.4 stores the active vault as AES-GCM encrypted app data and requires a master PIN, but it is still an unaudited Flipper utility. A compromised device, weak PIN, shoulder surfing, debug access, or modified firmware can still expose vault contents.
