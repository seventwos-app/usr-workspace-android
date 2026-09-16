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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BuildMetaTest {
    @Test
    fun `isSeventwosWorkspace returns true for the release application id`() {
        assertTrue(aBuildMeta(buildType = BuildType.RELEASE, applicationId = "org.seventwos.workspace").isSeventwosWorkspace())
    }

    @Test
    fun `isSeventwosWorkspace returns true for the nightly application id`() {
        assertTrue(aBuildMeta(buildType = BuildType.NIGHTLY, applicationId = "org.seventwos.workspace.nightly").isSeventwosWorkspace())
    }

    @Test
    fun `isSeventwosWorkspace returns true for the debug application id`() {
        assertTrue(aBuildMeta(buildType = BuildType.DEBUG, applicationId = "org.seventwos.workspace.debug").isSeventwosWorkspace())
    }

    @Test
    fun `isSeventwosWorkspace returns false for an unrelated application id`() {
        assertFalse(aBuildMeta(buildType = BuildType.RELEASE, applicationId = "com.example.other").isSeventwosWorkspace())
    }

    @Test
    fun `isSeventwosWorkspace returns false when the build type and application id suffix mismatch`() {
        assertFalse(aBuildMeta(buildType = BuildType.RELEASE, applicationId = "org.seventwos.workspace.debug").isSeventwosWorkspace())
    }

    private fun aBuildMeta(
        buildType: BuildType,
        applicationId: String,
    ) = BuildMeta(
        buildType = buildType,
        isDebuggable = buildType == BuildType.DEBUG,
        applicationName = "Seventwos Workspace",
        productionApplicationName = "Seventwos Workspace",
        desktopApplicationName = "Seventwos Workspace",
        applicationId = applicationId,
        isEnterpriseBuild = false,
        lowPrivacyLoggingEnabled = false,
        versionName = "1.0.0",
        versionCode = 1L,
        gitRevision = "0000000",
        gitBranchName = "develop",
        flavorDescription = "",
        flavorShortDescription = "",
    )
}
