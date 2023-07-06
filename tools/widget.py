import argparse
import os

import requests
import logging
import sys


class Main:
    ARCHIVARIUS_URL = os.getenv('ARCHIVARIUS_URL')

    def __init__(self):
        self.logger = logging.getLogger()
        self.parser = argparse.ArgumentParser()

        self.parser.add_argument(
            "application_name",
            help="Application Name",
        )
        self.parser.add_argument(
            "application_version_id",
            help="Application Version ID",
        )
        self.parser.add_argument(
            "application_semver",
            help="Application Semver",
        )
        self.parser.add_argument(
            "application_category",
            help="Application Category",
        )

    def main(self):
        return self.process(self.parser.parse_args())

    def retrieve_application_version_from_catalog(self, application_name) -> dict:
        response = requests.get(
            f"{self.ARCHIVARIUS_URL}/api/v0/application/{application_name}"
        )
        return response.json()["current_version"]

    def retrieve_build_statuses_from_catalog(self, application_version_id: str) -> list:
        response = requests.get(
            f"{self.ARCHIVARIUS_URL}/api/v0/application/version/{application_version_id}/build/status"
        )
        return response.json()

    def update_readme_statuses(
        self,
        readme_file_arr: list,
        application_version_statuses: list,
        application_name: str,
        application_version_id: str,
        application_semver: str,
    ) -> list:
        # change readme title
        readme_file_arr[
            2
        ] = f"Latest **{application_name}** version is **{application_semver}**"

        widget_template = (
            "[![{API} {TARGET}]"
            "({ARCHIVARIUS_URL}/api/v0/application/version/{APP_VERSION_ID}/build/{TARGET}/{API}/status/widget)]"
            "({ARCHIVARIUS_URL}/api/v0/application/version/{APP_VERSION_ID}/build/{TARGET}/{API}/logs)"
        )

        # append build statuses
        for status in application_version_statuses:
            readme_file_arr.append(
                widget_template.format(
                    API=status["sdk"]["api"],
                    TARGET=status["sdk"]["target"],
                    ARCHIVARIUS_URL=self.ARCHIVARIUS_URL,
                    APP_VERSION_ID=application_version_id,
                )
                + "\n\n"
            )
        return readme_file_arr

    def process(self, args):
        try:
            # Get application version build statuses
            application_version_statuses = self.retrieve_build_statuses_from_catalog(
                application_version_id=args.application_version_id,
            )

            with open(f".github/WIDGET_TEMPLATE.md", "r") as reader:
                readme_file_arr = reader.readlines()
                readme_file_arr.append("\n")

            readme_file_arr = self.update_readme_statuses(
                readme_file_arr,
                application_version_statuses=application_version_statuses,
                application_name=args.application_name,
                application_semver=args.application_semver,
                application_version_id=args.application_version_id,
            )

            with open(
                f"applications/{args.application_category}/{args.application_name}/README.md",
                "w",
            ) as writer:
                for line in readme_file_arr:
                    writer.write(line)

            return 0
        except Exception as e:
            self.logger.exception(e)
            return 1


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname).1s] %(message)s",
        level=logging.INFO,
        datefmt="%H:%M:%S",
    )

    sys.exit(Main().main())
