#! /bin/bash

# Copyright (c) 2025 Element Creations Ltd.
# Copyright 2024 New Vector Ltd.
#
# SPDX-License-Identifier: AGPL-3.0-only.
# Please see LICENSE files in the repository root for full details.

adb shell am start -a android.intent.action.VIEW -c android.intent.category.BROWSABLE \
   -d "https://example.org/#/room/!cuqHozLHNBgupgLMKN:matrix.org/%24LZDOueY3R8OD2ZYf8FLKtu95aF7imLBC3F5TIUj-4cc"
