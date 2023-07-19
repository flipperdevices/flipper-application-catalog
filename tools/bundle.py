import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

import yaml

# import markdown2
from dataclass_wizard import YAMLWizard
from dataclass_wizard.dumpers import asdict
from git import Repo
from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import HtmlBlockPreprocessor
from PIL import Image

# import markdown


class BundlerException(Exception):
    pass


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


# A Markdown extension that removes all but basic text formatting
class BasicTextExtension(Extension):
    ERROR_MESSAGE = "Markdown element '{}' is not allowed"
    MAX_HEADER_DEPTH = 2

    def __init__(self, **kwargs):
        # override the html preprocessor to avoid html text conversion so as not to be skipped by HtmlInlineProcessor
        HtmlBlockPreprocessor.run = lambda _self, lines: lines
        super().__init__(**kwargs)

    @staticmethod
    def handleMatch(element_type):
        def wrapper(instance, m):
            raise Exception(BasicTextExtension.ERROR_MESSAGE.format(element_type))

        return wrapper

    @staticmethod
    def not_supported_reference_processor_wrapper(instance, method):
        def wrapper(parent, block):
            res = method(parent, block)

            if res:
                raise Exception(BasicTextExtension.ERROR_MESSAGE.format("Reference"))

            return False

        return wrapper

    @staticmethod
    def not_supported_block_processor_wrapper(instance, name=None):
        def wrapper(parent, block):
            raise Exception(
                BasicTextExtension.ERROR_MESSAGE.format(
                    name or instance.__class__.__name__
                )
            )

        return wrapper

    @staticmethod
    def not_supported_header_depth_processor_wrapper(instance):
        orig_run = instance.run

        def wrapper(parent, blocks):
            if m := instance.RE.match(blocks[0]):
                header_depth = len(m.group("level"))
                if header_depth > BasicTextExtension.MAX_HEADER_DEPTH:
                    raise Exception(
                        f"Markdown element 'Header Depth' max level {BasicTextExtension.MAX_HEADER_DEPTH} exceeded"
                    )

            return orig_run(parent, blocks)

        return wrapper

    def extendMarkdown(self, md):
        for md_element in (
            "backtick",
            # "reference",
            # "link",
            "image_link",
            "image_reference",
            "short_reference",
            "short_image_ref",
            # "autolink",
            "automail",
            "html",
            "entity",
        ):
            md.inlinePatterns[md_element].handleMatch = self.handleMatch(
                md_element.capitalize()
            )

        hash_header_processor = md.parser.blockprocessors["hashheader"]
        hash_header_processor.run = self.not_supported_header_depth_processor_wrapper(
            instance=hash_header_processor
        )

        setext_header_processor = md.parser.blockprocessors["setextheader"]
        setext_header_processor.run = self.not_supported_block_processor_wrapper(
            instance=setext_header_processor, name="Setext Header"
        )

        code_block_processor = md.parser.blockprocessors["code"]
        code_block_processor.run = self.not_supported_block_processor_wrapper(
            instance=code_block_processor, name="Code Block"
        )

        hr_processor = md.parser.blockprocessors["hr"]
        hr_processor.run = self.not_supported_block_processor_wrapper(
            instance=hr_processor, name="Horizontal Line"
        )

        quote_processor = md.parser.blockprocessors["quote"]
        quote_processor.run = self.not_supported_block_processor_wrapper(
            instance=quote_processor, name="Quote"
        )

        reference_processor = md.parser.blockprocessors["reference"]
        reference_processor.run = self.not_supported_reference_processor_wrapper(
            instance=reference_processor, method=reference_processor.run
        )


