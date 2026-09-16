/*
 * Copyright (c) 2025 Element Creations Ltd.
 * Copyright 2023-2025 New Vector Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only.
 * Please see LICENSE files in the repository root for full details.
 */

package io.element.android.appconfig

object ApplicationConfig {
    /**
     * Application name used in the UI for string. If empty, the value is taken from the resources `R.string.app_name`.
     * Note that this value is not used for the launcher icon.
     * For Seventwos, the value is empty, and so read from `R.string.app_name`, which depends on the build variant
     * and [config.BuildTimeConfig.APPLICATION_NAME] (for instance "Seventwos Workspace dbg" for debug builds).
     */
    const val APPLICATION_NAME: String = ""

    /**
     * Used in the strings to reference the production client, for instance in onboarding and QR
     * code sign-in screens.
     * Cannot be empty.
     * For Seventwos, the value is "Seventwos Workspace".
     */
    const val PRODUCTION_APPLICATION_NAME: String = "Seventwos Workspace"

    /**
     * Used in the strings to reference the desktop client, for instance in QR code sign-in screens.
     * Cannot be empty.
     * For Seventwos, we use the same name for desktop and mobile for now.
     */
    const val DESKTOP_APPLICATION_NAME: String = "Seventwos Workspace"
}
