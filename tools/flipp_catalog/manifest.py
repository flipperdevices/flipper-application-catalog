import os
from dataclasses import dataclass, field
from typing import Dict, List
import logging

from dataclass_wizard import YAMLWizard


@dataclass
class CodeLocation:
    type: str
    location: Dict[str, str]


@dataclass
class ApplicationManifest(YAMLWizard, key_transform="SNAKE"):
    sourcecode: CodeLocation
    name: str = ""
    id: str = ""
    author: str = ""
    version: str = ""
    icon: str = ""
    category: str = ""
    short_description: str = ""
    description: str = ""
    changelog: str = ""
    screenshots: List[str] = field(default_factory=list)
    targets: List[str] = field(default_factory=list)

    def sync_from(self, app: "FlipperApplication"):
        field_map = {
            # yaml_field, (app_field, converter, must_match)
            "name": ("name", None, True),
            "id": ("appid", None, True),
            "author": ("fap_author", None, False),
            "category": ("fap_category", None, False),
            "icon": ("fap_icon", None, False),
            "short_description": ("fap_description", None, False),
            "targets": ("targets", None, False),
            # Version matcher error flag must be set to "True" on release
            "version": (
                "fap_version",
                lambda v: ".".join(map(str, v)),
                os.environ.get("BUNDLE_ALLOW_VERSION_MISMATCH", "0") == "0",
            ),
        }

        for yaml_field, (app_field, converter, must_match) in field_map.items():
            current_value = getattr(self, yaml_field)
            fam_value = getattr(app, app_field)
            if converter:
                fam_value = converter(fam_value)

            if type(current_value) != type(fam_value):
                raise BundlerException(
                    f"Type mismatch for {yaml_field}: {type(current_value)} != {type(fam_value)}"
                )

            if current_value and fam_value and current_value != fam_value:
                error_msg = f"Value in YAML for '{yaml_field}' is different from value in FAM: '{current_value}' / '{fam_value}'"
                if must_match:
                    raise BundlerException(error_msg)

                logging.getLogger(self.__class__.__name__).warning(
                    f"{error_msg}. Using value from YAML."
                )
                continue

            if not current_value:
                logging.getLogger(self.__class__.__name__).info(
                    f"Value for '{yaml_field}' is empty in YAML. Using value '{fam_value}' from FAM."
                )
                setattr(self, yaml_field, fam_value)
