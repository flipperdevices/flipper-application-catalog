from flipper.app import App
from requests import Session


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

    @staticmethod
    def get_bundle_zip(session: Session, uri: str) -> object:
        print(f"Get from {uri}")
        response = session.get(uri)
        return response

    @staticmethod
    def post_application_build(session: Session, uri: str, app: object) -> None:
        print(f"Post to {uri}")
        response = session.post(uri)

    def process(self):
        with Session() as session:
            # Get bundle from Archivarius through REST
            bundle = self.get_bundle_zip(session, self.bundle_url)

            # processing bundle
            # ...

            # Post new application build to Archivarius through REST
            self.post_application_build(session, self.upload_url, ...)

        return 0


if __name__ == "__main__":
    Main()()
