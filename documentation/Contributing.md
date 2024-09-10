# Contribution Guide

Thanks for taking an interest in contributing to the Flipper Apps Catalog. The Apps Catalog is a centralized repository for users to discover, download, and share community-developed apps for Flipper Zero. We welcome contributions from anyone as long as they meet the terms and requirements described below.


## General Terms and Requirements

 * Applications submitted to this repository must be licensed under an Open Source License of your choice, permitting building and distribution of the application in binary form by the Flipper Apps Catalog's infrastructure.
 * Applications and data they produce or process must not infringe on any third-party rights or trademarks.
 * Submitted applications must not contain any malicious code or code that may cause harm to the user's device or data.
 * Applications must comply with the User-Generated Content Policies of [Play Store](https://support.google.com/googleplay/android-developer/answer/9876937) and [App Store](https://developer.apple.com/app-store/review/guidelines/#user-generated-content).
    * We reserve the right to reject and remove applications that do not comply with these policies.
 * If any changes to the application metadata or source code are required, we will contact the application author, as specified in the of submitted pull request or using the contact information provided in the manifest file. If we do not receive a response within 14 days, the application will be removed from the Catalog.
    * If immediate changes are required to address a security vulnerability, copyright or other critical issue, we reserve the right to unpublish the application from the Catalog before contacting the author.
 * We also reserve the right to reject and unpublish applications that do not comply with these terms and requirements, or for any other reason at any time.

Applications are submitted as a pull request to this repository.

 * The pull request must contain a [manifest file](./Manifest.md) with a link to the application source code repository and additional information, such as application name, description, author, screenshots, etc. 
 * The application source code must be hosted in a public Git repository. We currently only accept applications hosted on GitHub.


## Adding and Updating Applications

To submit an application, fork this repository, add your application manifest and create a pull request, filling in the pull request template. You may also include a `README.md` file with additional information about the application in the same directory as the manifest.

The recommended naming scheme for your branch is `<username>/<appid>_<appversion>`, where `username` is your GitHub username, `appid` is your application ID and `appversion` is your application's version. For example, `johndoe/myapp_1.0`.

Updating an application is done in the same way. Note that each submission must have a unique version. If you want to update an application, increment the version number in application's build system manifest (`application.fam`) in the source code repo. See [manifest format description](./Manifest.md#application-version) for details.

# Technical Requirements

Applications must be buildable with [uFBT](https://pypi.org/project/ufbt/) and compatible with the latest Release or Release Candidate firmware version at the moment of submission.

Application submission consists of two parts:
 - Application manifest: `applications/<category>/<application-id>/manifest.yml`, with all mandatory fields filled in. See [manifest format](./Manifest.md) for details.
 - An optional `README.md` file with additional information about the application in the same directory as the manifest.

### Validating Manifest

You can check your manifest file for validity before submitting it to this repository. To do so, set up a virtual Python environment with the required dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r tools/requirements.txt
```

If you haven't yet installed the SDK for `ufbt` for your current user, you can install one within the virtual environment.

```bash
export UFBT_HOME=`realpath venv/ufbt`
ufbt update
```

Then run the validation script, passing it the path to your manifest file:

```bash
python3 tools/bundle.py --nolint applications/CATEGORY/APPID/manifest.yml bundle.zip
```

If there are any errors, the script will print them and exit with non-zero exit code. **Be sure to fix all errors before submitting your application.**
