# Seventwos Workspace for Android

Seventwos Workspace for Android is the native Android client for the Seventwos workspace. It is built on top of a fork of [Element X Android](https://github.com/element-hq/element-x-android) and is being evolved for people and agents to communicate and collaborate over [Matrix](https://matrix.org/).

The project retains Element X's native-client approach: Jetpack Compose over the [Matrix Rust SDK](https://github.com/matrix-org/matrix-rust-sdk), exposed to Kotlin through its bindings. The shared Rust core provides Matrix synchronisation, local state, and end-to-end encryption while the application remains native to Android.

## Status

This repository is in transition from its Element X foundation to a separately authored Seventwos application layer.

The current code includes inherited Element X Android code, branding, and configuration. That inherited code remains subject to Element X's licence terms and must not be represented as an independent Seventwos implementation. The transition will replace the inherited application layer with Seventwos code while retaining the native-client architecture and the Apache-2.0 Matrix Rust SDK.

## Architecture

The intended Android implementation includes:

- Kotlin and Jetpack Compose.
- Matrix Rust SDK integration through Kotlin bindings.
- Client-side Matrix end-to-end encryption.
- Secure credential storage in the Android Keystore.
- Background synchronisation.
- Android push notifications for encrypted messages.

Element X is the upstream foundation and architectural reference for this workspace, not the target product identity.

## Repository role

The Seventwos workspace captures product intent and human direction. This repository captures the Android implementation, review history, and upstream attribution.

Changes should make the transition from inherited application code explicit and auditable. New product code should follow the repository's architecture and contribution rules.

## Provenance and licence

The current codebase is derived from Element X Android, which is dual-licensed under the GNU Affero General Public License v3 or a paid Element Commercial License.

Copyright (c) 2025 Element Creations Ltd.

Copyright (c) 2022 - 2025 New Vector Ltd.

See [LICENSE](LICENSE) and [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL) for the terms that apply to inherited code.

The licensing of future separately authored Seventwos components must be documented when those components are introduced. Their inclusion does not alter the licence obligations of inherited Element X code.
