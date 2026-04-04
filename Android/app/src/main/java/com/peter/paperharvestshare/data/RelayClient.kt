package com.peter.paperharvestshare.data

import com.peter.paperharvestshare.BuildConfig
import com.peter.paperharvestshare.model.RelayClientConfig
import com.peter.paperharvestshare.model.RelayModeOption
import com.peter.paperharvestshare.model.SourceType
import com.peter.paperharvestshare.util.AppLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class RelayClient {
    suspend fun safeSubmit(
        relayBaseUrl: String,
        modeId: String,
        sourceType: SourceType,
        rawSharedText: String,
        rawUrl: String?,
        normalizedUrl: String,
        clientSubmissionId: String,
    ): RelaySubmissionResult =
        try {
            submit(relayBaseUrl, modeId, sourceType, rawSharedText, rawUrl, normalizedUrl, clientSubmissionId)
        } catch (error: IOException) {
            AppLog.w(TAG, "Relay request failed before response: ${error.message}", error)
            RelaySubmissionResult(
                outcome = RelayOutcome.RETRYABLE_ERROR,
                message = error.message ?: "Network unavailable.",
                relayTaskId = null,
                httpCode = null,
            )
        }

    suspend fun safeFetchClientConfig(relayBaseUrl: String): RelayConfigFetchResult =
        try {
            fetchClientConfig(relayBaseUrl)
        } catch (error: IOException) {
            AppLog.w(TAG, "Relay config request failed: ${error.message}", error)
            RelayConfigFetchResult(
                success = false,
                config = null,
                message = error.message ?: "Network unavailable.",
                httpCode = null,
            )
        }

    suspend fun safeFetchTaskStatus(relayBaseUrl: String, relayTaskId: String): RelayTaskStatusFetchResult =
        try {
            fetchTaskStatus(relayBaseUrl, relayTaskId)
        } catch (error: IOException) {
            AppLog.w(TAG, "Relay task status request failed: ${error.message}", error)
            RelayTaskStatusFetchResult(
                success = false,
                status = null,
                message = error.message ?: "Network unavailable.",
                httpCode = null,
            )
        }

    suspend fun safeCancelTask(relayBaseUrl: String, relayTaskId: String): RelayCancelResult =
        try {
            cancelTask(relayBaseUrl, relayTaskId)
        } catch (error: IOException) {
            AppLog.w(TAG, "Relay cancel request failed: ${error.message}", error)
            RelayCancelResult(
                success = false,
                status = null,
                message = error.message ?: "Network unavailable.",
                httpCode = null,
            )
        }

    private suspend fun submit(
        relayBaseUrl: String,
        modeId: String,
        sourceType: SourceType,
        rawSharedText: String,
        rawUrl: String?,
        normalizedUrl: String,
        clientSubmissionId: String,
    ): RelaySubmissionResult = withContext(Dispatchers.IO) {
        val endpoint = "${RelaySettingsStore.normalizeBaseUrl(relayBaseUrl)}/api/share-submissions"
        AppLog.i(TAG, "POST $endpoint")
        val payload = JSONObject()
            .put("mode", modeId)
            .put("source", sourceType.wireValue)
            .put("rawText", rawSharedText)
            .put("rawUrl", rawUrl)
            .put("normalizedUrl", normalizedUrl)
            .put("clientSubmissionId", clientSubmissionId)
            .put("clientAppVersion", BuildConfig.VERSION_NAME)

        val requestBuilder = Request.Builder()
            .url(endpoint)
            .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
            .header("Accept", "application/json")

        attachAuth(requestBuilder)

        SHARED_CLIENT.newCall(requestBuilder.build()).execute().use { response ->
            AppLog.i(TAG, "Relay responded with HTTP ${response.code}")
            val bodyText = response.body?.string().orEmpty()
            val json = parseJsonObject(bodyText)
            val message = json?.optString("message").orEmpty().ifBlank {
                bodyText.trim().ifBlank {
                    if (response.isSuccessful) {
                        "Relay accepted the submission."
                    } else {
                        "Relay returned an empty response."
                    }
                }
            }
            val relayTaskId = json?.optString("taskId").orEmpty().ifBlank { null }

            when {
                response.code in 200..299 -> RelaySubmissionResult(
                    outcome = RelayOutcome.ACCEPTED,
                    message = message,
                    relayTaskId = relayTaskId,
                    httpCode = response.code,
                )

                response.code == 408 || response.code == 429 || response.code >= 500 -> RelaySubmissionResult(
                    outcome = RelayOutcome.RETRYABLE_ERROR,
                    message = message,
                    relayTaskId = relayTaskId,
                    httpCode = response.code,
                )

                else -> RelaySubmissionResult(
                    outcome = RelayOutcome.PERMANENT_ERROR,
                    message = message,
                    relayTaskId = relayTaskId,
                    httpCode = response.code,
                )
            }
        }
    }

    private suspend fun fetchClientConfig(relayBaseUrl: String): RelayConfigFetchResult = withContext(Dispatchers.IO) {
        val endpoint = "${RelaySettingsStore.normalizeBaseUrl(relayBaseUrl)}/api/client-config"
        AppLog.i(TAG, "GET $endpoint")
        val requestBuilder = Request.Builder()
            .url(endpoint)
            .get()
            .header("Accept", "application/json")

        attachAuth(requestBuilder)

        SHARED_CLIENT.newCall(requestBuilder.build()).execute().use { response ->
            val bodyText = response.body?.string().orEmpty()
            val json = parseJsonObject(bodyText)
            if (!response.isSuccessful || json == null) {
                return@withContext RelayConfigFetchResult(
                    success = false,
                    config = null,
                    message = bodyText.ifBlank { "Failed to load relay configuration." },
                    httpCode = response.code,
                )
            }

            val modes = buildList {
                val array = json.optJSONArray("modes")
                if (array != null) {
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
            }.filter { it.id.isNotBlank() }

            val config = RelayClientConfig(
                serviceName = json.optString("serviceName").ifBlank { "Relay" },
                serviceVersion = json.optString("serviceVersion"),
                defaultModeId = json.optString("defaultMode").ifBlank {
                    json.optString("defaultModeId").ifBlank { BuildConfig.RELAY_MODE }
                },
                modes = modes,
            )

            RelayConfigFetchResult(
                success = modes.isNotEmpty(),
                config = config,
                message = json.optString("message").ifBlank {
                    if (modes.isNotEmpty()) "Relay configuration loaded." else "Relay returned no modes."
                },
                httpCode = response.code,
            )
        }
    }

    private suspend fun fetchTaskStatus(relayBaseUrl: String, relayTaskId: String): RelayTaskStatusFetchResult = withContext(Dispatchers.IO) {
        val endpoint = "${RelaySettingsStore.normalizeBaseUrl(relayBaseUrl)}/api/share-submissions/$relayTaskId"
        AppLog.i(TAG, "GET $endpoint")
        val requestBuilder = Request.Builder()
            .url(endpoint)
            .get()
            .header("Accept", "application/json")

        attachAuth(requestBuilder)

        SHARED_CLIENT.newCall(requestBuilder.build()).execute().use { response ->
            val bodyText = response.body?.string().orEmpty()
            val json = parseJsonObject(bodyText)
            if (!response.isSuccessful || json == null) {
                return@withContext RelayTaskStatusFetchResult(
                    success = false,
                    status = null,
                    message = bodyText.ifBlank { "Failed to load relay task status." },
                    httpCode = response.code,
                )
            }

            RelayTaskStatusFetchResult(
                success = true,
                status = RelayTaskStatus(
                    taskId = json.optString("taskId"),
                    status = json.optString("status"),
                    stageLabel = json.optString("stageLabel"),
                    mode = json.optString("mode"),
                    source = json.optString("source"),
                    normalizedUrl = json.optString("normalizedUrl"),
                    resultSummary = json.optString("resultSummary"),
                    errorMessage = json.optString("errorMessage"),
                    errorCode = json.optString("errorCode"),
                    relayMessage = json.optString("relayMessage"),
                    executorKind = json.optString("executorKind"),
                    taskDir = json.optString("taskDir"),
                    problemTitle = json.optString("problemTitle"),
                    suggestedActions = parseStringList(json.optJSONArray("suggestedActions")),
                    diagnosticSummary = json.optString("diagnosticSummary"),
                    durationMs = if (json.has("durationMs")) json.optLong("durationMs") else null,
                    canCancel = json.optBoolean("canCancel", false),
                    timeline = parseTimeline(json),
                    createdAt = json.optString("createdAt"),
                    updatedAt = json.optString("updatedAt"),
                    startedAt = json.optString("startedAt").ifBlank { null },
                    completedAt = json.optString("completedAt").ifBlank { null },
                ),
                message = json.optString("relayMessage").ifBlank { "Relay task status loaded." },
                httpCode = response.code,
            )
        }
    }

    private suspend fun cancelTask(relayBaseUrl: String, relayTaskId: String): RelayCancelResult = withContext(Dispatchers.IO) {
        val endpoint = "${RelaySettingsStore.normalizeBaseUrl(relayBaseUrl)}/api/share-submissions/$relayTaskId/cancel"
        AppLog.i(TAG, "POST $endpoint")
        val requestBuilder = Request.Builder()
            .url(endpoint)
            .post("{}".toRequestBody(JSON_MEDIA_TYPE))
            .header("Accept", "application/json")

        attachAuth(requestBuilder)

        SHARED_CLIENT.newCall(requestBuilder.build()).execute().use { response ->
            val bodyText = response.body?.string().orEmpty()
            val json = parseJsonObject(bodyText)
            if (!response.isSuccessful || json == null) {
                return@withContext RelayCancelResult(
                    success = false,
                    status = null,
                    message = bodyText.ifBlank { "Failed to cancel relay task." },
                    httpCode = response.code,
                )
            }

            RelayCancelResult(
                success = true,
                status = RelayCancelStatus(
                    taskId = json.optString("taskId"),
                    status = json.optString("status"),
                    message = json.optString("message"),
                    canCancel = json.optBoolean("canCancel", false),
                ),
                message = json.optString("message").ifBlank { "Cancellation requested." },
                httpCode = response.code,
            )
        }
    }

    private fun attachAuth(requestBuilder: Request.Builder) {
        if (BuildConfig.RELAY_AUTH_TOKEN.isNotBlank()) {
            requestBuilder.header("Authorization", "Bearer ${BuildConfig.RELAY_AUTH_TOKEN}")
        }
    }

    private fun parseJsonObject(text: String): JSONObject? =
        runCatching { JSONObject(text) }.getOrNull()

    private fun parseTimeline(json: JSONObject): List<RelayTimelineEntry> =
        buildList {
            val array = json.optJSONArray("timeline") ?: return@buildList
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                add(
                    RelayTimelineEntry(
                        stepId = item.optString("stepId"),
                        label = item.optString("label"),
                        status = item.optString("status"),
                        at = item.optString("at"),
                        message = item.optString("message"),
                    ),
                )
            }
        }

    private fun parseStringList(array: org.json.JSONArray?): List<String> =
        buildList {
            if (array == null) return@buildList
            for (index in 0 until array.length()) {
                val value = array.optString(index).trim()
                if (value.isNotBlank()) {
                    add(value)
                }
            }
        }

    companion object {
        private const val TAG = "RelayClient"
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
        private val SHARED_CLIENT = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()
    }
}

