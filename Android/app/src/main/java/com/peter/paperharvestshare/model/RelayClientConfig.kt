package com.peter.paperharvestshare.model

data class RelayClientConfig(
    val serviceName: String,
    val serviceVersion: String,
    val defaultModeId: String,
    val modes: List<RelayModeOption>,
)
