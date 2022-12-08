import os
import shutil
import yaml
import subprocess
import logging
import zipfile

from dataclasses import dataclass, field
from dataclass_wizard import YAMLWizard
from tempfile import TemporaryDirectory
from git import Repo
from pathlib import Path
from shlex import quote
from PIL import Image

from flipper.app import App
from flipper.appmanifest_core import AppManager, FlipperAppType, FlipperApplication


class BundlerException(Exception):
    pass


@dataclass
class CodeLocation:
    type: str
    location: dict[str, str]


@dataclass
class ApplicationManifest(YAMLWizard):
    sourcecode: CodeLocation
    name: str = ""
    id: str = ""
    author: str = ""
    version: str = ""
    icon: str = ""
    category: str = "Misc"
    description: str = ""
    changelog: str = ""
    screenshots: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=lambda: ["all"])

    def sync_from(self, app: FlipperApplication):
        field_map = {
            "name": "name",
            "id": "appid",
            "author": "fap_author",
            # "version": "fap_version",
            "category": "fap_category",
            "icon": "fap_icon",
            "description": "fap_description",
            "targets": "targets",
        }

        for yaml_field, app_field in field_map.items():
            current_value = getattr(self, yaml_field)
            fam_value = getattr(app, app_field)

            if type(current_value) != type(fam_value):
                raise BundlerException(
                    f"Type mismatch for {yaml_field}: {type(current_value)} != {type(fam_value)}"
                )

            if current_value and fam_value and current_value != fam_value:
                logging.getLogger(self.__class__.__name__).warning(
                    f"Value in YAML for {yaml_field} is different from value in FAM: '{fam_value}' / '{current_value}'"
                )
                continue

            setattr(self, yaml_field, getattr(app, app_field))


class AppBundler:
    UFBT_COMMAND = "ufbt.cmd" if os.name == "nt" else "ufbt"
    ORANGE_BG_COLOR = (254, 138, 44)  # RGB for background color in screenshots
    FLIPPER_SCREEN_SIZE = (128, 64)

    def __init__(self, manifest_yaml_path: str, bundle_path: str):
        self._log = logging.getLogger(self.__class__.__name__)
        self._manifest_yaml_path = manifest_yaml_path
        self._bundle_path = bundle_path
        self._tmp_dir = TemporaryDirectory()
        self._working_dir = Path(self._tmp_dir.name)
        self._code_dir = self._working_dir / "code"
        self._assets_dir = self._working_dir / "assets"
        self._assets_dir.mkdir()
        self._repo = None
        self._fam_manifest = None
        self._log.info(f"Working in '{self._working_dir}'")
        self._load()

    def bundle(self, *, skip_lint: bool = False, skip_build: bool = False):
        self._fetch_sources()
        if not skip_lint:
            self._lint_sources()
        if not skip_build:
            self._build_sources()
        self._update_manifest_from_fap()
        self._process_includes()
        self._process_assets()
        self._build_package()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.cleanup()

    def cleanup(self):
        self._tmp_dir.cleanup()

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
        if not path.exists():
            raise BundlerException(f"Path not found: {path}")
        if not path.resolve().is_relative_to(self._working_dir):
            raise BundlerException(f"Path traversal detected: {path}")

    def _rel_path(self, path: Path):
        self._validate_path(path)
        return path.relative_to(self._working_dir).as_posix()

    def _fetch_sources(self):
        if self._manifest.sourcecode.type == "git":
            repo_origin = self._manifest.sourcecode.location["origin"]
            self._repo = Repo.clone_from(
                repo_origin,
                self._code_dir,
                multi_options=[
                    f"--branch {quote(self._manifest.sourcecode.location['tag'])}",
                    "--depth 1",
                    "--recurse-submodules",
                ],
            )
            self._log.info(f"Cloned {repo_origin} to {self._code_dir}")
        else:
            raise BundlerException(
                f"Unknown sourcecode type: {self._manifest.sourcecode.type}"
            )

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
        elif len(known_ext_apps) > 1:
            raise BundlerException("Multiple external applications found")

        self._fam_manifest = known_ext_apps[0]
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
        downsized_resolution = (img.width // 4, img.height // 4)
        if downsized_resolution != self.FLIPPER_SCREEN_SIZE:
            raise BundlerException(
                f"Screenshot {screenshot_src_path} has resolution {img.width}x{img.height}, "
                f"expected {self.FLIPPER_SCREEN_SIZE[0]}x{self.FLIPPER_SCREEN_SIZE[1]}"
            )

        img = img.resize(downsized_resolution, resample=Image.Resampling.NEAREST)
        # Set orange background to transparent
        img.putdata(
            tuple(
                (255, 255, 255, 0) if pixel[:3] == self.ORANGE_BG_COLOR else pixel
                for pixel in img.getdata()
            )
        )
        img.save(screenshot_dst_path, "PNG")

    def _process_assets(self):
        icon_path = self._assets_dir / "icon.png"
        src_icon_path = self._code_dir / self._fam_manifest.fap_icon
        self._validate_path(src_icon_path)
        shutil.copy(src_icon_path, icon_path)
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

        self._manifest.screenshots = new_screenshot_paths

    def _build_package(self):
        self._log.info(f"Saving updated manifest")
        self._manifest.to_yaml_file(self._working_dir / "manifest.yml")

        with zipfile.ZipFile(
            self._bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as new_zip:
            for folder, subfolders, filenames in os.walk(self._working_dir):
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


class Main(App):
    def init(self):
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
        self.parser.set_defaults(func=self.process)

    def before(self):
        pass

    def after(self):
        pass

    def process(self):
        try:
            with AppBundler(
                self.args.manifest_path, self.args.bundle_zip_path
            ) as bundler:
                bundler.bundle(skip_lint=self.args.nolint, skip_build=self.args.nobuild)
                return 0
        except BundlerException as e:
            self.logger.exception(e)
            return 1


if __name__ == "__main__":
    Main()()
