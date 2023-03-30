from flipper.app import App


class Main(App):
    def init(self):
        self.parser.add_argument(
            "bundle_url",
            help="Path to the manifest file",
        )
        self.parser.add_argument(
            "upload_url",
            help="Path to the bundle file",
        )
        self.parser.set_defaults(func=self.process)

    def process(self):
        pass


if __name__ == "__main__":
    Main()()
