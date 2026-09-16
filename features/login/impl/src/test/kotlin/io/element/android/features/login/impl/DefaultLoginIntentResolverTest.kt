/*
 * Copyright (c) 2025 Element Creations Ltd.
 * Copyright 2025 New Vector Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only.
 * Please see LICENSE files in the repository root for full details.
 */

package io.element.android.features.login.impl

import com.google.common.truth.Truth.assertThat
import io.element.android.features.login.api.LoginParams
import io.element.android.tests.testutils.robolectric.RobolectricTest
import org.junit.Test

class DefaultLoginIntentResolverTest : RobolectricTest() {
    @Test
    fun `nominal case`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://workspace.seventwos.org/login?account_provider=example.org&login_hint=mxid:@alice:example.org"
        assertThat(sut.parse(uriString)).isEqualTo(
            LoginParams(
                accountProvider = "example.org",
                loginHint = "mxid:@alice:example.org",
            )
        )
    }

    @Test
    fun `extra unknown param`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://workspace.seventwos.org/login?account_provider=example.org&login_hint=mxid:@alice:example.org&extra=uknown"
        assertThat(sut.parse(uriString)).isEqualTo(
            LoginParams(
                accountProvider = "example.org",
                loginHint = "mxid:@alice:example.org",
            )
        )
    }

    @Test
    fun `no account provider`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://workspace.seventwos.org/login?login_hint=mxid:@alice:example.org"
        assertThat(sut.parse(uriString)).isNull()
    }

    @Test
    fun `no path`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://workspace.seventwos.org?account_provider=example.org&login_hint=mxid:@alice:example.org"
        assertThat(sut.parse(uriString)).isNull()
    }

    @Test
    fun `wrong path`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://workspace.seventwos.org/wrong?account_provider=example.org&login_hint=mxid:@alice:example.org"
        assertThat(sut.parse(uriString)).isNull()
    }

    @Test
    fun `wrong host`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://wrong.seventwos.org/login?account_provider=example.org&login_hint=mxid:@alice:example.org"
        assertThat(sut.parse(uriString)).isNull()
    }

    @Test
    fun `no login_hint param`() {
        val sut = DefaultLoginIntentResolver()
        val uriString = "https://workspace.seventwos.org/login?account_provider=example.org"
        assertThat(sut.parse(uriString)).isEqualTo(
            LoginParams(
                accountProvider = "example.org",
                loginHint = null,
            )
        )
    }
}
