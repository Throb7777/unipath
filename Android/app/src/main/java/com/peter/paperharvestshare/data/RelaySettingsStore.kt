package com.peter.paperharvestshare.data

import android.content.Context
import android.net.Uri
import com.peter.paperharvestshare.BuildConfig
import com.peter.paperharvestshare.model.ConnectionType
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

    fun hasSavedRelayBaseUrl(): Boolean =
        prefs.contains(KEY_RELAY_BASE_URL)

    fun currentRelayAuthToken(): String =
        prefs.getString(KEY_RELAY_AUTH_TOKEN, BuildConfig.RELAY_AUTH_TOKEN)
            .orEmpty()
            .trim()

    fun hasSavedRelayAuthToken(): Boolean =
        prefs.contains(KEY_RELAY_AUTH_TOKEN)

    fun currentConnectionType(): ConnectionType =
        ConnectionType.fromStorage(prefs.getString(KEY_CONNECTION_TYPE, null))
            ?: inferConnectionType(currentRelayBaseUrl())

    fun hasSavedConnectionType(): Boolean =
        prefs.contains(KEY_CONNECTION_TYPE)

    fun selectedModeId(): String =
        prefs.getString(KEY_SELECTED_MODE_ID, BuildConfig.RELAY_MODE)
            .orEmpty()
            .ifBlank { BuildConfig.RELAY_MODE }

    fun hasSavedModeSelection(): Boolean =
        prefs.contains(KEY_SELECTED_MODE_ID)

    fun selectedModeLabel(): String =
        prefs.getString(KEY_SELECTED_MODE_LABEL, selectedModeId())
            .orEmpty()
            .ifBlank { selectedModeId() }

    fun selectedModeDescription(): String? =
        prefs.getString(KEY_SELECTED_MODE_DESCRIPTION, null)?.ifBlank { null }

    fun selectedModeSummary(): String =
        selectedModeDescription()?.let { "${selectedModeLabel()}\n$it" } ?: selectedModeLabel()

    fun saveSelection(
        relayBaseUrl: String,
        relayAuthToken: String,
        connectionType: ConnectionType,
        config: RelayClientConfig,
        mode: RelayModeOption,
    ) {
        val normalizedBaseUrl = normalizeBaseUrl(relayBaseUrl)
        prefs.edit()
            .putString(KEY_RELAY_BASE_URL, normalizedBaseUrl)
            .putString(KEY_RELAY_AUTH_TOKEN, relayAuthToken.trim())
            .putString(KEY_CONNECTION_TYPE, connectionType.storageValue)
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
            .remove(KEY_RELAY_BASE_URL)
            .remove(KEY_RELAY_AUTH_TOKEN)
            .remove(KEY_CONNECTION_TYPE)
            .remove(KEY_SELECTED_MODE_ID)
            .remove(KEY_SELECTED_MODE_LABEL)
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
            serviceName = json.optString("serviceName").ifBlank { "UniPATH Forwarding Service" },
            serviceVersion = json.optString("serviceVersion"),
            defaultModeId = json.optString("defaultModeId").ifBlank { BuildConfig.RELAY_MODE },
            modes = modes,
        )
    }

    companion object {
        private const val PREFS_NAME = "relay_settings"
        private const val KEY_APP_LANGUAGE_TAG = "app_language_tag"
        private const val KEY_RELAY_BASE_URL = "relay_base_url"
        private const val KEY_RELAY_AUTH_TOKEN = "relay_auth_token"
        private const val KEY_CONNECTION_TYPE = "connection_type"
        private const val KEY_SELECTED_MODE_ID = "selected_mode_id"
        private const val KEY_SELECTED_MODE_LABEL = "selected_mode_label"
        private const val KEY_SELECTED_MODE_DESCRIPTION = "selected_mode_description"
        private const val KEY_LAST_SERVICE_NAME = "last_service_name"
        private const val KEY_LAST_SERVICE_VERSION = "last_service_version"
        private const val KEY_CACHED_CONFIG_BASE_URL = "cached_config_base_url"
        private const val KEY_CACHED_CONFIG_JSON = "cached_config_json"

        fun normalizeBaseUrl(value: String): String =
            value.trim().trimEnd('/')

        fun inferConnectionType(baseUrl: String): ConnectionType {
            val host = runCatching { Uri.parse(normalizeBaseUrl(baseUrl)).host.orEmpty().lowercase() }
                .getOrDefault("")
            return when {
                host == "10.0.2.2" -> ConnectionType.EMULATOR
                looksLikePrivateNetworkHost(host) -> ConnectionType.PRIVATE_NETWORK
                else -> ConnectionType.LOCAL_NETWORK
            }
        }

        fun looksLikePrivateNetworkHost(host: String): Boolean {
            val normalized = host.trim().lowercase()
            if (normalized.isBlank()) {
                return false
            }
            if (normalized.endsWith(".ts.net")) {
                return true
            }
            val parts = normalized.split(".")
            if (parts.size != 4) {
                return false
            }
            val octets = parts.mapNotNull { it.toIntOrNull() }
            if (octets.size != 4) {
                return false
            }
            return octets[0] == 100 && octets[1] in 64..127
        }

        fun looksLikeWildcardHost(host: String): Boolean =
            host.trim().equals("0.0.0.0", ignoreCase = true)

        fun looksLikeLoopbackHost(host: String): Boolean {
            val normalized = host.trim().lowercase()
            return normalized == "localhost" || normalized == "127.0.0.1" || normalized == "::1"
        }

        fun looksLikeLanHost(host: String): Boolean {
            val normalized = host.trim().lowercase()
            if (normalized.isBlank() || looksLikeLoopbackHost(normalized) || looksLikePrivateNetworkHost(normalized)) {
                return false
            }
            if (normalized.endsWith(".local")) {
                return true
            }
            val parts = normalized.split(".")
            if (parts.size != 4) {
                return false
            }
            val octets = parts.mapNotNull { it.toIntOrNull() }
            if (octets.size != 4) {
                return false
            }
            return when {
                octets[0] == 10 -> true
                octets[0] == 172 && octets[1] in 16..31 -> true
                octets[0] == 192 && octets[1] == 168 -> true
                else -> false
            }
        }
    }
}
