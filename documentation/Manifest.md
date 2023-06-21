# Application Manifest

Each application submitted to this catalog is defined by an Application Manifest file called `manifest.yml`. Application manifest is used by bundler script to build application package. Application package is then automatically uploaded to Flipper Application Archivarius, which manages application builds for various SDKs and devices.

Application Manifest must be placed in a corresponding subdirectory of `applications` directory. Full path consists of `applications` directory, [category name](#categories), application id, and `manifest.yml` file.

## Minimal manifest example

Here is a minimal example of an application manifest. It expects some of the fields are specified in `application.fam` file in application's source code repository. Namely, `application.fam` should contain `name`, `appid` (set to "example_subghz_app"), `fap_category` (set to "Sub-GHz"), `fap_version`, `fap_author`, and `fap_icon` fields. 

There should also be "README.md" and "docs/changelog.md" files in the repository, and "screenshots/ss0.png" file.

See [Manifest structure](#manifest-structure) for more details on those fields.

```yaml
sourcecode:
  type: git
  location:
    origin: https://github.com/example/test.git
    commit_sha: bf7019d16d7b50f6a98cc3abdac38c53952a4f30
short_description: Test application
description: "@README.md"
changelog: "@./docs/changelog.md"
screenshots:
  - screenshots/ss0.png
```

This manifest must be placed in `applications/Sub-GHz/example_subghz_app/manifest.yml` file.


## Categories

Your application must be placed in one of the following categories:

 - **Sub-GHz**: Applications that use Sub-GHz radio.
 - **RFID 125**: Applications built for low-frequecy RFID subsystem.
 - **NFC**: Applications for NFC subsystem.
 - **Infrared**: Infrared-related applications.
 - **GPIO**: Applications utilizing GPIO pins.
 - **iButton**: Applications that use iButton/OneWire subsystem.
 - **USB**: USB-related applications.
 - **Games**: Games.
 - **Media**: Media applications.
 - **Tools**: Utility applications.


## Manifest structure

An application manifest is a YAML file that points to the application source code and provides additional information about the application. Note that Required fileds that are not specified in manifest file must be specified in `application.fam` file in application's source code repository. 

| Field | Required? | Description | Corresponding field in `application.fam` |
| --- | --- | --- | --- |
| `sourcecode` | Yes | Source code location. See [Source code location](#source-code-location) | None |
| `screenshots` | Yes | A list of paths to screenshot images in application's source code repo. See [Screenshots](#screenshots). | None |
| `changelog` | Yes | Applicatimon changelog. Supports Markdown formatting and file inclusion. [Details](#loading-values-from-files) | None |
| `short_description` | Yes | Short application description, plain text. | `fap_description` |
| `description` | Yes | Application description. Supports limited Markdown. [Details](#loading-values-from-files) | None |
| `name` | Yes | Application name | `name` |
| `id` | Yes | Application ID. A lowercase string with no spaces. Must be unique | `appid` |
| `category` | Yes | Application category. Must match manifest location within this repo. | `fap_category` |
| `version` | Yes | Application version, in format "major.minor". | `fap_version` |
| `author` | No | Application author | `fap_author` |
| `icon` | No | Application icon. Must be 10x10 1-bit .png file. | `fap_icon` |
| `targets` | No | A list of targets this application supports. See documentation on FAM Application Manifests for more. By default - includes all targets. | `targets` |

It is recommended to specify as many fields as possible in `application.fam` and not in `manifest.yml`, to avoid duplication and keep the manifest file short.

The most important field is `sourcecode`. It points to the application source code repository. The repository must be public. See [Source code location](#source-code-location) for details.

Some fields support loading their values from files in application's source code repository. See [Loading values from files](#loading-values-from-files).

### Source code location

Source code origin is specified in `sourcecode` section. It contains `type` field, which must be set to `git`. It must also contain `location` section, which specifies the source code repository location.

For `location` object, fields `origin` and `commit_sha` are required. 
 * `origin` is the git URL of the repository.
 * `commit_sha` is the commit SHA of the commit that contains the application source code being submitted.
 * `subdir` is optional and specifies the subdirectory within the repository where the application is located. If `subdir` is not specified, the root of the repository is used. This is useful if the repository contains multiple applications.

Example:

```yaml
sourcecode:
  type: git
  location:
    origin: https://github.com/example/test.git
    commit_sha: 520d9f1f04a5fcc67d20c759509ba7fe3d3f9091 
    subdir: metronome
```

### Application Version

Application version is used to determine whether a new version of the application is available for installation on the device. All submitted application updates must use a higher version number than the previous version, otherwise the update will be rejected.

Application version is specified in `version` field. It must be in format `major.minor`. For example, `1.0` or `2.3`. If not specified in YAML manifest, the version is taken from `application.fam` file in application's source code repository. That version is also embedded into the application binary, so to avoid confusion and build errors, it is recommended to specify the version in `application.fam` and not in `manifest.yml`.

### Loading Values from Files

Some fields support loading their values from files in application's source code repository. This is useful for fields that contain large amounts of text, such as `description` or `changelog`.

To load a value from a file, specify the field value as a string starting with `@` followed by the path to the file in application's repository. The path is relative to application's source code folder, which may be specified in `location.subdir` field. Example:

```yaml
...
description: "@README.md"
changelog: "@./docs/changelog.md"
...
```

### Markdown Support

For fields that support loading values from files, Markdown formatting is supported. However, only a subset of Markdown features is allowed:

 - Headers of levels 1-2
 - **Bold** and _italic_ text
 - Lists

## Screenshots

Applications submitted to this catalog must contain at least one screenshot. Screenshots are used to showcase the application in the catalog. Screenshots are specified in `screenshots` section of the manifest. It is a list of screenshot paths.  

**Screenshots must be created using qFlipper's screenshot feature.** Please don't change their resolution or format.
