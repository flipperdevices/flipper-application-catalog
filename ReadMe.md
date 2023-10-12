# Flipper Application Catalog

This is a public repository for community developed applications for Flipper Zero. 

This repository hosts application manifests that contain application metadata and build information. This repository doesn't host applications' source code.

# How to Install an Application

Applications from this repository are automatically built and archived to Flipper Application Mirror. Use Flipper companion apps to search and install apps from this repository:
 - [Download from App Store](https://apps.apple.com/app/flipper-mobile-app/id1534655259)
 - [Download from Google Play](https://play.google.com/store/apps/details?id=com.flipperdevices.app)
 - [Web catalog](https://lab.flipper.net/) _(chromium-based browser required)_

# How to Contribute an Application

Read [contribution guide](documentation/Contributing.md) to learn how to add an application to the catalog.

# How to Report an Issue

If you have found a bug in an application or want to suggent an improvement for it, please contact the application's developer using the contact information provided in the application manifest, or by opening an issue in the application's source code repository.

If you want to report abuse or violation of your rights, please open an issue in this repo with details.

# Structure

- `applications` - Application catalog manifests
- `documentation` - Application Catalog documentation, notes on the build process and architecture
- `tools` - CI/CD tools for workflow automation: verifies application manifest and its code before, creates application code bundles.
