# Analytics in Seventwos Workspace

<!--- TOC -->

* [Sentry](#sentry)

<!--- END -->

## Sentry

Analytics is disabled by default. No inherited Element endpoint or project is used.

To opt in to Seventwos-owned Sentry, set `SEVENTWOS_ANDROID_SENTRY_DSN`. The Rust SDK can use
`SEVENTWOS_ANDROID_SDK_SENTRY_DSN`.

PostHog is enabled only when both `SEVENTWOS_ANDROID_POSTHOG_HOST` and
`SEVENTWOS_ANDROID_POSTHOG_API_KEY` are present. Bug reporting is independent and requires
`SEVENTWOS_ANDROID_BUG_REPORT_URL`. Keep credentials in protected CI secrets, never in the
repository.
