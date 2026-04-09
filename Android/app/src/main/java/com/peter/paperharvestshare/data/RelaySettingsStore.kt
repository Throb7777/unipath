package com.peter.paperharvestshare.data

import android.content.Context
import android.net.Uri
import com.peter.paperharvestshare.BuildConfig
import com.peter.paperharvestshare.model.ConnectionType
import com.peter.paperharvestshare.model.RelayClientConfig
import com.peter.paperharvestshare.model.RelayModeOption
import com.peter.paperharvestshare.model.RelayServiceProfile
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

    fun currentRecentTaskLimit(): Int =
        prefs.getInt(KEY_RECENT_TASK_LIMIT, DEFAULT_RECENT_TASK_LIMIT)
            .takeIf { it in RECENT_TASK_LIMIT_OPTIONS }
            ?: DEFAULT_RECENT_TASK_LIMIT

    fun saveRecentTaskLimit(limit: Int) {
        val normalized = if (limit in RECENT_TASK_LIMIT_OPTIONS) limit else DEFAULT_RECENT_TASK_LIMIT
        prefs.edit().putInt(KEY_RECENT_TASK_LIMIT, normalized).apply()
    }

    fun savedProfiles(): List<RelayServiceProfile> {
        val stored = loadSavedProfiles()
        return if (stored.isNotEmpty()) {
            stored
        } else {
            legacyCurrentProfile()?.let(::listOf).orEmpty()
        }
    }

    fun currentProfileId(): String? =
        prefs.getString(KEY_CURRENT_PROFILE_ID, null)?.ifBlank { null }

    fun currentProfile(): RelayServiceProfile? {
        val currentId = currentProfileId()
        return savedProfiles().firstOrNull { it.id == currentId } ?: legacyCurrentProfile()
    }

    fun switchToProfile(profileId: String): Boolean {
        val profile = loadSavedProfiles().firstOrNull { it.id == profileId } ?: return false
        writeCurrentSelection(profile)
        return true
    }

    fun deleteProfile(profileId: String): Boolean {
        val remaining = loadSavedProfiles().filterNot { it.id == profileId }
        val currentId = currentProfileId()
        saveProfiles(remaining)
        return when {
            remaining.isEmpty() && currentId == profileId -> {
                clearCurrentSelection()
                true
            }
            currentId == profileId -> {
                writeCurrentSelection(remaining.first())
                true
            }
            else -> true
        }
    }

    fun saveSelection(
        relayBaseUrl: String,
        relayAuthToken: String,
        connectionType: ConnectionType,
        config: RelayClientConfig,
        mode: RelayModeOption,
        profileDisplayName: String? = null,
    ) {
        val normalizedBaseUrl = normalizeBaseUrl(relayBaseUrl)
        val cachedConfigJson = configToJson(config).toString()
        val profileId = buildProfileId(normalizedBaseUrl)
        val displayName = profileDisplayName
            ?.trim()
            ?.takeIf { it.isNotBlank() }
            ?: deriveProfileDisplayName(normalizedBaseUrl, config.serviceName)
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
            .putString(KEY_CACHED_CONFIG_JSON, cachedConfigJson)
            .putString(KEY_CURRENT_PROFILE_ID, profileId)
            .apply()
        upsertProfile(
            RelayServiceProfile(
                id = profileId,
                displayName = displayName,
                relayBaseUrl = normalizedBaseUrl,
                relayAuthToken = relayAuthToken.trim(),
                connectionType = connectionType,
                selectedModeId = mode.id,
                selectedModeLabel = mode.label,
                selectedModeDescription = mode.description,
                lastServiceName = config.serviceName,
                lastServiceVersion = config.serviceVersion,
                cachedConfigJson = cachedConfigJson,
            ),
        )
    }

    fun saveClientConfig(relayBaseUrl: String, config: RelayClientConfig) {
        val normalizedBaseUrl = normalizeBaseUrl(relayBaseUrl)
        val cachedConfigJson = configToJson(config).toString()
        prefs.edit()
            .putString(KEY_LAST_SERVICE_NAME, config.serviceName)
            .putString(KEY_LAST_SERVICE_VERSION, config.serviceVersion)
            .putString(KEY_CACHED_CONFIG_BASE_URL, normalizedBaseUrl)
            .putString(KEY_CACHED_CONFIG_JSON, cachedConfigJson)
            .apply()
        updateProfileMetadata(
            buildProfileId(normalizedBaseUrl),
            config.serviceName,
            config.serviceVersion,
            cachedConfigJson,
        )
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
            .remove(KEY_CURRENT_PROFILE_ID)
            .apply()
    }

    fun updateSelectedMode(mode: RelayModeOption) {
        prefs.edit()
            .putString(KEY_SELECTED_MODE_ID, mode.id)
            .putString(KEY_SELECTED_MODE_LABEL, mode.label)
            .putString(KEY_SELECTED_MODE_DESCRIPTION, mode.description)
            .apply()
        currentProfileId()?.let { profileId ->
            val updated = loadSavedProfiles().map { profile ->
                if (profile.id == profileId) {
                    profile.copy(
                        selectedModeId = mode.id,
                        selectedModeLabel = mode.label,
                        selectedModeDescription = mode.description,
                    )
                } else {
                    profile
                }
            }
            saveProfiles(updated)
        }
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

    private fun upsertProfile(profile: RelayServiceProfile) {
        val updated = loadSavedProfiles()
            .filterNot { it.id == profile.id }
            .plus(profile)
            .sortedBy { it.displayName.lowercase() }
        saveProfiles(updated)
    }

    private fun updateProfileMetadata(
        profileId: String,
        serviceName: String,
        serviceVersion: String,
        cachedConfigJson: String,
    ) {
        val updated = loadSavedProfiles().map { profile ->
            if (profile.id == profileId) {
                val existingDerived = deriveProfileDisplayName(profile.relayBaseUrl, profile.lastServiceName)
                val replacementDerived = deriveProfileDisplayName(profile.relayBaseUrl, serviceName)
                profile.copy(
                    displayName = when {
                        profile.displayName.isBlank() -> replacementDerived
                        profile.displayName == existingDerived -> replacementDerived
                        else -> profile.displayName
                    },
                    lastServiceName = serviceName,
                    lastServiceVersion = serviceVersion,
                    cachedConfigJson = cachedConfigJson,
                )
            } else {
                profile
            }
        }
        if (updated.isNotEmpty()) {
            saveProfiles(updated)
        }
    }

    private fun loadSavedProfiles(): List<RelayServiceProfile> {
        val raw = prefs.getString(KEY_SAVED_PROFILES_JSON, null).orEmpty()
        if (raw.isBlank()) {
            return emptyList()
        }
        val array = runCatching { JSONArray(raw) }.getOrNull() ?: return emptyList()
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                val relayBaseUrl = item.optString("relayBaseUrl").ifBlank { null } ?: continue
                val id = item.optString("id").ifBlank { buildProfileId(relayBaseUrl) }
                add(
                    RelayServiceProfile(
                        id = id,
                        displayName = item.optString("displayName").ifBlank {
                            deriveProfileDisplayName(relayBaseUrl, item.optString("lastServiceName"))
                        },
                        relayBaseUrl = normalizeBaseUrl(relayBaseUrl),
                        relayAuthToken = item.optString("relayAuthToken"),
                        connectionType = ConnectionType.fromStorage(item.optString("connectionType"))
                            ?: inferConnectionType(relayBaseUrl),
                        selectedModeId = item.optString("selectedModeId").ifBlank { null },
                        selectedModeLabel = item.optString("selectedModeLabel").ifBlank { null },
                        selectedModeDescription = item.optString("selectedModeDescription").ifBlank { null },
                        lastServiceName = item.optString("lastServiceName").ifBlank { null },
                        lastServiceVersion = item.optString("lastServiceVersion").ifBlank { null },
                        cachedConfigJson = item.optString("cachedConfigJson").ifBlank { null },
                    ),
                )
            }
        }
    }

    private fun saveProfiles(profiles: List<RelayServiceProfile>) {
        val serialized = JSONArray(
            profiles.map { profile ->
                JSONObject()
                    .put("id", profile.id)
                    .put("displayName", profile.displayName)
                    .put("relayBaseUrl", profile.relayBaseUrl)
                    .put("relayAuthToken", profile.relayAuthToken)
                    .put("connectionType", profile.connectionType.storageValue)
                    .put("selectedModeId", profile.selectedModeId)
                    .put("selectedModeLabel", profile.selectedModeLabel)
                    .put("selectedModeDescription", profile.selectedModeDescription)
                    .put("lastServiceName", profile.lastServiceName)
                    .put("lastServiceVersion", profile.lastServiceVersion)
                    .put("cachedConfigJson", profile.cachedConfigJson)
            },
        ).toString()
        prefs.edit().putString(KEY_SAVED_PROFILES_JSON, serialized).apply()
    }

    private fun legacyCurrentProfile(): RelayServiceProfile? {
        if (!hasSavedRelayBaseUrl()) {
            return null
        }
        val relayBaseUrl = currentRelayBaseUrl()
        return RelayServiceProfile(
            id = buildProfileId(relayBaseUrl),
            displayName = deriveProfileDisplayName(relayBaseUrl, prefs.getString(KEY_LAST_SERVICE_NAME, null)),
            relayBaseUrl = relayBaseUrl,
            relayAuthToken = currentRelayAuthToken(),
            connectionType = currentConnectionType(),
            selectedModeId = selectedModeId(),
            selectedModeLabel = selectedModeLabel(),
            selectedModeDescription = selectedModeDescription(),
            lastServiceName = prefs.getString(KEY_LAST_SERVICE_NAME, null),
            lastServiceVersion = prefs.getString(KEY_LAST_SERVICE_VERSION, null),
            cachedConfigJson = prefs.getString(KEY_CACHED_CONFIG_JSON, null),
        )
    }

    private fun writeCurrentSelection(profile: RelayServiceProfile) {
        val normalizedBaseUrl = normalizeBaseUrl(profile.relayBaseUrl)
        prefs.edit()
            .putString(KEY_RELAY_BASE_URL, normalizedBaseUrl)
            .putString(KEY_RELAY_AUTH_TOKEN, profile.relayAuthToken)
            .putString(KEY_CONNECTION_TYPE, profile.connectionType.storageValue)
            .putString(KEY_SELECTED_MODE_ID, profile.selectedModeId)
            .putString(KEY_SELECTED_MODE_LABEL, profile.selectedModeLabel)
            .putString(KEY_SELECTED_MODE_DESCRIPTION, profile.selectedModeDescription)
            .putString(KEY_LAST_SERVICE_NAME, profile.lastServiceName)
            .putString(KEY_LAST_SERVICE_VERSION, profile.lastServiceVersion)
            .putString(KEY_CACHED_CONFIG_BASE_URL, normalizedBaseUrl)
            .putString(KEY_CACHED_CONFIG_JSON, profile.cachedConfigJson)
            .putString(KEY_CURRENT_PROFILE_ID, profile.id)
            .apply()
    }

    private fun clearCurrentSelection() {
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
            .remove(KEY_CURRENT_PROFILE_ID)
            .apply()
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
        private const val KEY_SAVED_PROFILES_JSON = "saved_profiles_json"
        private const val KEY_CURRENT_PROFILE_ID = "current_profile_id"
        private const val KEY_RECENT_TASK_LIMIT = "recent_task_limit"

        const val DEFAULT_RECENT_TASK_LIMIT = 20
        val RECENT_TASK_LIMIT_OPTIONS = setOf(5, 10, 20, 0)

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

        fun buildProfileId(baseUrl: String): String =
            normalizeBaseUrl(baseUrl).lowercase()

        fun deriveProfileDisplayName(baseUrl: String, serviceName: String?): String {
            val host = runCatching { Uri.parse(normalizeBaseUrl(baseUrl)).host.orEmpty() }.getOrDefault("")
                .removePrefix("www.")
                .ifBlank { normalizeBaseUrl(baseUrl) }
            val cleanServiceName = serviceName.orEmpty().trim()
            return when {
                cleanServiceName.isBlank() -> host
                cleanServiceName.equals("UniPATH Forwarding Service", ignoreCase = true) -> host
                cleanServiceName.contains(host, ignoreCase = true) -> cleanServiceName
                else -> "$cleanServiceName ($host)"
            }
        }
    }
}
