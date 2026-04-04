package com.peter.paperharvestshare.util

import android.content.Context
import androidx.annotation.StringRes
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelaySettingsStore
import java.util.Locale

enum class AppLanguage(
    val tag: String,
    @StringRes val labelResId: Int,
) {
    ENGLISH("en", R.string.language_english),
    SIMPLIFIED_CHINESE("zh-CN", R.string.language_simplified_chinese),
    ;

    companion object {
        fun fromTag(tag: String?): AppLanguage? =
            entries.firstOrNull { it.tag.equals(tag.orEmpty().trim(), ignoreCase = true) }

        fun fromResolvedLocale(locale: Locale): AppLanguage =
            if (locale.language.equals("zh", ignoreCase = true)) {
                SIMPLIFIED_CHINESE
            } else {
                ENGLISH
            }
    }
}

object AppLanguageManager {
    fun applyStoredLanguage(context: Context) {
        val stored = RelaySettingsStore(context).currentAppLanguageTag()
        val language = AppLanguage.fromTag(stored) ?: return
        applyLanguage(language)
    }

    fun currentSelectionForUi(context: Context): AppLanguage {
        val stored = RelaySettingsStore(context).currentAppLanguageTag()
        return AppLanguage.fromTag(stored)
            ?: AppLanguage.fromResolvedLocale(currentResolvedLocale())
    }

    fun saveAndApply(context: Context, language: AppLanguage) {
        RelaySettingsStore(context).saveAppLanguageTag(language.tag)
        applyLanguage(language)
    }

    private fun applyLanguage(language: AppLanguage) {
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(language.tag))
    }

    private fun currentResolvedLocale(): Locale {
        val appLocales = AppCompatDelegate.getApplicationLocales()
        val first = appLocales[0]
        return first ?: Locale.getDefault()
    }
}
