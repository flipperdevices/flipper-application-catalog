import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

import yaml
from dataclass_wizard.dumpers import asdict
from flipp_catalog.manifest import ApplicationManifest
from flipp_catalog.markdown_filter import BasicFormattingEnforcingExtension
from markdown import Markdown
from PIL import Image

# Temporary hack
try:
    import SCons
    import SCons.Node
except ImportError:
    import sys

    class _fbt_util_stub:
        @staticmethod
        def resolve_real_dir_node(node):
            return node

    sys.modules["fbt.util"] = _fbt_util_stub


class BundlerException(Exception):
    pass


class AppBundler:
    MANIFEST_YAML_NAME = "manifest.yml"
    UFBT_COMMAND = "ufbt"
    APP_ID_REGEX = re.compile(r"^[a-z0-9_]+$")
    FLIPPER_SCREEN_SIZE = (128, 64)
    APP_SCREENSHOT_DOWNSCALE_FACTORS = (4, 8)
    FLIPPER_ICON_SIZE = (10, 10)
    BLACK_THRESHOLD = (15, 15, 15)
    PIXEL_BLACK = (0, 0, 0, 255)
    PIXEL_TRANSPARENT = (255, 255, 255, 0)

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

    def __exec_git(self, *args, **kwargs):
        return subprocess.check_output(
            ["git", *args], cwd=self._tmp_code_path, **kwargs
        )

    def _fetch_sources(self):
        if self._manifest.sourcecode.type != "git":
            raise BundlerException(
                f"Unknown sourcecode type: {self._manifest.sourcecode.type}"
            )

        location_data = self._manifest.sourcecode.location
        repo_origin = location_data["origin"]

        if not (commit_sha := location_data.get("commit_sha")):
            raise BundlerException(
                f"Commit SHA (sourcecode.location.commit_sha) not specified for {repo_origin}"
            )

        if len(commit_sha) != 40:
            raise BundlerException(
                f"Commit SHA (sourcecode.location.commit_sha) for {repo_origin} is not 40 characters long"
            )

        self._log.info(f"Cloning {repo_origin} to {self._tmp_code_path}")
        self.__exec_git(
            "clone", repo_origin, self._tmp_code_path, "--recurse-submodules"
        )

        self._log.info(f"Cloned. Checking out commit {commit_sha}")
        self.__exec_git("-c", "advice.detachedHead=false", "checkout", commit_sha)

        self._log.info(f"Checked out. Updating submodules")
        self.__exec_git("submodule", "update", "--init", "--recursive")

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
            raise BundlerException(f"Code checks failed: {str(e.output, 'utf-8')}")

    def _build_sources(self):
        try:
            self._log.info("Building")
            subprocess.check_output([self.UFBT_COMMAND], cwd=self._code_dir)
        except subprocess.CalledProcessError as e:
            raise BundlerException(f"Code checks failed: {str(e.output, 'utf-8')}")

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

    def __convert_image_pixels(self, img: Image):
        # Set all pixels above threshold to transparent
        img.putdata(
            tuple(
                (
                    self.PIXEL_TRANSPARENT
                    if pixel[:3] > self.BLACK_THRESHOLD
                    else self.PIXEL_BLACK
                )
                for pixel in img.getdata()
            )
        )

    def __process_screenshot(
        self, screenshot_src_path: Path, screenshot_dst_path: Path
    ):
        self._validate_path(screenshot_src_path)
        # Check image type / downsize x4 and convert to transparent png
        img = Image.open(screenshot_src_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if img.width < img.height:
            raise BundlerException(
                f"Screenshot {screenshot_src_path} is in portrait orientation. Only landscape screenshots are allowed."
            )

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
        self.__convert_image_pixels(img)
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

        if any(
            map(
                lambda pixel: pixel[:3] != self.PIXEL_TRANSPARENT[:3]
                and pixel[:3] != self.PIXEL_BLACK[:3],
                img.getdata(),
            )
        ):
            raise BundlerException(
                f"Icon {os.path.basename(icon_src_path)} is not black and white"
            )
        self.__convert_image_pixels(img)
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
            mk = Markdown(extensions=[BasicFormattingEnforcingExtension()])
            mk.convert(markdown)

        except Exception as e:
            raise BundlerException(f"Markdown error: {e}")

    def _build_package(self, skip_source_code: bool = False):
        self._log.info(f"Saving updated manifest with {skip_source_code=}")
        self._manifest.to_yaml_file(self._tmp_path / self.MANIFEST_YAML_NAME)

        with zipfile.ZipFile(
            self._bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as new_zip:
            for folder, subfolders, filenames in os.walk(self._tmp_path):
                # Exclude hidden folders and "dist" folder with build artifacts
                for folder_name in subfolders.copy():
                    if folder_name.startswith(".") or folder_name == "dist":
                        self._log.debug(f"Skipping folder {filename}")
                        subfolders.remove(folder_name)
                    # Exclude source code folder if requested
                    if skip_source_code and self._code_dir == Path(folder, folder_name):
                        self._log.debug(f"Skipping source code folder {folder}")
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

    def package_artifacts(self, artifacts_path: Path):
        self._log.info(f"Packaging artifacts: {artifacts_path}")
        dist_dir = self._code_dir / "dist"
        with zipfile.ZipFile(
            artifacts_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as new_zip:
            # Package "dist" folder with build artifacts
            for folder, subfolders, filenames in os.walk(dist_dir):
                for filename in filenames:
                    file_path = Path(os.path.join(folder, filename))
                    self._log.info(f"Adding {file_path}")
                    new_zip.write(file_path, file_path.relative_to(dist_dir))


class Main:
    def __init__(self):
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
        self.parser.add_argument(
            "--artifacts",
            default=None,
            help="ZIP file to write build artifacts to",
        )

    def main(self):
        return self.process(self.parser.parse_args())

    def _setup_imports(self):
        try:
            subprocess.check_output(
                [AppBundler.UFBT_COMMAND, "update"], encoding="utf-8"
            )
        except subprocess.CalledProcessError as e:
            raise BundlerException(f"Could not update ufbt: {e}")

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
                if args.artifacts:
                    bundler.package_artifacts(Path(args.artifacts))
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
