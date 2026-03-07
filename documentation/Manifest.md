# App manifest

Each app submitted to this catalog is defined by an app manifest file called `manifest.yml`. The app manifest is used by the bundler script to build the app package. The app package is then automatically uploaded to Flipper Application Archivarius, which manages app builds for various SDKs and devices.

The app manifest must be placed in a corresponding subdirectory of the `applications` directory. The full path consists of the `applications` directory, [category name](#categories), app ID, and `manifest.yml` file.

## Minimal manifest example

Here is a minimal example of an app manifest. It is expected that some of the fields are specified in the `application.fam` file in the app's source code repository. Namely, `application.fam` should contain `name`, `appid` (set to "example_subghz_app"), `fap_category` (set to "Sub-GHz"), `fap_version`, `fap_author`, and `fap_icon` fields.

The repositofy should also contain `README.md`, `docs/changelog.md` files , and `screenshots/ss0.png` files.

See [Manifest structure](#manifest-structure) for more details on those fields.

```yaml
sourcecode:
  type: git
  location:
    origin: https://github.com/example/test.git
    commit_sha: bf7019d16d7b50f6a98cc3abdac38c53952a4f30
short_description: Test app
description: "@README.md"
changelog: "@./docs/changelog.md"
screenshots:
  - screenshots/ss0.png
```

This manifest must be placed in the `applications/Sub-GHz/example_subghz_app/manifest.yml` file.


## Categories

Your app must be placed in one of the following categories:

 - **Sub-GHz**: Apps that use Sub-GHz radio.
 - **RFID**: Apps built for low-frequency RFID subsystem.
 - **NFC**: Apps for NFC subsystem.
 - **Infrared**: Infrared-related apps.
 - **GPIO**: Apps utilizing GPIO pins.
 - **iButton**: Apps that use iButton/OneWire subsystem.
 - **USB**: USB-related apps.
 - **Games**: Games.
 - **Media**: Media apps.
 - **Tools**: Utility apps.
 - **Bluetooth**: Bluetooth LE apps.


## Manifest structure

An app manifest is a YAML file that points to the app's source code and provides additional information about the app. Note that Required fields that are not specified in the manifest file must be specified in the `application.fam` file in the app's source code repository.

| Field | Required? | Description | Corresponding field in `application.fam` |
| --- | --- | --- | --- |
| `sourcecode` | Yes | Source code location. See [Source code location](#source-code-location). | None |
| `screenshots` | Yes | A list of paths to screenshot images in app's source code repo. See [Screenshots](#screenshots). | None |
| `changelog` | Yes | App changelog. Supports Markdown formatting and file inclusion. [Details](#loading-values-from-files). | None |
| `short_description` | Yes | Short app description, plain text. | `fap_description` |
| `description` | Yes | App description. Supports limited Markdown. [Details](#loading-values-from-files). | None |
| `name` | Yes | App name. | `name` |
| `id` | Yes | App ID. A lowercase string with no spaces. Must be globally unique. | `appid` |
| `category` | Yes | App category. Must match manifest location within this repo. | `fap_category` |
| `version` | Yes | App version, in format "major.minor". | `fap_version` |
| `author` | No | App author. | `fap_author` |
| `icon` | No | App icon. Must be 10x10px 1-bit .png file. | `fap_icon` |
| `targets` | No | A list of targets this app supports. See [documentation on FAM App Manifests](https://developer.flipper.net/flipperzero/doxygen/app_manifests.html) for more. By default - includes all targets. | `targets` |

**It is recommended to specify as many fields as possible in `application.fam` and not in `manifest.yml`, to avoid duplication and keep the manifest file short.**

If your `application.fam` defines multiple apps, you can specify the app ID in `manifest.yml` using the `id` field.

The most important field is `sourcecode`. It points to the app's source code repository. The repository must be public. See [Source code location](#source-code-location) for details.

Some fields support loading their values from files in the app's source code repository. See [Loading values from files](#loading-values-from-files).

### Source code location

The source code origin is specified in the `sourcecode` section. It contains the `type` field, which must be set to `git`. It must also contain the `location` section, which specifies the source code repository location.

For the `location` object, fields `origin` and `commit_sha` are required.
 * `origin` is the git URL of the repository.
 * `commit_sha` is the commit SHA of the commit that contains the app's source code being submitted.
 * `subdir` is optional and specifies the subdirectory within the repository where the app is located. If `subdir` is not specified, the root of the repository is used. This is useful if the repository contains multiple apps.

Example:

```yaml
sourcecode:
  type: git
  location:
    origin: https://github.com/example/test.git
    commit_sha: 520d9f1f04a5fcc67d20c759509ba7fe3d3f9091
    subdir: metronome
```

### App version

The app version is used to determine whether a new version of the app is available for installation on the device. All submitted app updates must use a higher version number than the previous version, otherwise the update will be rejected.

The app version is specified in the `version` field. It must be in format `major.minor`. For example, `1.0` or `2.3`. If not specified in the YAML manifest, the version is taken from `application.fam` file in the app's source code repository. That version is also embedded into the app binary, so to avoid confusion and build errors, it is recommended to specify the version in `application.fam` and not in `manifest.yml`.

### Loading values from files

Some fields support loading their values from files in the app's source code repository. This is useful for fields that contain large amounts of text, such as `description` or `changelog`.

To load a value from a file, specify the field value as a string starting with `@` followed by the path to the file in the app's repository. The path is relative to the app's source code folder, which may be specified in the `location.subdir` field. Example:

```yaml
...
description: "@README.md"
changelog: "@./docs/changelog.md"
...
```

### Markdown support

For fields that support loading values from files, Markdown formatting is supported. However, only a subset of Markdown features is allowed:

 - Headers of levels 1-2
 - **Bold** and _italic_ text
 - Lists
 - Links - automatic and inline

## Screenshots

Apps submitted to the Flipper Apps Catalog must contain at least one screenshot. Screenshots are used to showcase the app in the Apps Catalog. Screenshots are specified in the `screenshots` section of the manifest as a list of screenshot paths.

**Screenshots must be created using the qFlipper screenshot feature.** Please don't change their resolution or format.

## Validating manifest

You can check your manifest file for validity. To do so, set up a virtual Python environment with the required dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r tools/requirements.txt
```
*Hint 1.* Above is the Linux-way of doing it. For instance in Windows Power-shell, activating the phython-environment is done with `.\venv\Scripts\Activate.ps1`. 
*Hint 2.* The `tools/requirements.txt` is obviously located in your local repo `flipper-application-catalog`.

If you haven't yet installed the SDK for `ufbt` for your current user, you can install one within the virtual environment.

```bash
export UFBT_HOME=`realpath venv/ufbt`
ufbt update
```

Then run the validation script, passing it the path to your manifest file:

```bash
python3 tools/bundle.py --nolint applications/CATEGORY/APPID/manifest.yml bundle.zip
```

If there are any errors, the script will print them and exit with non-zero exit code. **Be sure to fix all errors before submitting your app.**
