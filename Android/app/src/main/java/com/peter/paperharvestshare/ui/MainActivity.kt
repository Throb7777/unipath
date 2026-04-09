package com.peter.paperharvestshare.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.DrawableCompat
import androidx.core.view.WindowCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.lifecycle.lifecycleScope
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelayClient
import com.peter.paperharvestshare.data.RelayTaskStatus
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.data.TaskStore
import com.peter.paperharvestshare.databinding.ActivityMainBinding
import com.peter.paperharvestshare.model.ConnectionType
import com.peter.paperharvestshare.model.RelayModeOption
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
    private lateinit var recentTasksAdapter: RecentTasksAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        SystemBarInsets.applyTo(binding.root)

        taskStore = TaskStore(this)
        settingsStore = RelaySettingsStore(this)
        recentTasksAdapter = RecentTasksAdapter(this) { record ->
            startActivity(
                Intent(this, SubmissionStatusActivity::class.java)
                    .putExtra(SubmissionStatusActivity.EXTRA_WORK_ID, record.workId),
            )
        }
        binding.recentTasksRecyclerView.layoutManager = LinearLayoutManager(this)
        binding.recentTasksRecyclerView.adapter = recentTasksAdapter
        setupStaticTexts()
        binding.clearTasksButton.setOnClickListener {
            taskStore.clear()
            lastRecentRenderKey = null
            renderRecentTasks()
        }
        binding.switchRelayButton.setOnClickListener { showRelayProfilesDialog() }
        binding.switchModeButton.setOnClickListener { showModeChooserDialog() }
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
        binding.recentHintText.text = buildRecentHint()
        binding.clearTasksButton.text = getString(R.string.action_clear)
        binding.recentEmptyText.text = getString(R.string.main_no_tasks_hint)
        binding.switchRelayButton.text = getString(R.string.action_services)
        binding.switchModeButton.text = getString(R.string.action_choose)
    }

    private fun renderCurrentConfig() {
        val relayDisplay = buildRelayDisplay()
        val modeDisplay = buildModeDisplay()
        val renderKey = listOf(
            relayDisplay.title,
            relayDisplay.hint,
            modeDisplay.title,
            modeDisplay.hint,
        ).joinToString("\n")
        if (renderKey == lastConfigRenderKey) {
            return
        }

        binding.relayValueText.text = relayDisplay.title
        binding.relayHintText.text = relayDisplay.hint
        binding.modeValueText.text = modeDisplay.title
        binding.modeHintText.text = modeDisplay.hint
        binding.switchModeButton.visibility = if (currentAvailableModes().isEmpty()) View.GONE else View.VISIBLE
        lastConfigRenderKey = renderKey
    }

    private fun buildRelayDisplay(): ConfigDisplay {
        if (!settingsStore.hasSavedRelayBaseUrl()) {
            val hint = buildString {
                append(getString(R.string.main_relay_not_set_hint))
                if (shouldShowEmulatorOption() &&
                    settingsStore.currentConnectionType() == ConnectionType.EMULATOR &&
                    settingsStore.currentRelayBaseUrl().startsWith("http://10.0.2.2")
                ) {
                    append("\n")
                    append(getString(R.string.main_relay_emulator_hint))
                }
            }
            return ConfigDisplay(
                title = getString(R.string.main_config_not_set),
                hint = hint,
            )
        }

        val hint = when {
            settingsStore.currentConnectionType() == ConnectionType.PRIVATE_NETWORK &&
                settingsStore.currentRelayAuthToken().isBlank() ->
                getString(R.string.main_relay_private_auth_hint)
            settingsStore.currentConnectionType() == ConnectionType.PRIVATE_NETWORK ->
                getString(R.string.main_relay_private_hint)
            settingsStore.lastServiceSummary() != null ->
                getString(R.string.main_relay_connection_ready_hint)
            else -> getString(R.string.main_relay_saved_hint)
        }
        return ConfigDisplay(
            title = settingsStore.currentRelayBaseUrl(),
            hint = hint,
        )
    }

    private fun buildModeDisplay(): ConfigDisplay {
        if (!settingsStore.hasSavedModeSelection()) {
            return ConfigDisplay(
                title = getString(R.string.main_config_not_set),
                hint = getString(R.string.main_mode_not_set_hint),
            )
        }

        val modeLabel = UiText.processingModeLabel(
            this,
            settingsStore.selectedModeId(),
            settingsStore.selectedModeLabel(),
        )
        val modeHint = settingsStore.selectedModeDescription()
            ?.takeIf { it.isNotBlank() }
            ?: getString(R.string.main_mode_saved_hint)

        return ConfigDisplay(
            title = modeLabel,
            hint = modeHint,
        )
    }

    private fun currentAvailableModes(): List<RelayModeOption> =
        settingsStore.cachedClientConfigFor(settingsStore.currentRelayBaseUrl())
            ?.modes
            ?.filter { it.enabled }
            .orEmpty()

    private fun renderRecentTasks() {
        val records = taskStore.listRecent(recentTaskDisplayLimit())
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

        val hasTasks = records.isNotEmpty()
        binding.recentHintText.text = buildRecentHint()
        binding.recentEmptyText.visibility = if (hasTasks) View.GONE else View.VISIBLE
        binding.recentTasksRecyclerView.visibility = if (hasTasks) View.VISIBLE else View.GONE
        binding.clearTasksButton.visibility = if (hasTasks) View.VISIBLE else View.GONE

        if (!hasTasks) {
            binding.recentEmptyText.text = getString(R.string.main_no_tasks_hint)
            recentTasksAdapter.submitList(emptyList())
            lastRecentRenderKey = renderKey
            return
        }
        recentTasksAdapter.submitList(records)
        lastRecentRenderKey = renderKey
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

    internal fun buildMessageSummaryForAdapter(record: SubmissionRecord): String =
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
        record.modeIdSnapshot?.takeIf { it.isNotBlank() }?.let { modeId ->
            parts.add(UiText.processingModeLabel(this, modeId, record.modeLabelSnapshot))
        }
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

    internal fun stateAppearanceForAdapter(record: SubmissionRecord): Triple<String, Int, Int> =
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
        val records = taskStore.listRecent(recentTaskSyncWindowLimit())
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
                val relayAuthToken = settingsStore.currentRelayAuthToken()
                recentSyncTimestamps[record.workId] = now
                val result = relayClient.safeFetchTaskStatus(relayBaseUrl, relayTaskId, relayAuthToken)
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
        val activeStatuses = taskStore.listRecent(recentTaskSyncWindowLimit())
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
            "$timeText  ${entry.label}"
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

    private data class ConfigDisplay(
        val title: String,
        val hint: String,
    )

    private fun showRelayProfilesDialog() {
        val profiles = settingsStore.savedProfiles()
        if (profiles.isEmpty()) {
            startActivity(Intent(this, SettingsActivity::class.java))
            return
        }
        val currentId = settingsStore.currentProfileId()
        val sortedProfiles = profiles.sortedWith(
            compareByDescending<com.peter.paperharvestshare.model.RelayServiceProfile> { it.id == currentId }
                .thenBy { it.displayName.lowercase() },
        )
        var selectedIndex = sortedProfiles.indexOfFirst { it.id == currentId }.coerceAtLeast(0)
        val items = sortedProfiles.map { profile ->
            profileLine(profile, profile.id == currentId)
        }.toTypedArray()
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.main_saved_services_title))
            .setSingleChoiceItems(items, selectedIndex) { _, which ->
                selectedIndex = which
            }
            .setPositiveButton(getString(R.string.action_use)) { _, _ ->
                if (sortedProfiles.indices.contains(selectedIndex) && settingsStore.switchToProfile(sortedProfiles[selectedIndex].id)) {
                    lastConfigRenderKey = null
                    lastRecentRenderKey = null
                    renderCurrentConfig()
                    renderRecentTasks()
                }
            }
            .setNeutralButton(getString(R.string.action_delete)) { _, _ ->
                showDeleteRelayProfileDialog(sortedProfiles, selectedIndex)
            }
            .setNegativeButton(getString(R.string.settings_entry)) { _, _ ->
                startActivity(Intent(this, SettingsActivity::class.java))
            }
            .show()
    }

    private fun profileLine(
        profile: com.peter.paperharvestshare.model.RelayServiceProfile,
        isCurrent: Boolean,
    ): CharSequence {
        val connectionLabel = when (profile.connectionType) {
            ConnectionType.EMULATOR -> getString(R.string.settings_connection_type_emulator)
            ConnectionType.LOCAL_NETWORK -> getString(R.string.settings_connection_type_local)
            ConnectionType.PRIVATE_NETWORK -> getString(R.string.settings_connection_type_private)
        }
        val prefix = if (isCurrent) "• " else ""
        return buildString {
            append(prefix)
            append(profile.displayName)
            append('\n')
            append(connectionLabel)
            append(" · ")
            append(profile.relayBaseUrl)
        }
    }

    private fun showDeleteRelayProfileDialog(profiles: List<com.peter.paperharvestshare.model.RelayServiceProfile>, selectedIndex: Int) {
        if (!profiles.indices.contains(selectedIndex)) {
            return
        }
        val profile = profiles[selectedIndex]
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.main_delete_service_title))
            .setMessage(getString(R.string.main_delete_service_message, profile.displayName))
            .setPositiveButton(getString(R.string.action_delete)) { _, _ ->
                settingsStore.deleteProfile(profile.id)
                lastConfigRenderKey = null
                renderCurrentConfig()
            }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun showModeChooserDialog() {
        val modes = currentAvailableModes()
        if (modes.isEmpty()) {
            startActivity(Intent(this, SettingsActivity::class.java))
            return
        }
        var selectedIndex = modes.indexOfFirst { it.id == settingsStore.selectedModeId() }.coerceAtLeast(0)
        val items = modes.map { mode ->
            UiText.processingModeLabel(this@MainActivity, mode.id, mode.label)
        }.toTypedArray()
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.main_mode_picker_title))
            .setSingleChoiceItems(items, selectedIndex) { _, which ->
                selectedIndex = which
            }
            .setPositiveButton(getString(R.string.action_use)) { _, _ ->
                if (modes.indices.contains(selectedIndex)) {
                    settingsStore.updateSelectedMode(modes[selectedIndex])
                    lastConfigRenderKey = null
                    lastRecentRenderKey = null
                    renderCurrentConfig()
                    renderRecentTasks()
                }
            }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun shouldShowEmulatorOption(): Boolean =
        com.peter.paperharvestshare.BuildConfig.DEBUG ||
            settingsStore.currentConnectionType() == ConnectionType.EMULATOR ||
            isProbablyEmulator()

    private fun recentTaskDisplayLimit(): Int =
        settingsStore.currentRecentTaskLimit()

    private fun recentTaskSyncWindowLimit(): Int {
        val displayLimit = recentTaskDisplayLimit()
        return when {
            displayLimit <= 0 -> 50
            else -> max(displayLimit, 20)
        }
    }

    private fun buildRecentHint(): String {
        val limit = recentTaskDisplayLimit()
        return if (limit <= 0) {
            getString(R.string.main_recent_hint_all)
        } else {
            getString(R.string.main_recent_hint_limited, limit)
        }
    }

    private fun isProbablyEmulator(): Boolean =
        Build.FINGERPRINT.contains("generic", ignoreCase = true) ||
            Build.MODEL.contains("Emulator", ignoreCase = true) ||
            Build.MANUFACTURER.contains("Genymotion", ignoreCase = true) ||
            Build.PRODUCT.contains("sdk", ignoreCase = true)
}

