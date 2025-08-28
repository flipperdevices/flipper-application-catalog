# Mouse Jiggler for Flipper Zero
This simple application is a fork of Matthew Willard's [flipper-mouse-jiggler](https://github.com/matthewwwillard/flipper-mouse-jiggler). Unlike other mouse jiggler implementations for the Flipper Zero, this one introduces an element of randomness to the movement patterns instead of performing a simple back-and-forth cycle.

**WARNING: Do not use this application to interact with a system that you do not own unless you have explicitly been granted permission to do so. If you choose to use this application in an unauthorized manner, I am not responsible for the consequences you may face.**

## Installing
1. Download the FAP file from the [release page](https://github.com/DavidBerdik/flipper-mouse-jiggler/releases).
2. Copy the FAP file to your Flipper. The easiest way to do this is by using the [qFlipper desktop application](https://flipperzero.one/downloads). The recommended storage location for this application is 'SD Card/apps/USB/'.
3. On your Flipper, navigate to 'Apps > USB > Mouse Jiggler' and launch the application.
4. Plug your Flipper in to a computer using a USB cable. While the application is running, the Flipper will present itself to the computer as a mouse and send arbitrary movement instructions to the system.

## Building
1. Clone this repository.
2. [Install uFBT.](https://github.com/flipperdevices/flipperzero-ufbt)
3. Using a command line, navigate to this repository's directory and execute the following command: 'ufbt faps'
4. Once the build completes, a 'dist' folder will be created. This folder will contain the compiled FAP file.
5. You can run the compiled FAP file by manually copying it to your Flipper as described above or by executing the following command: 'ufbt launch'
