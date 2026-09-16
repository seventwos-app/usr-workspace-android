# Android release readiness

The repository is configured for the Seventwos-owned Android application identity
`org.seventwos.workspace`. The Kotlin namespace remains `io.element.android.x` to preserve the
upstream package structure and provenance.

## Release signing

Signed artifacts are created only by the manually dispatched
`Build signed Android release artifacts` workflow. Configure an `android-release` GitHub
environment with required reviewers and these protected secrets:

- `SEVENTWOS_ANDROID_SIGNING_KEYSTORE_BASE64`
- `SEVENTWOS_ANDROID_SIGNING_KEY_ALIAS`
- `SEVENTWOS_ANDROID_SIGNING_KEY_PASSWORD`
- `SEVENTWOS_ANDROID_SIGNING_STORE_PASSWORD`

The workflow verifies the keystore, APK signatures, absence of the Android debug certificate, and
the application identifier. It uploads artifacts only to GitHub Actions; it does not publish to
Google Play, Firebase App Distribution, or another external service. The production keystore must
be generated, backed up, access-controlled, and rotated according to Seventwos policy before the
first release.

## External requirements

Repository configuration alone cannot complete a production release. Seventwos must provide:

- A Google Play developer account, application record, store listing, and any required declarations.
- Public privacy, acceptable-use, support, and security-contact pages. No placeholder URLs are
  embedded in the application.
- `https://workspace.seventwos.org/.well-known/assetlinks.json` containing
  `org.seventwos.workspace` and the final production certificate SHA-256 fingerprint.
- OAuth client metadata and redirect registrations for `org.seventwos.workspace` with every
  supported Matrix authentication service.
- Optional Seventwos-owned observability, bug-reporting, call, and push infrastructure if those
  features are enabled.

## Optional integrations

All inherited Element-operated integrations are off by default.

| Integration | Build environment |
|---|---|
| PostHog | `SEVENTWOS_ANDROID_POSTHOG_HOST`, `SEVENTWOS_ANDROID_POSTHOG_API_KEY` |
| Sentry | `SEVENTWOS_ANDROID_SENTRY_DSN`, optional `SEVENTWOS_ANDROID_SDK_SENTRY_DSN` |
| Bug reports | `SEVENTWOS_ANDROID_BUG_REPORT_URL` |
| Calls | `SEVENTWOS_ANDROID_CALLS_ENABLED=true`; optional call telemetry variables use the `SEVENTWOS_ANDROID_CALL_` prefix |
| Firebase push | `SEVENTWOS_ANDROID_ENABLE_FIREBASE=true`, `SEVENTWOS_ANDROID_FIREBASE_PUSH_GATEWAY`, `SEVENTWOS_ANDROID_PUSHER_APP_ID`, plus an untracked Seventwos Firebase resource configuration |
| UnifiedPush | `SEVENTWOS_ANDROID_ENABLE_UNIFIED_PUSH=true`, `SEVENTWOS_ANDROID_UNIFIED_PUSH_GATEWAY`, `SEVENTWOS_ANDROID_UNIFIED_PUSH_DISTRIBUTORS_URL`, `SEVENTWOS_ANDROID_PUSHER_APP_ID` |

Firebase additionally requires a Seventwos Firebase Android app registered for
`org.seventwos.workspace`, FCM credentials, and a Seventwos-operated Matrix push gateway such as
Sygnal. Firebase resource files and `google-services.json` are ignored and must be supplied
securely at build time. Partial push configuration is treated as disabled.

Normal pull-request CI compiles release sources without packaging a release, so protected signing
material is never exposed to untrusted pull requests.
