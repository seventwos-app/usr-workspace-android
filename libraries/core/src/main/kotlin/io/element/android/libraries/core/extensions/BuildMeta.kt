/*
 * Copyright (c) 2025 Element Creations Ltd.
 * Copyright 2024, 2025 New Vector Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only.
 * Please see LICENSE files in the repository root for full details.
 */

package io.element.android.libraries.core.extensions

import io.element.android.libraries.core.meta.BuildMeta
import io.element.android.libraries.core.meta.BuildType

/**
 * Returns `true` if this build is the Seventwos-owned production build of this application,
 * identified by its application id, for the given [BuildMeta.buildType].
 *
 * This capability check replaces a previous brand-specific `isElement()` gate; it is safe to
 * use for any application id configured through `BuildTimeConfig`, and is not tied to a
 * particular upstream brand.
 */
fun BuildMeta.isSeventwosWorkspace(): Boolean {
    return when (buildType) {
        BuildType.RELEASE -> applicationId == "org.seventwos.workspace"
        BuildType.NIGHTLY -> applicationId == "org.seventwos.workspace.nightly"
        BuildType.DEBUG -> applicationId == "org.seventwos.workspace.debug"
    }
}
