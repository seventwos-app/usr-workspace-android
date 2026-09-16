/*
 * Copyright (c) 2025 Element Creations Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only.
 * Please see LICENSE files in the repository root for full details.
 */

package io.element.android.libraries.matrix.impl.analytics

import io.element.android.libraries.core.extensions.runCatchingExceptions
import io.element.android.services.analytics.api.AnalyticsSdkSpan
import kotlinx.coroutines.DelicateCoroutinesApi
import org.matrix.rustcomponents.sdk.LogLevel
import org.matrix.rustcomponents.sdk.Span
import timber.log.Timber

// Must be kept in sync with the tracing target declared in PlatformInitializer.
private const val APP_TRACING_TARGET = "seventwos"

class RustAnalyticsSdkSpan(
    name: String? = null,
    private val parentTraceId: String?,
) : AnalyticsSdkSpan {
    private val inner = if (name != null) {
        Span(
            target = APP_TRACING_TARGET,
            name = name,
            file = "-",
            line = null,
            level = LogLevel.WARN,
            bridgeTraceId = parentTraceId,
        )
    } else {
        Span.newBridgeSpan(
            target = APP_TRACING_TARGET,
            parentTraceId = parentTraceId,
        )
    }

    override fun enter() {
        if (Span.current().isNone()) {
            inner.enter()
        } else {
            Timber.w("Not entering span sentry.trace='$parentTraceId' because another span is already active")
        }
    }

    @OptIn(DelicateCoroutinesApi::class)
    override fun exit() {
        inner.exit()
        runCatchingExceptions { inner.destroy() }
        Timber.d("Exited span sentry.trace='$parentTraceId'")
    }
}
