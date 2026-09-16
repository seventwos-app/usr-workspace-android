# Setup a debug mitm proxy to inspect all the app's network traffic

1) Install mitmproxy: `brew install mitmproxy`.
    1) Launch `mitmweb` from a terminal. It will pop up mitmproxy's web interface in a web browser.
1) Configure Android Emulator.
    1) Launch your android emulator.
    1) Open its settings page and go to Settings -> Proxy (nb this tab isn't visible when running the emu inside the Android Studio window, you need to set it so it runs in its own window).
    1) Disable "Use Android Studio HTTP proxy settings" and pick "Manual proxy configuration".
    1) Set `127.0.0.1` as "Host name" and `8080` as "Port number".
    1) Click "Apply" and verify that "Proxy status" is "Success" and close the settings window.
    1) Alternatively, set the proxy on the device itself, which the app honours through `DefaultProxyProvider`, and which also works on a physical device:
       ```
       adb shell settings put global http_proxy 10.0.2.2:8080
       ```
       Use `adb shell settings delete global http_proxy` to remove it afterwards. On a physical device, replace `10.0.2.2` with the address of the machine running mitmproxy.
1) Install the mitmproxy CA cert (this is needed to see traffic from java/kotlin code, it's not needed for traffic coming from native code e.g. the matrix-rust-sdk).
    1) Open the emulator Chrome browser app
    1) Go to the url `mitm.it`
    1) Follow the instructions to install the CA cert on Android devices.
1) Slightly modify the Seventwos Workspace app source code.
    1) Go to the `RustMatrixClientFactory.getBaseClientBuilder()` method, which builds every client the app creates, whether it is logging in or restoring a session.
    1) Add `.disableSslVerification()` in the `ClientBuilder` method chain.
1) Build and run the Seventwos Workspace app.
1) Enjoy, you will see all the traffic in mitmproxy's web interface.
