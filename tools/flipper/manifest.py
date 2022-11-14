from schema import *

import pathlib
import logging
import yaml
import os

manifest_schema = Schema({
    "application": {
        "name": str,
        "description": str,
        "changelog": str,
        "github_url": str,
        "github_ref": str,
        "target": str,
        Optional("manifest_path"): str,
    }
})

class Manifest:
    def __init__(self, manifest_file:str):
        self.logger = logging.getLogger("Manifest")
        self.manifest_file = manifest_file

    def load(self):
        self.data = yaml.load(open(self.manifest_file, "r"), yaml.Loader)
        try:
            manifest_schema.validate(self.data)
        except SchemaError as se:
            self.logger.error("Invalid Manifest")
            raise se

    def getSources(self):
        pass

    def process(self):
        pass

    def uploadArtifacts(self):
        pass

class ManifestProcessor:
    def __init__(self):
        self.logger = logging.getLogger("ManifestProcessor")

    def load(self, applications_directory:str):
        if not os.path.exists(applications_directory):
            raise Exception("Directory doesn't exists")

        manifests = []
        for namifest_file in pathlib.Path(applications_directory).glob("*/*/manifest.yaml"):
            manifest = Manifest(namifest_file)
            manifest.load()
            manifests.append(manifest)
            print(f">{namifest_file}")

    def process(self):
        pass
