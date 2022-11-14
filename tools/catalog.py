#!/usr/bin/env python

from flipper.app import *
from flipper.manifest import *

import yaml

class Main(App):
    def init(self):
        self.subparsers = self.parser.add_subparsers(help="sub-command help")
        # Wipe
        self.parser_process = self.subparsers.add_parser("process", help="Process manifest")
        self.parser_process.add_argument("catalog", help="Catalog directory")
        self.parser_process.set_defaults(func=self.process)

    def before(self):
        pass

    def after(self):
        pass

    def process(self):
        self.logger.info(f"Processing {self.args.catalog}")

        try:
            mp = ManifestProcessor()
            mp.load(self.args.catalog)
            mp.process()
        except Exception as e:
            self.logger.error("Failed to process manifests")
            self.logger.exception(e)
            return 1

        return 0


if __name__ == '__main__':
    Main()()