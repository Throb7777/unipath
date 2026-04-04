package com.peter.paperharvestshare.util

import android.content.Context
import android.net.Uri
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.model.ParsedShare
import com.peter.paperharvestshare.model.SourceType

object UrlNormalizer {
    private val urlRegex = Regex("""https?://[^\s<>"']+""", RegexOption.IGNORE_CASE)
    private val removablePunctuationTypes = setOf(
        Character.CONNECTOR_PUNCTUATION.toInt(),
        Character.DASH_PUNCTUATION.toInt(),
        Character.END_PUNCTUATION.toInt(),
        Character.FINAL_QUOTE_PUNCTUATION.toInt(),
        Character.INITIAL_QUOTE_PUNCTUATION.toInt(),
        Character.OTHER_PUNCTUATION.toInt(),
        Character.START_PUNCTUATION.toInt(),
    )

    fun parse(context: Context, sharedText: String?): ParsedShare {
        val text = sharedText?.trim().orEmpty()
        if (text.isBlank()) {
            return ParsedShare(
                rawSharedText = "",
                extractedUrl = null,
                normalizedUrl = null,
                sourceType = SourceType.UNKNOWN,
                errorMessage = context.getString(R.string.share_error_no_text),
            )
        }

        val extracted = extractFirstUrl(text)
            ?: return ParsedShare(
                rawSharedText = text,
                extractedUrl = null,
                normalizedUrl = null,
                sourceType = SourceType.UNKNOWN,
                errorMessage = context.getString(R.string.share_error_no_url),
            )

        val uri = runCatching { Uri.parse(extracted) }.getOrNull()
            ?: return ParsedShare(
                rawSharedText = text,
                extractedUrl = extracted,
                normalizedUrl = null,
                sourceType = SourceType.UNKNOWN,
                errorMessage = context.getString(R.string.share_error_no_url),
            )

        val host = uri.host?.lowercase().orEmpty()
        return when {
            host == "mp.weixin.qq.com" -> ParsedShare(
                rawSharedText = text,
                extractedUrl = extracted,
                normalizedUrl = normalizeWechatArticle(uri),
                sourceType = SourceType.WECHAT_ARTICLE,
            )

            host.endsWith("xiaohongshu.com") || host == "xhslink.com" || host.endsWith(".xhslink.com") -> ParsedShare(
                rawSharedText = text,
                extractedUrl = extracted,
                normalizedUrl = stripFragment(uri),
                sourceType = SourceType.XIAOHONGSHU,
            )

            else -> ParsedShare(
                rawSharedText = text,
                extractedUrl = extracted,
                normalizedUrl = null,
                sourceType = SourceType.UNKNOWN,
                errorMessage = context.getString(R.string.share_error_unsupported),
            )
        }
    }

    private fun extractFirstUrl(text: String): String? {
        val match = urlRegex.find(text) ?: return null
        return trimTrailingPunctuation(match.value)
    }

    private fun trimTrailingPunctuation(value: String): String {
        var end = value.length
        while (end > 0) {
            val lastChar = value[end - 1]
            val lastType = Character.getType(lastChar)
            if (lastType !in removablePunctuationTypes) {
                break
            }
            end -= 1
        }
        return value.substring(0, end)
    }

    private fun normalizeWechatArticle(uri: Uri): String {
        val canonicalKeys = listOf("__biz", "mid", "idx", "sn")
        val values = canonicalKeys.associateWith { uri.getQueryParameter(it).orEmpty() }
        if (values.values.any { it.isBlank() }) {
            return stripFragment(uri)
        }

        return Uri.Builder()
            .scheme("https")
            .authority("mp.weixin.qq.com")
            .path("/s")
            .apply {
                canonicalKeys.forEach { key ->
                    appendQueryParameter(key, values.getValue(key))
                }
            }
            .build()
            .toString()
    }

    private fun stripFragment(uri: Uri): String =
        uri.buildUpon()
            .fragment(null)
            .build()
            .toString()
}
