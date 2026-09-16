/*
 * Copyright (c) 2025 Element Creations Ltd.
 * Copyright 2025 New Vector Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial.
 * Please see LICENSE files in the repository root for full details.
 */

package config

object BuildTimeConfig {
    private fun environment(name: String): String? = System.getenv(name)?.takeIf(String::isNotBlank)

    const val APPLICATION_ID = "org.seventwos.workspace"
    const val APPLICATION_NAME = "Seventwos Workspace"
    val METADATA_HOST_REVERSED: String? = APPLICATION_ID
    val OAUTH_CLIENT_URL_PATH: String? = "apps/android"
    val URL_WEBSITE: String? = "https://workspace.seventwos.org"
    val URL_LOGO: String? = null
    val URL_COPYRIGHT: String? = null
    val URL_ACCEPTABLE_USE: String? = null
    val URL_PRIVACY: String? = null
    val URL_POLICY: String? = null
    val SERVICES_MAPTILER_BASE_URL: String? = null
    val SERVICES_MAPTILER_APIKEY: String? = null
    val SERVICES_MAPTILER_LIGHT_MAPID: String? = null
    val SERVICES_MAPTILER_DARK_MAPID: String? = null
    val SERVICES_POSTHOG_HOST: String? = environment("SEVENTWOS_ANDROID_POSTHOG_HOST")
    val SERVICES_POSTHOG_APIKEY: String? = environment("SEVENTWOS_ANDROID_POSTHOG_API_KEY")
    val SERVICES_SENTRY_DSN: String? = environment("SEVENTWOS_ANDROID_SENTRY_DSN")
    val SERVICES_SENTRY_DSN_RUST: String? = environment("SEVENTWOS_ANDROID_SDK_SENTRY_DSN")
    val BUG_REPORT_URL: String? = environment("SEVENTWOS_ANDROID_BUG_REPORT_URL")
    val BUG_REPORT_APP_NAME: String? = BUG_REPORT_URL?.let { "seventwos-workspace-android" }
    val CALLS_ENABLED: Boolean = environment("SEVENTWOS_ANDROID_CALLS_ENABLED").toBoolean()
    val FIREBASE_PUSH_GATEWAY: String? = environment("SEVENTWOS_ANDROID_FIREBASE_PUSH_GATEWAY")
    val UNIFIED_PUSH_GATEWAY: String? = environment("SEVENTWOS_ANDROID_UNIFIED_PUSH_GATEWAY")
    val UNIFIED_PUSH_DISTRIBUTORS_URL: String? = environment("SEVENTWOS_ANDROID_UNIFIED_PUSH_DISTRIBUTORS_URL")
    val PUSHER_APP_ID_RELEASE: String? = environment("SEVENTWOS_ANDROID_PUSHER_APP_ID")
    val PUSHER_APP_ID_DEBUG: String? = environment("SEVENTWOS_ANDROID_PUSHER_APP_ID_DEBUG")
    val PUSHER_APP_ID_NIGHTLY: String? = environment("SEVENTWOS_ANDROID_PUSHER_APP_ID_NIGHTLY")
    val PUSH_CONFIG_INCLUDE_FIREBASE: Boolean =
        environment("SEVENTWOS_ANDROID_ENABLE_FIREBASE").toBoolean() &&
            FIREBASE_PUSH_GATEWAY != null &&
            PUSHER_APP_ID_RELEASE != null
    val PUSH_CONFIG_INCLUDE_UNIFIED_PUSH: Boolean =
        environment("SEVENTWOS_ANDROID_ENABLE_UNIFIED_PUSH").toBoolean() &&
            UNIFIED_PUSH_GATEWAY != null &&
            UNIFIED_PUSH_DISTRIBUTORS_URL != null &&
            PUSHER_APP_ID_RELEASE != null
}
