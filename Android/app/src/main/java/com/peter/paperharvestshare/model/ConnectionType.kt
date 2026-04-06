package com.peter.paperharvestshare.model

enum class ConnectionType(val storageValue: String) {
    EMULATOR("emulator"),
    LOCAL_NETWORK("local_network"),
    PRIVATE_NETWORK("private_network"),
    ;

    companion object {
        fun fromStorage(value: String?): ConnectionType? =
            entries.firstOrNull { it.storageValue == value?.trim() }
    }
}
