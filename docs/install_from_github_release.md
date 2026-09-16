# Installing Seventwos Workspace for Android from a GitHub release

This document explains how to install Seventwos Workspace for Android from a published GitHub release.
The protected release workflow first produces signed build artifacts in GitHub Actions. A maintainer then verifies
those artifacts and explicitly publishes selected files to a GitHub release. Workflow artifacts alone are not a
public release.

<!--- TOC -->

* [Installing the universal APK](#installing-the-universal-apk)
  * [Instructions](#instructions)
  * [Steps](#steps)
  * [I already have the application on my phone](#i-already-have-the-application-on-my-phone)
* [Installing from the App Bundle](#installing-from-the-app-bundle)
  * [Requirements](#requirements)
  * [Steps](#steps-1)
  * [I already have the application on my phone](#i-already-have-the-application-on-my-phone-1)

<!--- END -->

## Installing the universal APK

### Instructions

The easiest way to install the application from a GitHub release is to use the universal APK which is attached to the release. This APK is compatible with all Android devices, but it is not optimized for any of them. So it may not be as fast as it could be on your device, and it may not be as small as it could be.

Alternatively, you can generate an APK that is optimized for your device. This is explained in the next section.

### Steps

- Open the GitHub release that you want to install from using the Web browser of your phone.
- Download the APK
- Open the APK file from the download notification, or from the file manager
- Follow the steps to install the application

###  I already have the application on my phone

If the application was already installed on your phone, there are several cases:

- it was installed from the PlayStore, you can install the universal APK as long as the version is more recent. The existing data should not be lost.
- it was installed from a previous GitHub release, this is like an application upgrade.
- it was installed from a more recent GitHub release, or from the PlayStore with a later version, you will have to uninstall it first.

## Installing from the App Bundle

### Requirements

The GitHub release can contain an Android App Bundle (with `aab` extension), which needs to be converted into APKs suitable for the target device.

Release artifacts must already be signed by the protected Seventwos release workflow. The
repository debug key is development-only and must never be used for a release.

You can clone the project by running:
```bash
git clone git@github.com:seventwos-app/usr-workspace-android.git
```
or
```bash
git clone https://github.com/seventwos-app/usr-workspace-android.git
```

You will also need to install [bundletool](https://developer.android.com/studio/command-line/bundletool). On MacOS, you can run the following command:

```bash
brew install bundletool
```

### Steps

1. Open the GitHub release that you want to install from https://github.com/seventwos-app/usr-workspace-android/releases
2. Download the asset `app-gplay-release.aab`. This is the signed bundle produced and verified by the protected
   release process; the filename does not include a `-signed` suffix.
3. Navigate to the folder where you cloned the project and run the following command. Bundletool
will preserve and verify the signature carried by the signed app bundle:
```bash
bundletool build-apks --bundle=<PATH_TO_YOUR_APP-GPLAY-RELEASE.AAB_FILE> \
      --output=./tmp/seventwos-workspace.apks --mode=universal --overwrite
```
4. Run an Android emulator, or connect a real device to your computer
5. Install the APKs on the device:
```bash
bundletool install-apks --apks=./tmp/seventwos-workspace.apks
```

That's it, the application should be installed on your device, you can start it from the launcher icon.

###  I already have the application on my phone

If the application was already installed on your phone, there are several cases:

- it was installed from the PlayStore, you will have to uninstall it first because the signature will not match.
- it was installed from a previous GitHub release, this is like an application upgrade, so no need to uninstall the existing app.
- it was installed from a more recent GitHub release, you will have to uninstall it first.
