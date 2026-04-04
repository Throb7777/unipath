package com.peter.paperharvestshare.data

import android.content.Context
import com.peter.paperharvestshare.BuildConfig
import com.peter.paperharvestshare.model.RelayClientConfig
import com.peter.paperharvestshare.model.RelayModeOption
import org.json.JSONArray
import org.json.JSONObject

class RelaySettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun currentAppLanguageTag(): String =
        prefs.getString(KEY_APP_LANGUAGE_TAG, "")
            .orEmpty()
            .trim()

    fun saveAppLanguageTag(languageTag: String) {
        prefs.edit()
            .putString(KEY_APP_LANGUAGE_TAG, languageTag.trim())
            .apply()
    }

    fun currentRelayBaseUrl(): String =
        normalizeBaseUrl(
            prefs.getString(KEY_RELAY_BASE_URL, BuildConfig.RELAY_BASE_URL)
                .orEmpty()
                .ifBlank { BuildConfig.RELAY_BASE_URL },
        )

    fun selectedModeId(): String =
        prefs.getString(KEY_SELECTED_MODE_ID, BuildConfig.RELAY_MODE)
            .orEmpty()
            .ifBlank { BuildConfig.RELAY_MODE }

    fun selectedModeLabel(): String =
        prefs.getString(KEY_SELECTED_MODE_LABEL, selectedModeId())
            .orEmpty()
            .ifBlank { selectedModeId() }

    fun selectedModeDescription(): String? =
        prefs.getString(KEY_SELECTED_MODE_DESCRIPTION, null)?.ifBlank { null }

    fun selectedModeSummary(): String =
        selectedModeDescription()?.let { "${selectedModeLabel()}\n$it" } ?: selectedModeLabel()

    fun saveSelection(relayBaseUrl: String, config: RelayClientConfig, mode: RelayModeOption) {
        val normalizedBaseUrl = normalizeBaseUrl(relayBaseUrl)
        prefs.edit()
            .putString(KEY_RELAY_BASE_URL, normalizedBaseUrl)
            .putString(KEY_SELECTED_MODE_ID, mode.id)
            .putString(KEY_SELECTED_MODE_LABEL, mode.label)
            .putString(KEY_SELECTED_MODE_DESCRIPTION, mode.description)
            .putString(KEY_LAST_SERVICE_NAME, config.serviceName)
            .putString(KEY_LAST_SERVICE_VERSION, config.serviceVersion)
            .putString(KEY_CACHED_CONFIG_BASE_URL, normalizedBaseUrl)
            .putString(KEY_CACHED_CONFIG_JSON, configToJson(config).toString())
            .apply()
    }

    fun saveClientConfig(relayBaseUrl: String, config: RelayClientConfig) {
        val normalizedBaseUrl = normalizeBaseUrl(relayBaseUrl)
        prefs.edit()
            .putString(KEY_LAST_SERVICE_NAME, config.serviceName)
            .putString(KEY_LAST_SERVICE_VERSION, config.serviceVersion)
            .putString(KEY_CACHED_CONFIG_BASE_URL, normalizedBaseUrl)
            .putString(KEY_CACHED_CONFIG_JSON, configToJson(config).toString())
            .apply()
    }

    fun cachedClientConfigFor(relayBaseUrl: String): RelayClientConfig? {
        val normalizedBaseUrl = normalizeBaseUrl(relayBaseUrl)
        val cachedBaseUrl = prefs.getString(KEY_CACHED_CONFIG_BASE_URL, null).orEmpty()
        if (cachedBaseUrl != normalizedBaseUrl) {
            return null
        }
        val raw = prefs.getString(KEY_CACHED_CONFIG_JSON, null).orEmpty()
        if (raw.isBlank()) {
            return null
        }
        return runCatching { configFromJson(JSONObject(raw)) }.getOrNull()
    }

    fun lastServiceSummary(): String? {
        val name = prefs.getString(KEY_LAST_SERVICE_NAME, null).orEmpty()
        val version = prefs.getString(KEY_LAST_SERVICE_VERSION, null).orEmpty()
        if (name.isBlank()) {
            return null
        }
        return if (version.isBlank()) name else "$name $version"
    }

    fun restoreDefaults() {
        prefs.edit()
            .putString(KEY_RELAY_BASE_URL, normalizeBaseUrl(BuildConfig.RELAY_BASE_URL))
            .putString(KEY_SELECTED_MODE_ID, BuildConfig.RELAY_MODE)
            .putString(KEY_SELECTED_MODE_LABEL, BuildConfig.RELAY_MODE)
            .remove(KEY_SELECTED_MODE_DESCRIPTION)
            .remove(KEY_LAST_SERVICE_NAME)
            .remove(KEY_LAST_SERVICE_VERSION)
            .remove(KEY_CACHED_CONFIG_BASE_URL)
            .remove(KEY_CACHED_CONFIG_JSON)
            .apply()
    }

    private fun configToJson(config: RelayClientConfig): JSONObject =
        JSONObject()
            .put("serviceName", config.serviceName)
            .put("serviceVersion", config.serviceVersion)
            .put("defaultModeId", config.defaultModeId)
            .put(
                "modes",
                JSONArray(
                    config.modes.map { mode ->
                        JSONObject()
                            .put("id", mode.id)
                            .put("label", mode.label)
                            .put("description", mode.description)
                            .put("enabled", mode.enabled)
                    },
                ),
            )

    private fun configFromJson(json: JSONObject): RelayClientConfig {
        val modes = buildList {
            val array = json.optJSONArray("modes") ?: JSONArray()
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                add(
                    RelayModeOption(
                        id = item.optString("id"),
                        label = item.optString("label").ifBlank { item.optString("id") },
                        description = item.optString("description"),
                        enabled = item.optBoolean("enabled", true),
                    ),
                )
            }
        }
        return RelayClientConfig(
            serviceName = json.optString("serviceName").ifBlank { "Relay" },
            serviceVersion = json.optString("serviceVersion"),
            defaultModeId = json.optString("defaultModeId").ifBlank { BuildConfig.RELAY_MODE },
            modes = modes,
        )
    }

    companion object {
        private const val PREFS_NAME = "relay_settings"
        private const val KEY_APP_LANGUAGE_TAG = "app_language_tag"
        private const val KEY_RELAY_BASE_URL = "relay_base_url"
        private const val KEY_SELECTED_MODE_ID = "selected_mode_id"
        private const val KEY_SELECTED_MODE_LABEL = "selected_mode_label"
        private const val KEY_SELECTED_MODE_DESCRIPTION = "selected_mode_description"
        private const val KEY_LAST_SERVICE_NAME = "last_service_name"
        private const val KEY_LAST_SERVICE_VERSION = "last_service_version"
        private const val KEY_CACHED_CONFIG_BASE_URL = "cached_config_base_url"
        private const val KEY_CACHED_CONFIG_JSON = "cached_config_json"

        fun normalizeBaseUrl(value: String): String =
            value.trim().trimEnd('/')
    }
}
