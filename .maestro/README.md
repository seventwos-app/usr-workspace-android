# Maestro

Maestro is a framework that we are using to test navigation across the application.
To setup, please refer at [https://maestro.mobile.dev](https://maestro.mobile.dev)

<!--- TOC -->

* [Run test](#run-test)
  * [Output](#output)
* [Write test](#write-test)
* [CI](#ci)
* [iOS](#ios)
* [Future](#future)

<!--- END -->

## Run test

From root dir of the project

*Note: Since Seventwos Workspace does not allow account creation, we have to use an existing account to run maestro test suite. So to run locally, please replace `user` and `123` with your test matrix.org account credentials, and `my room` with one of a room this account has joined. Note that the test will send messages to this room.*

```shell
maestro test \
    -e MAESTRO_APP_ID=org.seventwos.workspace.debug \
    -e MAESTRO_USERNAME=user1 \
    -e MAESTRO_PASSWORD=123 \
    -e MAESTRO_RECOVERY_KEY=ABC \
    -e MAESTRO_ROOM_NAME="MyRoom" \
    -e MAESTRO_INVITEE1_MXID=user2 \
    -e MAESTRO_INVITEE2_MXID=user3 \
    .maestro/allTests.yaml
```

### Output

Test result will be printed on the console, and screenshots will be generated at `./build/maestro`

## Write test

Tests are yaml files. Generally each yaml file should leave the app in the same screen than at the beginning.

Start the Seventwos Workspace app and run this command to help writing test.

```shell
maestro studio
```

Note that sometimes, this prevent running the test. So kill the `maestro studio` process to be able to run the test again.

Also, if updating the application code, do not forget to deploy again the application before running the maestro tests.

## CI

The CI can run Maestro using the workflow `.github/workflows/maestro-local.yml` and [Maestro Cloud](https://cloud.mobile.dev/).
Configure `MAESTRO_CLOUD_API_KEY` and `MATRIX_MAESTRO_ACCOUNT_PASSWORD` with Seventwos-owned test infrastructure before enabling cloud runs. Do not reuse inherited upstream accounts.

## iOS

Need to install `idb-companion` first

```shell
brew install idb-companion
```

Also:
https://github.com/mobile-dev-inc/maestro/issues/146
https://github.com/mobile-dev-inc/maestro/issues/107
So you have to change your input keyboard to QWERTY for it to work properly.

## Future

- This repository's product scope is Android-only (see the root [README](../README.md#repository-scope)); cross-platform test coordination is out of scope until a companion client is part of this product's scope.
