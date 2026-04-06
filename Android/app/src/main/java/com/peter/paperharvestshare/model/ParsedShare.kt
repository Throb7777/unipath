package com.peter.paperharvestshare.model

data class ParsedShare(
    val rawSharedText: String,
    val extractedUrl: String?,
    val normalizedUrl: String?,
    val sourceType: SourceType,
    val errorMessage: String? = null,
) {
    val isValid: Boolean
        get() = normalizedUrl != null && errorMessage == null
}
