/*
 * Copyright (c) 2025 Element Creations Ltd.
 * Copyright 2023-2025 New Vector Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only.
 * Please see LICENSE files in the repository root for full details.
 */

package io.element.android.appconfig

/**
 * "Learn more" destinations for in-app help topics.
 *
 * These previously pointed at Element's own help site (element.io). Seventwos does not yet
 * publish equivalent help pages, so each URL is `null` until a Seventwos-owned page exists for
 * that topic. Callers must treat `null` as "no link available" and fail closed (hide or disable
 * the affordance) rather than falling back to an upstream Element URL.
 */
object LearnMoreConfig {
    val ENCRYPTION_URL: String? = null
    val DEVICE_VERIFICATION_URL: String? = null
    val SECURE_BACKUP_URL: String? = null
    val IDENTITY_CHANGE_URL: String? = null
    val HISTORY_VISIBLE_URL: String? = null
}
