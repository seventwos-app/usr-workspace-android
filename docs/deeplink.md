# Seventwos Workspace Android deep links

<!--- TOC -->

* [Introduction](#introduction)
  * [Asset Links](#asset-links)
  * [Supported links](#supported-links)
* [Developer tools](#developer-tools)

<!--- END -->


## Introduction

Seventwos Workspace supports Matrix links, the `seventwos-workspace://open` internal scheme, and
verified HTTPS links on `workspace.seventwos.org`.

### Asset Links

Before production release, publish the final signing certificate association at
`https://workspace.seventwos.org/.well-known/assetlinks.json`. The certificate fingerprint cannot
be populated until Seventwos creates the production signing key.

### Supported links

Matrix protocol links (`matrix:`) remain supported. HTTPS links intended to open directly in this
application must use `https://workspace.seventwos.org`.

## Developer tools

Using an Android 12 or higher emulator

Ensure links verification is enabled
```bash
adb shell am compat enable 175408749 org.seventwos.workspace.debug
```

Reset link verifications for the given package id
```bash
adb shell pm set-app-links --package org.seventwos.workspace.debug 0 all
```

Force the package id links to be verified
```bash
adb shell pm verify-app-links --re-verify org.seventwos.workspace.debug
```

Print the link verification of the package id
```bash
adb shell pm get-app-links org.seventwos.workspace.debug
```

```
  org.seventwos.workspace.debug:
    Domain verification state:
      workspace.seventwos.org: verified
```
