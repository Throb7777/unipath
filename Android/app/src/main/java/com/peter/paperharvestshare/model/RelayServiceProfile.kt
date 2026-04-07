package com.peter.paperharvestshare.model

data class RelayServiceProfile(
    val id: String,
    val displayName: String,
    val relayBaseUrl: String,
    val relayAuthToken: String,
    val connectionType: ConnectionType,
    val selectedModeId: String?,
    val selectedModeLabel: String?,
    val selectedModeDescription: String?,
    val lastServiceName: String?,
    val lastServiceVersion: String?,
    val cachedConfigJson: String?,
)
