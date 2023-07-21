import argparse
import os

import requests
import logging
import sys


class Main:
    ARCHIVARIUS_URL = os.getenv("ARCHIVARIUS_URL")

    def __init__(self):
        self.logger = logging.getLogger()
        if self.ARCHIVARIUS_URL is None:
            self.logger.error("ARCHIVARIUS_URL is not set in environment")
            sys.exit(1)

        self.parser = argparse.ArgumentParser()

        self.parser.add_argument(
            "application_name",
            help="Application Name",
        )
        self.parser.add_argument(
            "application_category",
            help="Application Category",
        )

    def main(self):
        return self.process(self.parser.parse_args())

    def add_widget_to_readme(
        self,
        readme_file_arr: list,
        application_name: str,
    ) -> list:
        widget_template = (
            "[![{APPLICATION_NAME}]"
            "({ARCHIVARIUS_URL}/application/{APPLICATION_NAME}/widget)]"
            "({ARCHIVARIUS_URL}/application/{APPLICATION_NAME}/page)"
        )
        readme_file_arr.append(
            widget_template.format(
                ARCHIVARIUS_URL=self.ARCHIVARIUS_URL,
                APPLICATION_NAME=application_name,
            )
        )
        return readme_file_arr

    def process(self, args):
        try:
            with open(f".github/WIDGET_TEMPLATE.md", "r") as reader:
                readme_file_arr = reader.readlines()
                readme_file_arr.append("\n")

            readme_file_arr = self.add_widget_to_readme(
                readme_file_arr, application_name=args.application_name
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