enum class RelayOutcome {
    ACCEPTED,
    RETRYABLE_ERROR,
    PERMANENT_ERROR,
}

data class RelaySubmissionResult(
    val outcome: RelayOutcome,
    val message: String,
    val relayTaskId: String?,
    val httpCode: Int?,
)

data class RelayConfigFetchResult(
    val success: Boolean,
    val config: RelayClientConfig?,
    val message: String,
    val httpCode: Int?,
)

data class RelayTaskStatus(
    val taskId: String,
    val status: String,
    val stageLabel: String,
    val mode: String,
    val source: String,
    val normalizedUrl: String,
    val resultSummary: String,
    val errorMessage: String,
    val errorCode: String,
    val relayMessage: String,
    val executorKind: String,
    val taskDir: String,
    val problemTitle: String,
    val suggestedActions: List<String>,
    val diagnosticSummary: String,
    val durationMs: Long?,
    val canCancel: Boolean,
    val timeline: List<RelayTimelineEntry>,
    val createdAt: String,
    val updatedAt: String,
    val startedAt: String?,
    val completedAt: String?,
)

data class RelayTimelineEntry(
    val stepId: String,
    val label: String,
    val status: String,
    val at: String,
    val message: String,
)

data class RelayTaskStatusFetchResult(
    val success: Boolean,
    val status: RelayTaskStatus?,
    val message: String,
    val httpCode: Int?,
)

data class RelayCancelStatus(
    val taskId: String,
    val status: String,
    val message: String,
    val canCancel: Boolean,
)

data class RelayCancelResult(
    val success: Boolean,
    val status: RelayCancelStatus?,
    val message: String,
    val httpCode: Int?,
)
