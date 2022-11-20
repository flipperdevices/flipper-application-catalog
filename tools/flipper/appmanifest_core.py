from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import os


class FlipperManifestException(Exception):
    pass


class FlipperAppType(Enum):
    SERVICE = "Service"
    SYSTEM = "System"
    APP = "App"
    PLUGIN = "Plugin"
    DEBUG = "Debug"
    ARCHIVE = "Archive"
    SETTINGS = "Settings"
    STARTUP = "StartupHook"
    EXTERNAL = "External"
    METAPACKAGE = "Package"


@dataclass
class FlipperApplication:
    @dataclass
    class ExternallyBuiltFile:
        path: str
        command: str

    @dataclass
    class Library:
        name: str
        fap_include_paths: List[str] = field(default_factory=lambda: ["."])
        sources: List[str] = field(default_factory=lambda: ["*.c*"])
        cflags: List[str] = field(default_factory=list)
        cdefines: List[str] = field(default_factory=list)
        cincludes: List[str] = field(default_factory=list)

    PRIVATE_FIELD_PREFIX = "_"

    appid: str
    apptype: FlipperAppType
    name: Optional[str] = ""
    entry_point: Optional[str] = None
    flags: List[str] = field(default_factory=lambda: ["Default"])
    cdefines: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    stack_size: int = 2048
    icon: Optional[str] = None
    order: int = 0
    sdk_headers: List[str] = field(default_factory=list)
    targets: List[str] = field(default_factory=lambda: ["all"])

    # .fap-specific
    sources: List[str] = field(default_factory=lambda: ["*.c*"])
    fap_version: Tuple[int] = field(default_factory=lambda: (0, 1))
    fap_icon: Optional[str] = None
    fap_libs: List[str] = field(default_factory=list)
    fap_category: str = ""
    fap_description: str = ""
    fap_author: str = ""
    fap_weburl: str = ""
    fap_icon_assets: Optional[str] = None
    fap_extbuild: List[ExternallyBuiltFile] = field(default_factory=list)
    fap_private_libs: List[Library] = field(default_factory=list)
    # Internally used by fbt
    _appdir: Optional[object] = None
    _apppath: Optional[str] = None


class AppManager:
    def __init__(self):
        self.known_apps = {}

    def get(self, appname: str):
        try:
            return self.known_apps[appname]
        except KeyError as _:
            raise FlipperManifestException(
                f"Missing application manifest for '{appname}'"
            )

    def find_by_appdir(self, appdir: str):
        for app in self.known_apps.values():
            if app._appdir.name == appdir:
                return app
        return None

    def load_manifest(self, app_manifest_path: str, app_dir_node: object):
        if not os.path.exists(app_manifest_path):
            raise FlipperManifestException(
                f"App manifest not found at path {app_manifest_path}"
            )
        # print("Loading", app_manifest_path)

        app_manifests = []

        def App(*args, **kw):
            nonlocal app_manifests
            app_manifests.append(
                FlipperApplication(
                    *args,
                    **kw,
                    _appdir=app_dir_node,
                    _apppath=os.path.dirname(app_manifest_path),
                ),
            )

        def ExtFile(*args, **kw):
            return FlipperApplication.ExternallyBuiltFile(*args, **kw)

        def Lib(*args, **kw):
            return FlipperApplication.Library(*args, **kw)

        try:
            with open(app_manifest_path, "rt") as manifest_file:
                exec(manifest_file.read())
        except Exception as e:
            raise FlipperManifestException(
                f"Failed parsing manifest '{app_manifest_path}' : {e}"
            )

        if len(app_manifests) == 0:
            raise FlipperManifestException(
                f"App manifest '{app_manifest_path}' is malformed"
            )

        # print("Built", app_manifests)
        for app in app_manifests:
            self._add_known_app(app)

    def _add_known_app(self, app: FlipperApplication):
        if self.known_apps.get(app.appid, None):
            raise FlipperManifestException(f"Duplicate app declaration: {app.appid}")
        self.known_apps[app.appid] = app

    # def filter_apps(self, applist: List[str], hw_target: str):
    #     return AppBuildset(self, applist, hw_target)
