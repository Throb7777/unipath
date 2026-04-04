package com.peter.paperharvestshare.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.DrawableCompat
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelayClient
import com.peter.paperharvestshare.data.RelayTaskStatus
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.data.TaskStore
import com.peter.paperharvestshare.databinding.ActivityMainBinding
import com.peter.paperharvestshare.databinding.ViewRecentTaskBinding
import com.peter.paperharvestshare.model.SourceType
import com.peter.paperharvestshare.model.SubmissionRecord
import com.peter.paperharvestshare.model.TaskState
import com.peter.paperharvestshare.util.SystemBarInsets
import com.peter.paperharvestshare.util.UiText
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.max

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var taskStore: TaskStore
    private lateinit var settingsStore: RelaySettingsStore
    private val relayClient = RelayClient()

    private var lastConfigRenderKey: String? = null
    private var lastRecentRenderKey: String? = null
    private var recentSyncJob: Job? = null
    private val recentSyncTimestamps = mutableMapOf<String, Long>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        SystemBarInsets.applyTo(binding.root)

        taskStore = TaskStore(this)
        settingsStore = RelaySettingsStore(this)
        setupStaticTexts()
        binding.clearTasksButton.setOnClickListener {
            taskStore.clear()
            lastRecentRenderKey = null
            renderRecentTasks()
        }
        binding.settingsButton.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        renderCurrentConfig()
        renderRecentTasks()
        startRecentSync()
    }

    override fun onPause() {
        stopRecentSync()
        super.onPause()
    }

    private fun setupStaticTexts() {
        binding.topBarTitleText.text = getString(R.string.topbar_home)
        binding.settingsButton.text = getString(R.string.settings_entry)
        binding.summaryText.text = getString(R.string.main_summary)
        binding.relayLabelText.text = getString(R.string.main_relay_label)
        binding.modeLabelText.text = getString(R.string.main_mode_label)
        binding.recentLabelText.text = getString(R.string.main_recent_label)
        binding.recentHintText.text = getString(R.string.main_recent_hint)
        binding.clearTasksButton.text = getString(R.string.action_clear)
        binding.recentEmptyText.text = getString(R.string.main_no_tasks_hint)
    }

    private fun renderCurrentConfig() {
        val relayBaseUrl = settingsStore.currentRelayBaseUrl()
        val modeSummary = settingsStore.selectedModeSummary()
        val renderKey = "$relayBaseUrl\n$modeSummary"
        if (renderKey == lastConfigRenderKey) {
            return
        }

        binding.relayValueText.text = relayBaseUrl
        binding.modeValueText.text = modeSummary
        lastConfigRenderKey = renderKey
    }

    private fun renderRecentTasks() {
        val records = taskStore.listRecent(TaskStore.MAX_RECORDS)
        val renderKey = records.joinToString("||") {
            listOf(
                it.sequenceNumber.toString(),
                it.workId,
                it.state.name,
                it.relayStatusSnapshot.orEmpty(),
                it.relayErrorCodeSnapshot.orEmpty(),
                it.updatedAtEpochMs.toString(),
                it.message,
                it.relayTaskId.orEmpty(),
                it.modeLabelSnapshot.orEmpty(),
                buildDurationSummary(it).orEmpty(),
            ).joinToString("|")
        }
        if (renderKey == lastRecentRenderKey) {
            return
        }

        binding.recentTasksContainer.removeAllViews()

        val hasTasks = records.isNotEmpty()
        binding.recentEmptyText.visibility = if (hasTasks) View.GONE else View.VISIBLE
        binding.clearTasksButton.visibility = if (hasTasks) View.VISIBLE else View.GONE

        if (!hasTasks) {
            binding.recentEmptyText.text = getString(R.string.main_no_tasks_hint)
            lastRecentRenderKey = renderKey
            return
        }

        records.forEach { record ->
            val itemBinding = ViewRecentTaskBinding.inflate(layoutInflater, binding.recentTasksContainer, false)
            bindRecentTask(itemBinding, record)
            binding.recentTasksContainer.addView(itemBinding.root)
        }
        lastRecentRenderKey = renderKey
    }

    private fun bindRecentTask(itemBinding: ViewRecentTaskBinding, record: SubmissionRecord) {
        val (sourceLabel, sourceBackground, sourceForeground) = when (record.sourceType) {
            SourceType.WECHAT_ARTICLE -> Triple(UiText.sourceLabel(this, record.sourceType), R.color.success_soft, R.color.success)
            SourceType.XIAOHONGSHU -> Triple(UiText.sourceLabel(this, record.sourceType), R.color.danger_soft, R.color.danger)
            SourceType.UNKNOWN -> Triple(UiText.sourceLabel(this, record.sourceType), R.color.pending_soft, R.color.pending)
        }
        val (stateLabel, stateBackground, stateForeground) = stateAppearance(record)

        itemBinding.sourceChipText.text = sourceLabel
        itemBinding.stateChipText.text = stateLabel
        itemBinding.serialText.text = "#${record.sequenceNumber}"
        tintChip(itemBinding.sourceChipText, sourceBackground, sourceForeground)
        tintChip(itemBinding.stateChipText, stateBackground, stateForeground)

        itemBinding.targetText.text = buildTargetSummary(record)
        itemBinding.messageText.text = buildMessageSummary(record)
        itemBinding.timeText.text = buildMetaSummary(record)
        itemBinding.root.setOnClickListener {
            startActivity(
                Intent(this, SubmissionStatusActivity::class.java)
                    .putExtra(SubmissionStatusActivity.EXTRA_WORK_ID, record.workId),
            )
        }
    }

    private fun tintChip(view: TextView, backgroundColorRes: Int, foregroundColorRes: Int) {
        val wrapped = DrawableCompat.wrap(view.background.mutate())
        DrawableCompat.setTint(wrapped, ContextCompat.getColor(this, backgroundColorRes))
        view.background = wrapped
        view.setTextColor(ContextCompat.getColor(this, foregroundColorRes))
    }

    private fun buildTargetSummary(record: SubmissionRecord): String {
        val host = runCatching { Uri.parse(record.normalizedUrl).host.orEmpty() }.getOrDefault("")
            .removePrefix("www.")
            .ifBlank {
                when (record.sourceType) {
                    SourceType.WECHAT_ARTICLE -> "mp.weixin.qq.com"
                    SourceType.XIAOHONGSHU -> "xiaohongshu.com"
                    SourceType.UNKNOWN -> getString(R.string.recent_target_unknown)
                }
            }
        return host
    }

    private fun buildMessageSummary(record: SubmissionRecord): String =
        buildRelayAdviceSummary(record) ?: when (record.relayErrorCodeSnapshot) {
            "manual_verification_required" -> getString(R.string.manual_verification_note)
            "profile_revalidation_required" -> getString(R.string.profile_revalidation_note)
            "wechat_parameter_error" -> getString(R.string.wechat_parameter_error_note)
            "executor_session_locked" -> getString(R.string.session_lock_note)
            "executor_network_error" -> getString(R.string.network_error_note)
            else -> UiText.localizeRelayDynamicText(this, record.message.ifBlank {
                when (record.relayStatusSnapshot) {
                    "completed" -> getString(R.string.recent_service_completed)
                    "failed" -> getString(R.string.recent_service_failed)
                    "cancelled" -> getString(R.string.recent_service_cancelled)
                    "cancelling" -> getString(R.string.cancel_requested_note)
                    "queued" -> getString(R.string.recent_service_received)
                    "preparing", "running", "finalizing" -> getString(R.string.recent_service_processing)
                    else -> UiText.recentMessage(this, record.state)
                }
            })
        }

    private fun buildRelayAdviceSummary(record: SubmissionRecord): String? {
        val problem = UiText.relayProblemTitle(
            this,
            record.relayStatusSnapshot,
            record.relayErrorCodeSnapshot,
            record.relayProblemTitleSnapshot,
        ).orEmpty()
        val action = UiText.relaySuggestedActions(
            this,
            record.relayStatusSnapshot,
            record.relayErrorCodeSnapshot,
            record.relaySuggestedActionsSnapshot,
        ).firstOrNull().orEmpty()
        if (problem.isBlank()) {
            return null
        }
        if (action.isBlank()) {
            return problem
        }
        return when (record.relayStatusSnapshot) {
            "failed", "cancelled" -> "$problem\n$action"
            else -> problem
        }
    }

    private fun buildMetaSummary(record: SubmissionRecord): String {
        val parts = mutableListOf(formatRelativeTime(record.updatedAtEpochMs))
        buildDurationSummary(record)?.let(parts::add)
        record.modeLabelSnapshot?.takeIf { it.isNotBlank() }?.let(parts::add)
        record.relayTaskId?.takeIf { it.isNotBlank() }?.let { parts.add(UiText.taskIdLabel(this, it)) }
        return parts.joinToString(" | ")
    }

    private fun buildDurationSummary(record: SubmissionRecord): String? {
        val durationMs = when (record.relayStatusSnapshot) {
            "completed", "failed", "cancelled" -> record.relayDurationMsSnapshot
            "queued", "preparing", "running", "finalizing", "cancelling" -> {
                if (record.createdAtEpochMs > 0L) System.currentTimeMillis() - record.createdAtEpochMs else null
            }
            else -> null
        }
        val text = UiText.formatDuration(this, durationMs)
        return text.takeIf { it != getString(R.string.status_duration_placeholder) }
    }

    private fun formatRelativeTime(updatedAtEpochMs: Long): String {
        val diffMs = max(0L, System.currentTimeMillis() - updatedAtEpochMs)
        val diffMinutes = diffMs / 60_000
        val diffHours = diffMs / 3_600_000
        val diffDays = diffMs / 86_400_000

        return when {
            diffMinutes < 1 -> getString(R.string.recent_time_now)
            diffMinutes < 60 -> UiText.relativeTimeMinutes(this, diffMinutes)
            diffHours < 24 -> UiText.relativeTimeHours(this, diffHours)
            else -> UiText.relativeTimeDays(this, diffDays)
        }
    }

    private fun stateAppearance(record: SubmissionRecord): Triple<String, Int, Int> =
        when (record.relayStatusSnapshot) {
            "completed" -> Triple(getString(R.string.recent_status_completed), R.color.success_soft, R.color.success)
            "failed" -> Triple(getString(R.string.recent_status_failed), R.color.danger_soft, R.color.danger)
            "cancelled" -> Triple(getString(R.string.recent_status_cancelled), R.color.pending_soft, R.color.pending)
            "cancelling" -> Triple(getString(R.string.recent_status_cancelling), R.color.warning_soft, R.color.warning)
            "queued" -> Triple(getString(R.string.recent_status_received), R.color.pending_soft, R.color.pending)
            "preparing", "running", "finalizing" -> Triple(getString(R.string.recent_status_processing), R.color.warning_soft, R.color.warning)
            else -> stateAppearance(record.state)
        }

    private fun stateAppearance(state: TaskState): Triple<String, Int, Int> =
        when (state) {
            TaskState.ENQUEUED -> Triple(UiText.recentState(this, state), R.color.pending_soft, R.color.pending)
            TaskState.RUNNING -> Triple(UiText.recentState(this, state), R.color.warning_soft, R.color.warning)
            TaskState.RETRYING -> Triple(UiText.recentState(this, state), R.color.warning_soft, R.color.warning)
            TaskState.SUCCEEDED -> Triple(UiText.recentState(this, state), R.color.success_soft, R.color.success)
            TaskState.FAILED -> Triple(UiText.recentState(this, state), R.color.danger_soft, R.color.danger)
            TaskState.CANCELLED -> Triple(UiText.recentState(this, state), R.color.pending_soft, R.color.pending)
        }

    private fun startRecentSync() {
        if (recentSyncJob?.isActive == true) {
            return
        }
        recentSyncJob = lifecycleScope.launch {
            while (isActive) {
                syncUnfinishedTasks()
                renderRecentTasks()
                delay(computeRecentSyncDelayMs())
            }
        }
    }

    private fun stopRecentSync() {
        recentSyncJob?.cancel()
        recentSyncJob = null
        recentSyncTimestamps.clear()
    }

    private suspend fun syncUnfinishedTasks() {
        val now = System.currentTimeMillis()
        val records = taskStore.listRecent(TaskStore.MAX_RECORDS)
        var changed = false
        records
            .filter { shouldSyncRecord(it) }
            .take(RECENT_SYNC_ACTIVE_LIMIT)
            .forEach { record ->
                val lastSyncAt = recentSyncTimestamps[record.workId] ?: 0L
                if (now - lastSyncAt < syncCooldownMsFor(record)) {
                    return@forEach
                }
                val relayTaskId = record.relayTaskId ?: return@forEach
                val relayBaseUrl = record.relayBaseUrlSnapshot ?: return@forEach
                recentSyncTimestamps[record.workId] = now
                val result = relayClient.safeFetchTaskStatus(relayBaseUrl, relayTaskId)
                val remoteStatus = result.status ?: return@forEach
                val merged = mergeRelayStatus(record, remoteStatus)
                if (merged != null) {
                    taskStore.upsert(merged)
                    changed = true
                    if (merged.relayStatusSnapshot in setOf("completed", "failed", "cancelled")) {
                        recentSyncTimestamps.remove(merged.workId)
                    }
                }
            }
        if (changed) {
            lastRecentRenderKey = null
        }
    }

    private fun shouldSyncRecord(record: SubmissionRecord): Boolean =
        !record.relayTaskId.isNullOrBlank() &&
            !record.relayBaseUrlSnapshot.isNullOrBlank() &&
            record.relayStatusSnapshot !in setOf("completed", "failed", "cancelled")

    private fun syncCooldownMsFor(record: SubmissionRecord): Long =
        when (record.relayStatusSnapshot) {
            "queued", "preparing" -> 1800L
            "cancelling" -> 1200L
            "running", "finalizing" -> 4000L
            else -> 5000L
        }

    private fun computeRecentSyncDelayMs(): Long {
        val activeStatuses = taskStore.listRecent(TaskStore.MAX_RECORDS)
            .filter { shouldSyncRecord(it) }
            .take(RECENT_SYNC_ACTIVE_LIMIT)
            .mapNotNull { it.relayStatusSnapshot }

        return when {
            activeStatuses.isEmpty() -> 7000L
            activeStatuses.any { it == "cancelling" } -> 1500L
            activeStatuses.any { it == "queued" || it == "preparing" } -> 2200L
            else -> 4200L
        }
    }

    private fun mergeRelayStatus(current: SubmissionRecord, remoteStatus: RelayTaskStatus): SubmissionRecord? {
        val mappedState = when (remoteStatus.status) {
            "queued" -> TaskState.ENQUEUED
            "preparing", "running", "finalizing", "cancelling" -> TaskState.RUNNING
            "completed" -> TaskState.SUCCEEDED
            "failed" -> TaskState.FAILED
            "cancelled" -> TaskState.CANCELLED
            else -> current.state
        }
        val timelineSummary = buildTimelineSummary(remoteStatus)
        val nextMessage = when (remoteStatus.status) {
            "completed" -> remoteStatus.resultSummary.ifBlank { remoteStatus.relayMessage.ifBlank { remoteStatus.stageLabel } }
            "failed" -> remoteStatus.errorMessage.ifBlank { remoteStatus.relayMessage.ifBlank { remoteStatus.stageLabel } }
            "cancelled" -> remoteStatus.relayMessage.ifBlank { getString(R.string.relay_cancelled_note) }
            else -> remoteStatus.stageLabel.ifBlank { remoteStatus.relayMessage.ifBlank { current.message } }
        }
        val updated = current.copy(
            relayStatusSnapshot = remoteStatus.status.ifBlank { current.relayStatusSnapshot },
            relayErrorCodeSnapshot = remoteStatus.errorCode.ifBlank { current.relayErrorCodeSnapshot },
            relayDurationMsSnapshot = remoteStatus.durationMs ?: current.relayDurationMsSnapshot,
            relayTimelineSnapshot = timelineSummary.ifBlank { current.relayTimelineSnapshot },
            relayProblemTitleSnapshot = remoteStatus.problemTitle.ifBlank { null },
            relaySuggestedActionsSnapshot = remoteStatus.suggestedActions,
            relayDiagnosticSummarySnapshot = remoteStatus.diagnosticSummary.ifBlank { null },
            state = mappedState,
            message = nextMessage,
            updatedAtEpochMs = System.currentTimeMillis(),
        )
        return if (updated == current) null else updated
    }

    private fun buildTimelineSummary(status: RelayTaskStatus): String =
        status.timeline.joinToString("\n") { entry ->
            val timeText = formatIsoDateTime(entry.at)
            "${entry.label} · ${timeText}"
        }

    private fun formatIsoDateTime(value: String): String =
        runCatching {
            OffsetDateTime.parse(value)
                .atZoneSameInstant(ZoneId.systemDefault())
                .format(TIMELINE_FORMATTER)
        }.getOrElse { value.replace("T", " ") }

    companion object {
        private const val RECENT_SYNC_ACTIVE_LIMIT = 5
        private val TIMELINE_FORMATTER: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
    }
}

