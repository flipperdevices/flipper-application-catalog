import argparse
import hashlib
import logging
import pathlib
import subprocess
import sys
import tempfile
import zipfile
from typing import Optional
import io

import requests
from bundle import ApplicationManifest


class GithubOutputHandler(logging.Handler):
    def __init__(self, gh_output: Optional[str]):
        super().__init__()
        self.gh_output = gh_output

    def emit(self, record):
        logging.info(
            f"Adding log to Github output: {self.format(record)} to {self.gh_output}"
        )
        with open(self.gh_output, "a") as f:
            f.write(f"{self.format(record)}\n")


github_logger = logging.getLogger("github")
github_logger.setLevel(logging.INFO)


class UploadError(Exception):
    def __init__(self, http_error: requests.HTTPError):
        self.http_error = http_error

    def __str__(self):
        return f"Upload failed: code {self.http_error}, message {self.http_error.response.text}"


class ArtifactUploader:
    FAILURE_URL_SUFFIX = "/status/fail"

    def __init__(self, upload_url: str, token: str, github_run_id: int = 0):
        self.upload_url = upload_url
        self.token = token
        self.github_run_id = github_run_id

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
        }

    def _get_params(self):
        params = {}
        if self.github_run_id:
            params["github_run_id"] = (None, self.github_run_id)
        return params

    def process_response(self, response: requests.Response):
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise UploadError(e)

    def upload(self, artifact: pathlib.Path):
        # Create a ZIP file with the artifact
        sha256 = hashlib.sha256()
        with open(artifact, "rb") as f:
            sha256.update(f.read())
        sha256_hash = sha256.hexdigest()

        github_logger.info(f"SHA256 for {artifact.name} = `{sha256_hash}`")

        artifact_zip = artifact.with_suffix(".zip")
        with zipfile.ZipFile(artifact_zip, "w") as zip_ref:
            zip_ref.write(artifact, artifact.name)

        # Upload it
        with artifact_zip.open("rb") as zip_fin:
            params = self._get_params()
            params.update(
                {
                    "build_checksum": (None, sha256_hash),
                    "build": zip_fin,
                }
            )
            response = requests.post(
                self.upload_url,
                headers=self._get_headers(),
                files=params,
            )
        self.process_response(response)

    def report_error(self, error_log: str):
        headers = self._get_headers()
        params = self._get_params()
        params.update({"logs": io.BytesIO(error_log.encode("utf-8"))})

        response = requests.post(
            self.upload_url + self.FAILURE_URL_SUFFIX,
            headers=headers,
            files=params,
        )
        self.process_response(response)


class BundleBuildError(Exception):
    def __init__(self, stdout: str, stderr: str):
        self.stdout = stdout
        self.stderr = stderr


class BundleBuilder:
    def __init__(self, bundle_zip_url: str):
        self.bundle_zip_url = bundle_zip_url
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = pathlib.Path(self.tmp_dir.name)

    def __del__(self):
        logging.info("Cleaning up")
        self.tmp_dir.cleanup()

    def build(self):
        logging.info(f"Building bundle from {self.bundle_zip_url}")
        response = requests.get(self.bundle_zip_url)
        response.raise_for_status()

        # subprocess.call(["open", self.tmp_path])

        zip_file = self.tmp_path / "bundle.zip"

        with open(zip_file, "wb") as f:
            f.write(response.content)

        logging.info(f"Bundle saved to {zip_file}")

        # Unzip the bundle
        logging.info("Unzipping bundle")

        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(self.tmp_path)

        logging.info("Bundle unzipped")

        manifest_file = self.tmp_path / "manifest.yml"
        manifest = ApplicationManifest.from_yaml_file(manifest_file)
        logging.info(f"Manifest: {manifest}")

        code_dir = self.tmp_path / "code"

        # Build the bundle
        logging.info("Building bundle")

        p = subprocess.run(
            [
                "ufbt",
                "faps",
            ],
            cwd=code_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logging.info(p.stdout.decode("utf-8"))
        if p.stderr:
            logging.error(p.stderr.decode("utf-8"))

        if p.returncode != 0:
            raise BundleBuildError(p.stdout.decode("utf-8"), p.stderr.decode("utf-8"))

        logging.info(f"Bundle built in {code_dir}")

        artifact = code_dir / "dist" / f"{manifest.id}.fap"

        if not artifact.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact}")
        else:
            logging.info(f"Artifact built: {artifact}")

        return artifact


class Main:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Build source code bundle")
        self.parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="Enable debug mode",
        )

        self.parser.add_argument(
            "--api",
            type=str,
            help="API URL",
            required=True,
        )

        self.parser.add_argument(
            "--bundle-path",
            type=str,
            help="Path to zip file with source code bundle, relative to API root",
            required=True,
        )

        self.parser.add_argument(
            "--upload-path",
            type=str,
            help="Path to upload zip file with artifact, relative to API root",
            required=True,
        )

        self.parser.add_argument(
            "--token",
            type=str,
            help="API token",
            required=True,
        )

        self.parser.add_argument(
            "--gh-summary",
            type=str,
            help="Github summary output file",
            default="",
        )

        self.parser.add_argument(
            "--gh-run-id",
            type=int,
            help="Github run ID",
            default=0,
        )

    def main(self):
        args = self.parser.parse_args()

        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        if args.gh_summary:
            logging.info(f"Also logging to Github output file {args.gh_summary}")
            github_logger.addHandler(GithubOutputHandler(args.gh_summary))

        builder = BundleBuilder(f"{args.api}{args.bundle_path}")
        uploader = ArtifactUploader(
            f"{args.api}{args.upload_path}",
            token=args.token,
            github_run_id=args.gh_run_id,
        )

        try:
            fap_path = builder.build()
            uploader.upload(fap_path)
            return 0
        except BundleBuildError as e:
            logging.error(f"Bundle build failed: {e.stderr}")
            uploader.report_error(f"Stdout: {e.stdout}\n\n\nStderr: {e.stderr}\n")
        except UploadError as e:
            logging.error(f"Upload failed: {e}")
        except Exception as e:
            logging.error(f"Bundle build failed: {e}")
            uploader.report_error(str(e))
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname).1s] %(message)s",
        level=logging.INFO,
        datefmt="%H:%M:%S",
    )
    logging.info("Building project")

    sys.exit(Main().main())