class AppBundler:
    MANIFEST_YAML_NAME = "manifest.yml"
    UFBT_COMMAND = "ufbt"
    FLIPPER_SCREEN_SIZE = (128, 64)
    APP_SCREENSHOT_DOWNSCALE_FACTORS = (4, 8)
    FLIPPER_ICON_SIZE = (10, 10)
    APP_ID_REGEX = re.compile(r"^[a-z0-9_]+$")

    def __init__(self, manifest_yaml_path: str, bundle_path: str):
        self._log = logging.getLogger(self.__class__.__name__)
        self._manifest_yaml_path = manifest_yaml_path
        self._bundle_path = bundle_path
        self._tmp_dir = TemporaryDirectory()
        self._tmp_path = Path(self._tmp_dir.name).resolve()
        self._tmp_code_dir = TemporaryDirectory()
        self._tmp_code_path = Path(self._tmp_code_dir.name).resolve()
        self._code_dir = self._tmp_path / "code"
        self._assets_dir = self._tmp_path / "assets"
        self._assets_dir.mkdir()
        self._repo = None
        self._fam_manifest = None
        self._log.info(f"Working in '{self._tmp_path}'")
        self._load()

    def bundle(
        self,
        *,
        skip_lint: bool = False,
        skip_build: bool = False,
        skip_source_code: bool = False,
    ):
        self._fetch_sources()
        if not skip_lint:
            self._lint_sources()
        if not skip_build:
            self._build_sources()
        self._update_manifest_from_fap()
        self._check_manifest_path()
        self._process_includes()
        self._process_assets()
        self._check_manifest_values()
        self._build_package(skip_source_code)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.cleanup()

    def cleanup(self):
        self._tmp_dir.cleanup()
        self._tmp_code_dir.cleanup()

    def _load(self):
        try:
            self._manifest = ApplicationManifest.from_yaml_file(
                self._manifest_yaml_path
            )
        except FileNotFoundError:
            raise BundlerException(f"File '{self._manifest_yaml_path}' not found")
        except yaml.YAMLError as e:
            raise BundlerException(f"YAML error: {e}")
        self._log.info(f"Loaded app manifest from {self._manifest_yaml_path}")
        self._log.debug(self._manifest)

    def _validate_path(self, path: Path):
        self._log.debug(f"Validating path: {path} vs {self._tmp_path}")
        if not path.exists():
            raise BundlerException(f"Path not found: {path}")
        if not path.resolve().is_relative_to(self._tmp_path):
            raise BundlerException(f"Path traversal detected: {path}")

    def _rel_path(self, path: Path):
        self._validate_path(path)
        return path.relative_to(self._tmp_path).as_posix()

    def _fetch_sources(self):
        if self._manifest.sourcecode.type != "git":
            raise BundlerException(
                f"Unknown sourcecode type: {self._manifest.sourcecode.type}"
            )

        location_data = self._manifest.sourcecode.location
        repo_origin = location_data["origin"]
        self._log.info(f"Cloning {repo_origin} to {self._tmp_code_path}")
        self._repo = Repo.clone_from(
            repo_origin,
            self._tmp_code_path,
            multi_options=["--recurse-submodules"],
        )
        self._log.info("Cloned")

        if not (commit_sha := location_data.get("commit_sha")):
            raise BundlerException(
                f"Commit SHA (sourcecode.location.commit_sha) not specified for {repo_origin}"
            )

        if len(commit_sha) != 40:
            raise BundlerException(
                f"Commit SHA (sourcecode.location.commit_sha) for {repo_origin} is not 40 characters long"
            )

        code_branch = self._repo.create_head("_catalog_app_version", commit_sha)
        self._repo.head.reference = code_branch
        self._repo.head.reset(index=True, working_tree=True)

        self._log.info(f"Checked out commit {commit_sha}")
        repo_code = self._tmp_code_path
        if sub_dir := location_data.get("subdir"):
            repo_code = repo_code / sub_dir

        if not repo_code.resolve().is_relative_to(self._tmp_code_path):
            raise BundlerException(
                f"Code path traversal detected: {repo_code} vs {self._tmp_code_path}"
            )
        self._log.info(f"Moving {repo_code} to {self._code_dir}")
        shutil.move(repo_code, self._code_dir)

    def _lint_sources(self):
        try:
            self._log.info("Linting")
            subprocess.check_output([self.UFBT_COMMAND, "lint"], cwd=self._code_dir)
        except subprocess.CalledProcessError as e:
            raise BundlerException(f"Code checks failed: {e.output}")

    def _build_sources(self):
        try:
            self._log.info("Building")
            subprocess.check_output([self.UFBT_COMMAND], cwd=self._code_dir)
        except subprocess.CalledProcessError as e:
            raise BundlerException(f"Code checks failed: {e.output}")

    def _update_manifest_from_fap(self):
        app_manifest_path = self._code_dir / "application.fam"
        if not os.path.exists(app_manifest_path):
            raise BundlerException("Application manifest not found")

        from fbt.appmanifest import AppManager, FlipperAppType

        app_manager = AppManager()
        app_manager.load_manifest(app_manifest_path, self._code_dir)

        known_ext_apps = list(
            filter(
                lambda app: app.apptype == FlipperAppType.EXTERNAL,
                app_manager.known_apps.values(),
            )
        )

        if len(known_ext_apps) == 0:
            raise BundlerException("No external applications found")
        elif len(known_ext_apps) == 1:
            self._fam_manifest = known_ext_apps[0]
        else:
            if app := next(
                filter(lambda app: app.appid == self._manifest.id, known_ext_apps),
                None,
            ):
                self._log.info(f"Selected application {app.name}")
                self._fam_manifest = app
            else:
                raise BundlerException(
                    f"Multiple external applications found, specify 'id' in the manifest.yml ({[app.appid for app in known_ext_apps]})"
                )

        self._manifest.sync_from(self._fam_manifest)

    def _process_includes(self):
        for attr_name in ("changelog", "description"):
            if attr_value := getattr(self._manifest, attr_name):
                if attr_value.startswith("@"):
                    file_path = self._code_dir / attr_value[1:]
                    self._validate_path(file_path)
                    self._log.info(f"Including {attr_name} from file {file_path}")
                    with open(file_path, "r") as f:
                        setattr(self._manifest, attr_name, f.read())

        self._log.debug(f"Updated: {self._manifest}")

    def __process_screenshot(
        self, screenshot_src_path: Path, screenshot_dst_path: Path
    ):
        self._validate_path(screenshot_src_path)
        # Check image type / downsize x4 and convert to transparent png
        img = Image.open(screenshot_src_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        # TODO: guess downsize ratio?
        downscale_factors = (
            img.width // self.FLIPPER_SCREEN_SIZE[0],
            img.height // self.FLIPPER_SCREEN_SIZE[1],
        )
        if (
            downscale_factors[0] != downscale_factors[1]
            or downscale_factors[0] not in self.APP_SCREENSHOT_DOWNSCALE_FACTORS
        ):
            raise BundlerException(
                f"Screenshot {screenshot_src_path} has resolution {img.width}x{img.height}, "
                f"downscaled to {downscale_factors[0]}x{downscale_factors[1]}, "
                f"expected {self.FLIPPER_SCREEN_SIZE[0]}x{self.FLIPPER_SCREEN_SIZE[1]}"
            )

        downscaled_resolution = (
            img.width // downscale_factors[0],
            img.height // downscale_factors[1],
        )
        if downscaled_resolution != self.FLIPPER_SCREEN_SIZE:
            raise BundlerException(
                f"Screenshot {screenshot_src_path} has resolution {img.width}x{img.height}, "
                f"downscaled to {downscaled_resolution[0]}x{downscaled_resolution[1]}, "
                f"expected {self.FLIPPER_SCREEN_SIZE[0]}x{self.FLIPPER_SCREEN_SIZE[1]}"
            )

        img = img.resize(downscaled_resolution, resample=Image.Resampling.NEAREST)
        # Set all non-black pixels to transparent
        img.putdata(
            tuple(
                (255, 255, 255, 0) if pixel[:3] != (0, 0, 0) else pixel
                for pixel in img.getdata()
            )
        )
        img.save(screenshot_dst_path, "PNG")

    def __process_icon(self, icon_src_path: Path, icon_dst_path: Path):
        self._validate_path(icon_src_path)
        # Check image type and size and convert to transparent png
        img = Image.open(icon_src_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if img.size != self.FLIPPER_ICON_SIZE:
            raise BundlerException(
                f"Icon {icon_src_path} has resolution {img.width}x{img.height}, "
                f"expected {self.FLIPPER_ICON_SIZE[0]}x{self.FLIPPER_ICON_SIZE[1]}"
            )
        # Set all non-black pixels to transparent
        img.putdata(
            tuple(
                (255, 255, 255, 0) if pixel[:3] != (0, 0, 0) else pixel
                for pixel in img.getdata()
            )
        )
        img.save(icon_dst_path, "PNG")

    def _process_assets(self):
        icon_path = self._assets_dir / "icon.png"
        src_icon_path = self._code_dir / self._fam_manifest.fap_icon
        self._validate_path(src_icon_path)
        self.__process_icon(src_icon_path, icon_path)
        self._manifest.icon = self._rel_path(icon_path)

        screenshot_dir = self._assets_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        new_screenshot_paths = []
        for i, screenshot in enumerate(self._manifest.screenshots):
            new_screenshot_path = (
                screenshot_dir / f"{i}{os.path.splitext(screenshot)[1]}"
            )
            self.__process_screenshot(self._code_dir / screenshot, new_screenshot_path)
            new_screenshot_paths.append(self._rel_path(new_screenshot_path))

        if len(new_screenshot_paths) == 0:
            raise BundlerException("No screenshots found")

        self._manifest.screenshots = new_screenshot_paths

    def _check_manifest_path(self):
        # Extract path components from self._manifest_yaml_path
        manifest_path_components = Path(self._manifest_yaml_path).parts
        # Find next to component called "applications", if there is one
        try:
            app_folder_index = manifest_path_components.index("applications")
        except ValueError:
            app_folder_index = -1
            self._log.info("Skipping category check, no 'applications' folder found")
        # If there is one, check that it matches the one in the manifest
        if app_folder_index != -1:
            try:
                path_category = manifest_path_components[app_folder_index + 1]
                path_app_id = manifest_path_components[app_folder_index + 2]
                manifest_name = manifest_path_components[app_folder_index + 3]
            except IndexError:
                raise BundlerException(
                    f"Invalid path to manifest: {self._manifest_yaml_path}"
                )

            if manifest_name != self.MANIFEST_YAML_NAME:
                raise BundlerException(
                    f"Manifest file name '{manifest_name}' does not match "
                    f"expected name '{self.MANIFEST_YAML_NAME}'"
                )
            if self._manifest.id != path_app_id:
                raise BundlerException(
                    f"App ID '{self._manifest.id}' in manifest does not match "
                    f"app ID '{path_app_id}' from path '{self._manifest_yaml_path}'"
                )
            if self._manifest.category != path_category:
                raise BundlerException(
                    f"App category '{self._manifest.category}' in manifest does not match "
                    f"category '{path_category}' from path '{self._manifest_yaml_path}'"
                )

    def _check_manifest_values(self):
        errors = []

        if not self.APP_ID_REGEX.match(self._manifest.id):
            errors.append(
                f"App ID '{self._manifest.id}' does not match regex "
                f"{self.APP_ID_REGEX.pattern}"
            )

        if not self._manifest.changelog:
            errors.append(f"Changelog is empty")

        if not self._manifest.short_description:
            errors.append(f"Short description is empty")

        if not self._manifest.description:
            errors.append(f"Description is empty")

        if errors:
            raise BundlerException("\n".join(errors))

        self.__check_markdown(self._manifest.changelog)
        self.__check_markdown(self._manifest.description)

    def __check_markdown(self, markdown: str):
        try:
            mk = Markdown(extensions=[BasicTextExtension()])
            mk.convert(markdown)

        except Exception as e:
            raise BundlerException(f"Markdown error: {e}")

    def _build_package(self, skip_source_code: bool = False):
        self._log.info(f"Saving updated manifest: {skip_source_code}")
        self._manifest.to_yaml_file(self._tmp_path / self.MANIFEST_YAML_NAME)

        if skip_source_code:
            self._log.info("Removing source code")
            shutil.rmtree(self._code_dir)

        with zipfile.ZipFile(
            self._bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as new_zip:
            for folder, subfolders, filenames in os.walk(self._tmp_path):
                # Exclude hidden folders and "dist" folder with build artifacts
                for folder_name in subfolders.copy():
                    if folder_name.startswith(".") or folder_name == "dist":
                        self._log.debug(f"Skipping folder {filename}")
                        subfolders.remove(folder_name)

                for filename in filenames:
                    if filename.startswith("."):
                        self._log.debug(f"Skipping hidden file {filename}")
                        continue
                    file_path = Path(os.path.join(folder, filename))
                    self._log.debug(f"Adding {file_path}")
                    new_zip.write(file_path, self._rel_path(file_path))

        self._log.info(f"Bundle created: {self._bundle_path}")

    def write_manifest_json(self, manifest_path: Path):
        self._log.info(f"Writing JSON manifest: {manifest_path}")
        with open(manifest_path, "w") as f:
            json.dump(asdict(self._manifest), f, indent=4)


class Main:
    def __init__(self, no_exit=False):
        # Argument Parser
        # Logging
        self.logger = logging.getLogger()
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="Debug",
        )
        self.parser.add_argument(
            "manifest_path",
            type=Path,
            help="Path to the manifest file",
        )
        self.parser.add_argument(
            "bundle_zip_path",
            type=Path,
            help="Path to the bundle file",
        )
        self.parser.add_argument(
            "--nobuild",
            action="store_true",
            default=False,
            help="Skip building the application",
        )
        self.parser.add_argument(
            "--nolint",
            action="store_true",
            default=False,
            help="Skip linting the application",
        )
        self.parser.add_argument(
            "--nosourcecode",
            action="store_true",
            default=False,
            help="Skip source code of the application",
        )
        self.parser.add_argument(
            "--json-manifest",
            dest="json",
            default="",
            help="File to write extra manifest copy in JSON format to",
        )

    def main(self):
        return self.process(self.parser.parse_args())

    def _setup_imports(self):
        try:
            ufbt_state_dir = subprocess.check_output(
                [AppBundler.UFBT_COMMAND, "status", "sdk_dir"], encoding="utf-8"
            ).strip()
        except subprocess.CalledProcessError as e:
            raise BundlerException(f"Could not find ufbt state dir: {e}")

        fbt_scripts_dir = Path(ufbt_state_dir) / "scripts"
        if not fbt_scripts_dir.exists():
            raise BundlerException(f"Could not find fbt scripts dir: {fbt_scripts_dir}")

        self.logger.debug(f"Using fbt scripts dir: {fbt_scripts_dir}")
        sys.path.insert(0, str(fbt_scripts_dir))

    def process(self, args):
        try:
            self._setup_imports()
            with AppBundler(args.manifest_path, args.bundle_zip_path) as bundler:
                bundler.bundle(
                    skip_lint=args.nolint,
                    skip_build=args.nobuild,
                    skip_source_code=args.nosourcecode,
                )
                if args.json:
                    bundler.write_manifest_json(args.json)
                return 0
        except BundlerException as e:
            self.logger.error(e)
            if args.debug:
                self.logger.exception(e)
            return 1


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname).1s] %(message)s",
        level=logging.INFO,
        datefmt="%H:%M:%S",
    )

    sys.exit(Main().main())
