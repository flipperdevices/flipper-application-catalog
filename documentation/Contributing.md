# General Requirements

Applications submitted to this repository must be open source and licensed under a permissive license (MIT, BSD, Apache, etc). The application source code must be hosted in a public Git repository. 

Applications are submitted as a pull request to this repository. The pull request must contain a manifest file with a link to the application source code repository and additional information, such as application name, description, author, screenshots, etc. 

You can also include a `README.md` file with additional information about the application in the same directory as the manifest.

# Adding and Updating Applications

To submit an application, fork this repository, add your application manifest and create a pull request, filling in the pull request template.

Recommended naming scheme for your branch is `<username>/<appid>_<appversion>`, where `username` is your GitHub username, `appid` is your application ID and `appversion` is your application's version. For example, `johndoe/myapp_1.0`.

Updating an application is done in the same way. Note that each submission must have a unique version. If you want to update an application, increment the version number in application's build system manifest (`application.fam`) in source code repo. See [manifest format description](./Manifest.md#application-version) for details.

# Technical Requirements

Applications must be buildable with [ufbt](https://pypi.org/project/ufbt/) and compatible with latest Release or Release Candidate firmware version at the moment of submission.

Application submission consists of two parts:
 - Application manifest: `applications/<category>/<application-id>/manifest.yml`, with all mandatory fields filled in. See [manifest format](./Manifest.md) for details.
 - An optional `README.md`` file with additional information about the application in the same directory as the manifest.

## Validating Manifest

You can check your manifest file for validity before submitting it to this repository. To do so, set up a virtual Python environment with required dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r tools/requirements.txt
```

Then run the validation script:

```bash
python3 tools/bundle.py applications/.../manifest.yml bundle.zip
```

If there are any errors, the script will print them and exit with non-zero exit code.
