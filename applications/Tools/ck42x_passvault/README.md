# CK42X PassVault

Catalog manifest for [CK42X PassVault](https://github.com/lordbuffcloud/flipper-ck42x-passvault), a Flipper Zero external app for PIN-gated encrypted password storage, saved-entry editing, RNG password generation, explicit opt-in USB HID password typing, macOS ANSI keyboard setup, and experimental FIDO2 WebAuthn registration and authentication.

Security note: PassVault stores passwords and FIDO credentials in separate AES-GCM encrypted app-data files behind the master PIN. It remains an experimental, unaudited Flipper utility. Flipper Zero has no secure element, and this build is not FIDO certified. Keep a backup authenticator and account recovery method.
