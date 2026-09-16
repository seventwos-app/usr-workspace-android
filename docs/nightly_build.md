# Nightly builds

<!--- TOC -->

* [Configuration](#configuration)
* [How to register to get nightly build](#how-to-register-to-get-nightly-build)
* [Build nightly manually](#build-nightly-manually)

<!--- END -->

## Configuration

The nightly build will contain what's on develop, in release mode, for the main variant. It reuses the same release signing config (the `SEVENTWOS_ANDROID_SIGNING_*` secrets) and has a `.nightly` application-id suffix, so it can be installed alongside the production version of this app. The only other difference is a different app name (`"$baseAppName nightly"`).

Nightly builds are built and released to Firebase every days, and automatically.

This is recommended to exclusively use this app, with your main account, instead of the production build, and fall back to the production build just in case of regression, to discover as soon as possible any regression, and report it to the team. To avoid double notification, you may want to disable the notification from the production version. Just open the production build, navigate to `Settings/Notifications` and uncheck `Enable notifications for this session` (TODO Not supported yet).

*Note:* Due to a limitation of Firebase, the nightly build is the universal build, which means that the size of the APK is a bit bigger, but this should not have any other side effect.

## How to register to get nightly build

No Seventwos-operated Firebase App Distribution invite link is configured yet. Ask your team lead for the current distribution invite once a Seventwos Firebase project is set up.

## Build nightly manually

Nightly build can be built manually from your computer. Nightly reuses the release signing config, so set
the same environment variables used for release builds (see `app/build.gradle.kts`), retrieving the
secret values from your organization's secrets manager:

```sh
export SEVENTWOS_ANDROID_SIGNING_KEYSTORE_PATH=VALUE_FROM_YOUR_SECRETS_MANAGER
export SEVENTWOS_ANDROID_SIGNING_KEY_ALIAS=VALUE_FROM_YOUR_SECRETS_MANAGER
export SEVENTWOS_ANDROID_SIGNING_KEY_PASSWORD=VALUE_FROM_YOUR_SECRETS_MANAGER
export SEVENTWOS_ANDROID_SIGNING_STORE_PASSWORD=VALUE_FROM_YOUR_SECRETS_MANAGER
```

You will also need to add the environment variable `FIREBASE_TOKEN`:

```sh
export FIREBASE_TOKEN=VALUE_FROM_YOUR_SECRETS_MANAGER
```

Then you can run the following commands (a dedicated GitHub Action for nightly builds is not currently configured in this repository; see `.github/workflows/` for the active workflows):

```sh
git checkout develop
./gradlew assembleGplayNightly appDistributionUploadGplayNightly
```

Then you can reset the change on the codebase.
