package com.peter.paperharvestshare.data

import android.content.Context
import com.peter.paperharvestshare.model.SourceType
import com.peter.paperharvestshare.model.SubmissionRecord
import com.peter.paperharvestshare.model.TaskState
import org.json.JSONArray
import org.json.JSONObject

class TaskStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private var cachedRaw: String? = null
    private var cachedRecords: List<SubmissionRecord>? = null

    @Synchronized
    fun upsert(record: SubmissionRecord) {
        val normalizedRecord = normalizeRecord(record)
        val current = loadAllInternal().toMutableList()
        val index = current.indexOfFirst { it.workId == normalizedRecord.workId }
        if (index >= 0) {
            val existing = current[index]
            val resolved = if (normalizedRecord.sequenceNumber > 0L) {
                normalizedRecord
            } else {
                normalizedRecord.copy(sequenceNumber = existing.sequenceNumber)
            }
            if (resolved == existing) {
                return
            }
            current[index] = resolved
        } else {
            val nextSequence = if (normalizedRecord.sequenceNumber > 0L) {
                normalizedRecord.sequenceNumber
            } else {
                (current.maxOfOrNull { it.sequenceNumber } ?: 0L) + 1L
            }
            current.add(0, normalizedRecord.copy(sequenceNumber = nextSequence))
        }

        val trimmed = current
            .sortedWith(compareByDescending<SubmissionRecord> { it.sequenceNumber }.thenByDescending { it.createdAtEpochMs })
            .take(MAX_STORED_RECORDS)

        val serialized = JSONArray(trimmed.map(::toJson)).toString()
        if (serialized == cachedRaw) {
            cachedRecords = trimmed
            return
        }

        prefs.edit().putString(KEY_TASKS_JSON, serialized).apply()
        cachedRaw = serialized
        cachedRecords = trimmed
    }

    @Synchronized
    fun getByWorkId(workId: String): SubmissionRecord? =
        loadAllInternal().firstOrNull { it.workId == workId }

    @Synchronized
    fun listRecent(limit: Int = DEFAULT_DISPLAY_LIMIT): List<SubmissionRecord> {
        val sorted = loadAllInternal()
            .sortedWith(compareByDescending<SubmissionRecord> { it.sequenceNumber }.thenByDescending { it.createdAtEpochMs })
        return if (limit <= 0) sorted else sorted.take(limit)
    }

    @Synchronized
    fun clear() {
        if (cachedRaw.isNullOrBlank() && prefs.getString(KEY_TASKS_JSON, null).isNullOrBlank()) {
            cachedRaw = null
            cachedRecords = emptyList()
            return
        }
        prefs.edit().remove(KEY_TASKS_JSON).apply()
        cachedRaw = null
        cachedRecords = emptyList()
    }

    private fun loadAllInternal(): List<SubmissionRecord> {
        val raw = prefs.getString(KEY_TASKS_JSON, null).orEmpty()
        if (cachedRaw == raw && cachedRecords != null) {
            return cachedRecords.orEmpty()
        }
        if (raw.isBlank()) {
            cachedRaw = raw
            cachedRecords = emptyList()
            return emptyList()
        }

        val parsed = buildList {
            val array = runCatching { JSONArray(raw) }.getOrNull() ?: return@buildList
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                fromJson(item)?.let(::add)
            }
        }
        cachedRaw = raw
        cachedRecords = parsed
        return parsed
    }

    private fun toJson(record: SubmissionRecord): JSONObject =
        JSONObject()
            .put("sequenceNumber", record.sequenceNumber)
            .put("clientSubmissionId", record.clientSubmissionId)
            .put("workId", record.workId)
            .put("sourceType", record.sourceType.name)
            .put("rawUrl", record.rawUrl)
            .put("normalizedUrl", record.normalizedUrl)
            .put("relayBaseUrlSnapshot", record.relayBaseUrlSnapshot)
            .put("modeIdSnapshot", record.modeIdSnapshot)
            .put("modeLabelSnapshot", record.modeLabelSnapshot)
            .put("relayStatusSnapshot", record.relayStatusSnapshot)
            .put("relayErrorCodeSnapshot", record.relayErrorCodeSnapshot)
            .put("relayDurationMsSnapshot", record.relayDurationMsSnapshot)
            .put("relayTimelineSnapshot", record.relayTimelineSnapshot)
            .put("state", record.state.name)
            .put("message", record.message)
            .put("relayTaskId", record.relayTaskId)
            .put("createdAtEpochMs", record.createdAtEpochMs)
            .put("updatedAtEpochMs", record.updatedAtEpochMs)
            .put("relayProblemTitleSnapshot", record.relayProblemTitleSnapshot)
            .put("relaySuggestedActionsSnapshot", JSONArray(record.relaySuggestedActionsSnapshot))
            .put("relayDiagnosticSummarySnapshot", record.relayDiagnosticSummarySnapshot)

    private fun fromJson(json: JSONObject): SubmissionRecord? {
        val normalizedUrl = json.optString("normalizedUrl")
        val workId = json.optString("workId")
        if (normalizedUrl.isBlank() || workId.isBlank()) {
            return null
        }

        return SubmissionRecord(
            sequenceNumber = if (json.has("sequenceNumber")) json.optLong("sequenceNumber") else 0L,
            clientSubmissionId = json.optString("clientSubmissionId"),
            workId = workId,
            sourceType = SourceType.valueOf(json.optString("sourceType", SourceType.UNKNOWN.name)),
            rawUrl = json.optString("rawUrl").ifBlank { null },
            normalizedUrl = normalizedUrl,
            relayBaseUrlSnapshot = json.optString("relayBaseUrlSnapshot").ifBlank { null },
            modeIdSnapshot = json.optString("modeIdSnapshot").ifBlank { null },
            modeLabelSnapshot = json.optString("modeLabelSnapshot").ifBlank { null },
            relayStatusSnapshot = json.optString("relayStatusSnapshot").ifBlank { null },
            relayErrorCodeSnapshot = json.optString("relayErrorCodeSnapshot").ifBlank { null },
            relayDurationMsSnapshot = if (json.has("relayDurationMsSnapshot")) json.optLong("relayDurationMsSnapshot") else null,
            relayTimelineSnapshot = json.optString("relayTimelineSnapshot").ifBlank { null },
            state = TaskState.valueOf(json.optString("state", TaskState.ENQUEUED.name)),
            message = json.optString("message"),
            relayTaskId = json.optString("relayTaskId").ifBlank { null },
            createdAtEpochMs = json.optLong("createdAtEpochMs"),
            updatedAtEpochMs = json.optLong("updatedAtEpochMs"),
            relayProblemTitleSnapshot = json.optString("relayProblemTitleSnapshot").ifBlank { null },
            relaySuggestedActionsSnapshot = buildList {
                val array = json.optJSONArray("relaySuggestedActionsSnapshot") ?: return@buildList
                for (index in 0 until array.length()) {
                    val value = array.optString(index).trim()
                    if (value.isNotBlank()) add(value)
                }
            },
            relayDiagnosticSummarySnapshot = json.optString("relayDiagnosticSummarySnapshot").ifBlank { null },
        )
    }

    companion object {
        const val MAX_STORED_RECORDS = 200
        const val DEFAULT_DISPLAY_LIMIT = 20
        private const val MESSAGE_LIMIT = 600
        private const val TIMELINE_LIMIT = 1800
        private const val DIAGNOSTIC_LIMIT = 1600
        private const val TITLE_LIMIT = 160
        private const val ACTION_LIMIT = 220
        private const val ACTION_COUNT_LIMIT = 3
        private const val PREFS_NAME = "task_store"
        private const val KEY_TASKS_JSON = "tasks_json"
    }

    private fun normalizeRecord(record: SubmissionRecord): SubmissionRecord =
        record.copy(
            message = trimText(record.message, MESSAGE_LIMIT),
            relayTimelineSnapshot = record.relayTimelineSnapshot?.let { trimText(it, TIMELINE_LIMIT) },
            relayProblemTitleSnapshot = record.relayProblemTitleSnapshot?.let { trimText(it, TITLE_LIMIT) },
            relaySuggestedActionsSnapshot = record.relaySuggestedActionsSnapshot
                .take(ACTION_COUNT_LIMIT)
                .map { trimText(it, ACTION_LIMIT) },
            relayDiagnosticSummarySnapshot = record.relayDiagnosticSummarySnapshot?.let { trimText(it, DIAGNOSTIC_LIMIT) },
        )

    private fun trimText(value: String, limit: Int): String {
        if (value.length <= limit) {
            return value
        }
        if (limit <= 1) {
            return value.take(limit)
        }
        val previewLimit = if (limit > 3) limit - 3 else limit
        return value.take(previewLimit).trimEnd() + "..."
    }
}
