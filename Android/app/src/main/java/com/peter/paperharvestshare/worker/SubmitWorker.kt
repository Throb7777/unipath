package com.peter.paperharvestshare.worker

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.peter.paperharvestshare.BuildConfig
import com.peter.paperharvestshare.data.RelayClient
import com.peter.paperharvestshare.data.RelayOutcome
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.data.TaskStore
import com.peter.paperharvestshare.model.ParsedShare
import com.peter.paperharvestshare.model.SourceType
import com.peter.paperharvestshare.model.SubmissionRecord
import com.peter.paperharvestshare.model.TaskState
import com.peter.paperharvestshare.util.AppLog
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit

class SubmitWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    private val taskStore = TaskStore(appContext)
    private val relayClient = RelayClient()

    override suspend fun doWork(): Result {
        val clientSubmissionId = inputData.getString(KEY_CLIENT_SUBMISSION_ID).orEmpty()
        val rawSharedText = inputData.getString(KEY_RAW_SHARED_TEXT).orEmpty()
        val rawUrl = inputData.getString(KEY_RAW_URL)
        val normalizedUrl = inputData.getString(KEY_NORMALIZED_URL).orEmpty()
        val sourceType = SourceType.valueOf(inputData.getString(KEY_SOURCE_TYPE) ?: SourceType.UNKNOWN.name)
        val relayBaseUrl = inputData.getString(KEY_RELAY_BASE_URL).orEmpty()
        val modeId = inputData.getString(KEY_MODE_ID).orEmpty()
        val modeLabel = inputData.getString(KEY_MODE_LABEL)

        if (clientSubmissionId.isBlank() || normalizedUrl.isBlank() || relayBaseUrl.isBlank() || modeId.isBlank()) {
            AppLog.e(TAG, "Missing required task parameters.")
            return Result.failure(outputData(KEY_OUTPUT_MESSAGE to "Missing required task parameters."))
        }

        AppLog.i(TAG, "Starting relay submission for $normalizedUrl")

        val current = taskStore.getByWorkId(id.toString())
        val createdAt = current?.createdAtEpochMs ?: System.currentTimeMillis()
        taskStore.upsert(
            SubmissionRecord(
                clientSubmissionId = clientSubmissionId,
                workId = id.toString(),
                sourceType = sourceType,
                rawUrl = rawUrl,
                normalizedUrl = normalizedUrl,
                relayBaseUrlSnapshot = relayBaseUrl,
                modeIdSnapshot = modeId,
                modeLabelSnapshot = modeLabel,
                relayStatusSnapshot = null,
                relayErrorCodeSnapshot = current?.relayErrorCodeSnapshot,
                relayDurationMsSnapshot = current?.relayDurationMsSnapshot,
                relayTimelineSnapshot = current?.relayTimelineSnapshot,
                state = TaskState.RUNNING,
                message = "Submitting to relay.",
                relayTaskId = current?.relayTaskId,
                createdAtEpochMs = createdAt,
                updatedAtEpochMs = System.currentTimeMillis(),
            ),
        )

        val relayResult = relayClient.safeSubmit(
            relayBaseUrl = relayBaseUrl,
            modeId = modeId,
            sourceType = sourceType,
            rawSharedText = rawSharedText,
            rawUrl = rawUrl,
            normalizedUrl = normalizedUrl,
            clientSubmissionId = clientSubmissionId,
        )

        return when (relayResult.outcome) {
            RelayOutcome.ACCEPTED -> {
                AppLog.i(TAG, "Relay accepted submission. taskId=${relayResult.relayTaskId.orEmpty()}")
                taskStore.upsert(
                    SubmissionRecord(
                        clientSubmissionId = clientSubmissionId,
                        workId = id.toString(),
                        sourceType = sourceType,
                        rawUrl = rawUrl,
                        normalizedUrl = normalizedUrl,
                        relayBaseUrlSnapshot = relayBaseUrl,
                        modeIdSnapshot = modeId,
                        modeLabelSnapshot = modeLabel,
                        relayStatusSnapshot = null,
                        relayErrorCodeSnapshot = null,
                        relayDurationMsSnapshot = null,
                        relayTimelineSnapshot = null,
                        state = TaskState.SUCCEEDED,
                        message = relayResult.message,
                        relayTaskId = relayResult.relayTaskId,
                        createdAtEpochMs = createdAt,
                        updatedAtEpochMs = System.currentTimeMillis(),
                    ),
                )
                Result.success(
                    outputData(
                        KEY_OUTPUT_MESSAGE to relayResult.message,
                        KEY_OUTPUT_RELAY_TASK_ID to relayResult.relayTaskId.orEmpty(),
                    ),
                )
            }

            RelayOutcome.RETRYABLE_ERROR -> {
                AppLog.w(TAG, "Retryable relay error: ${relayResult.message}")
                taskStore.upsert(
                    SubmissionRecord(
                        clientSubmissionId = clientSubmissionId,
                        workId = id.toString(),
                        sourceType = sourceType,
                        rawUrl = rawUrl,
                        normalizedUrl = normalizedUrl,
                        relayBaseUrlSnapshot = relayBaseUrl,
                        modeIdSnapshot = modeId,
                        modeLabelSnapshot = modeLabel,
                        relayStatusSnapshot = null,
                        relayErrorCodeSnapshot = null,
                        relayDurationMsSnapshot = null,
                        relayTimelineSnapshot = null,
                        state = TaskState.RETRYING,
                        message = relayResult.message,
                        relayTaskId = relayResult.relayTaskId,
                        createdAtEpochMs = createdAt,
                        updatedAtEpochMs = System.currentTimeMillis(),
                    ),
                )
                Result.retry()
            }

            RelayOutcome.PERMANENT_ERROR -> {
                AppLog.e(TAG, "Permanent relay error: ${relayResult.message}")
                taskStore.upsert(
                    SubmissionRecord(
                        clientSubmissionId = clientSubmissionId,
                        workId = id.toString(),
                        sourceType = sourceType,
                        rawUrl = rawUrl,
                        normalizedUrl = normalizedUrl,
                        relayBaseUrlSnapshot = relayBaseUrl,
                        modeIdSnapshot = modeId,
                        modeLabelSnapshot = modeLabel,
                        relayStatusSnapshot = null,
                        relayErrorCodeSnapshot = null,
                        relayDurationMsSnapshot = null,
                        relayTimelineSnapshot = null,
                        state = TaskState.FAILED,
                        message = relayResult.message,
                        relayTaskId = relayResult.relayTaskId,
                        createdAtEpochMs = createdAt,
                        updatedAtEpochMs = System.currentTimeMillis(),
                    ),
                )
                Result.failure(
                    outputData(
                        KEY_OUTPUT_MESSAGE to relayResult.message,
                        KEY_OUTPUT_RELAY_TASK_ID to relayResult.relayTaskId.orEmpty(),
                    ),
                )
            }
        }
    }

    companion object {
        private const val UNIQUE_PREFIX = "paper_harvest"
        private const val TAG = "SubmitWorker"
        const val KEY_CLIENT_SUBMISSION_ID = "client_submission_id"
        const val KEY_RAW_SHARED_TEXT = "raw_shared_text"
        const val KEY_RAW_URL = "raw_url"
        const val KEY_NORMALIZED_URL = "normalized_url"
        const val KEY_SOURCE_TYPE = "source_type"
        const val KEY_RELAY_BASE_URL = "relay_base_url"
        const val KEY_MODE_ID = "mode_id"
        const val KEY_MODE_LABEL = "mode_label"
        const val KEY_OUTPUT_MESSAGE = "output_message"
        const val KEY_OUTPUT_RELAY_TASK_ID = "output_relay_task_id"

        fun enqueue(context: Context, parsedShare: ParsedShare): UUID {
            val settingsStore = RelaySettingsStore(context)
            val relayBaseUrl = settingsStore.currentRelayBaseUrl()
            val modeId = settingsStore.selectedModeId().ifBlank { BuildConfig.RELAY_MODE }
            val modeLabel = settingsStore.selectedModeLabel().ifBlank { modeId }
            val clientSubmissionId = UUID.randomUUID().toString()
            val workRequest = OneTimeWorkRequestBuilder<SubmitWorker>()
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
                .setInputData(
                    Data.Builder()
                        .putString(KEY_CLIENT_SUBMISSION_ID, clientSubmissionId)
                        .putString(KEY_RAW_SHARED_TEXT, parsedShare.rawSharedText)
                        .putString(KEY_RAW_URL, parsedShare.extractedUrl)
                        .putString(KEY_NORMALIZED_URL, parsedShare.normalizedUrl)
                        .putString(KEY_SOURCE_TYPE, parsedShare.sourceType.name)
                        .putString(KEY_RELAY_BASE_URL, relayBaseUrl)
                        .putString(KEY_MODE_ID, modeId)
                        .putString(KEY_MODE_LABEL, modeLabel)
                        .build(),
                )
                .build()

            val now = System.currentTimeMillis()
            TaskStore(context).upsert(
                SubmissionRecord(
                    clientSubmissionId = clientSubmissionId,
                    workId = workRequest.id.toString(),
                    sourceType = parsedShare.sourceType,
                    rawUrl = parsedShare.extractedUrl,
                    normalizedUrl = parsedShare.normalizedUrl.orEmpty(),
                    relayBaseUrlSnapshot = relayBaseUrl,
                    modeIdSnapshot = modeId,
                    modeLabelSnapshot = modeLabel,
                    relayStatusSnapshot = null,
                    relayErrorCodeSnapshot = null,
                    relayDurationMsSnapshot = null,
                    relayTimelineSnapshot = null,
                    state = TaskState.ENQUEUED,
                    message = "Queued for relay submission.",
                    relayTaskId = null,
                    createdAtEpochMs = now,
                    updatedAtEpochMs = now,
                ),
            )

            WorkManager.getInstance(context).enqueueUniqueWork(
                "$UNIQUE_PREFIX:${sha256(parsedShare.normalizedUrl.orEmpty())}:$modeId",
                ExistingWorkPolicy.REPLACE,
                workRequest,
            )

            return workRequest.id
        }

        private fun sha256(value: String): String =
            MessageDigest.getInstance("SHA-256")
                .digest(value.toByteArray())
                .joinToString("") { "%02x".format(it) }
    }
}

private fun outputData(vararg values: Pair<String, String>): Data =
    Data.Builder().apply {
        values.forEach { (key, value) -> putString(key, value) }
    }.build()
