import io
import os
import zipfile
import tempfile
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

    #http://172.30.1.22:8000/api/v0/application/application_bundle.zip

    @staticmethod
    def download_and_extract_bundle(session: Session, uri: str, extract_path: str) -> None:
        """
        A method for retrieving the bundle required for the build
        :return: Upload status code
        """
        response = session.get(uri, stream=True)
        z = zipfile.ZipFile(io.BytesIO(response.content))
        z.extractall(extract_path)

    @staticmethod
    def make_application_build(bundle_path: str) -> str:
        """
        Using ufbt we create a build application from
        the received bundle from Archivarius
        :return: The path in which the build will be located
        """
        os.chdir(bundle_path + "/code")
        # create images (may not be needed in future versions)
        if not os.path.exists("images"):
            os.mkdir("images")
        # run build
        os.system("ufbt")

        return "./dist/demo_app.fap"

    @staticmethod
    def upload_application_build(session: Session, uri: str, build_path: str) -> bool:
        """
        Method for sending the final build to the Archivarius
        :return: Upload status code
        """
        files = {
            'build': open(build_path, 'rb')
        }
        response = session.post(uri, files=files)
        return response.status_code == 201

    def process(self) -> int:
        """
        Node to run the build build pipeline based on the
        received bundle from the Archivarius. As soon as the build
        has been received it sends back to the Archivarius
        :return: Nothing
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            with Session() as session:
                # Get bundle from Archivarius through REST
                self.download_and_extract_bundle(
                    session, self.args.bundle_url, extract_path=tmp_dir
                )
                # processing bundle
                build_path = self.make_application_build(bundle_path=tmp_dir)

                # Post new application build to Archivarius through REST
                upload_status = self.upload_application_build(
                    session, self.args.upload_url, build_path=build_path
                )

                if upload_status:
                    print("Application build completed successfully!")
                else:
                    print("Something went wrong while building the application!")

        return 0


if __name__ == "__main__":
    Main()()
