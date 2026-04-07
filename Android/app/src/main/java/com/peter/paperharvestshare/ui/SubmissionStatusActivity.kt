package com.peter.paperharvestshare.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.DrawableCompat
import androidx.core.view.WindowCompat
import androidx.lifecycle.Observer
import androidx.lifecycle.lifecycleScope
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelayClient
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.data.RelayTaskStatus
import com.peter.paperharvestshare.data.TaskStore
import com.peter.paperharvestshare.databinding.ActivitySubmissionStatusBinding
import com.peter.paperharvestshare.databinding.ViewTimelinePreviewEntryBinding
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
import java.util.UUID

class SubmissionStatusActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySubmissionStatusBinding
    private lateinit var taskStore: TaskStore
    private lateinit var settingsStore: RelaySettingsStore
    private val relayClient = RelayClient()

    private var workObserver: Observer<WorkInfo>? = null
    private var observedWorkId: String? = null
    private var relayPollingJob: Job? = null
    private var durationTickerJob: Job? = null
    private var observedRelayTaskId: String? = null
    private var lastRenderKey: String? = null
    private var currentWorkId: String? = null
    private var lastPreviewTimelineLines: List<String> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        binding = ActivitySubmissionStatusBinding.inflate(layoutInflater)
        setContentView(binding.root)
        SystemBarInsets.applyTo(binding.root)

        taskStore = TaskStore(this)
        settingsStore = RelaySettingsStore(this)
        setupStaticTexts()

        val workId = intent.getStringExtra(EXTRA_WORK_ID)
        if (workId.isNullOrBlank()) {
            renderMissingWorkId()
            return
        }
        currentWorkId = workId

        binding.topBarBackButton.setOnClickListener { finish() }
        binding.homeButton.setOnClickListener {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
        }
        binding.copyButton.setOnClickListener { copyCurrentResult() }
        binding.viewDetailButton.setOnClickListener { showFullDetailDialog() }
        binding.cancelTaskButton.setOnClickListener { requestCancel() }
        binding.viewTimelineButton.setOnClickListener {
            currentWorkId?.let { workId ->
                TaskFlowDialogFragment.newInstance(workId).show(supportFragmentManager, "task_flow")
            }
        }

        observeWork(workId)
        renderFromStore(workId)
        startDurationTicker()
    }

    override fun onDestroy() {
        stopObservingWork()
        stopRelayPolling()
        stopDurationTicker()
        super.onDestroy()
    }

    private fun setupStaticTexts() {
        binding.topBarTitleText.text = getString(R.string.topbar_status)
        binding.topBarBackButton.contentDescription = getString(R.string.action_back)
        binding.statusNoteText.text = getString(R.string.status_page_note)
        binding.stepReceivedText.text = getString(R.string.stage_received)
        binding.stepNormalizedText.text = getString(R.string.stage_normalized)
        binding.stepSubmittingText.text = getString(R.string.stage_submitting)
        binding.stepAcceptedText.text = getString(R.string.stage_accepted)
        binding.manualVerificationTitleText.text = getString(R.string.manual_verification_panel_title)
        binding.manualVerificationBodyText.text = getString(R.string.manual_verification_panel_body)
        binding.suggestedActionsTitleText.text = getString(R.string.status_next_steps_label)
        binding.detailLabelText.text = getString(R.string.status_detail_label)
        binding.viewDetailButton.text = getString(R.string.action_view_full_response)
        binding.timelineLabelText.text = getString(R.string.status_timeline_label)
        binding.viewTimelineButton.text = getString(R.string.action_view_full_flow)
        binding.taskLabelText.text = getString(R.string.status_task_label)
        binding.durationValueText.text = getString(R.string.status_duration_placeholder)
        updateTimelinePreview(null)
        binding.homeButton.text = getString(R.string.action_home)
        binding.copyButton.text = getString(R.string.action_copy_result)
        binding.cancelTaskButton.text = getString(R.string.action_cancel_task)
    }

    private fun observeWork(workId: String) {
        observedWorkId = workId
        val observer = Observer<WorkInfo> { workInfo ->
            val record = taskStore.getByWorkId(workId)
            if (record != null) {
                bindRecord(record)
                if (isTerminal(record.state) && record.relayTaskId.isNullOrBlank()) {
                    stopObservingWork()
                }
            } else {
                bindFallback(workInfo)
                if (isTerminal(workInfo.state)) {
                    stopObservingWork()
                }
            }
        }
        workObserver = observer
        WorkManager.getInstance(this)
            .getWorkInfoByIdLiveData(UUID.fromString(workId))
            .observe(this, observer)
    }

    private fun stopObservingWork() {
        val workId = observedWorkId
        val observer = workObserver
        if (!workId.isNullOrBlank() && observer != null) {
            WorkManager.getInstance(this).getWorkInfoByIdLiveData(UUID.fromString(workId)).removeObserver(observer)
        }
        observedWorkId = null
        workObserver = null
    }

    private fun renderFromStore(workId: String) {
        taskStore.getByWorkId(workId)?.let(::bindRecord)
    }

    private fun bindRecord(record: SubmissionRecord) {
        val renderKey = listOf(
            record.state.name,
            record.relayStatusSnapshot.orEmpty(),
            record.relayErrorCodeSnapshot.orEmpty(),
            (record.relayDurationMsSnapshot ?: -1L).toString(),
            record.relayTimelineSnapshot.orEmpty(),
            record.message,
            record.relayTaskId.orEmpty(),
            record.updatedAtEpochMs.toString(),
        ).joinToString("|")
        if (renderKey == lastRenderKey) {
            maybeStartRelayPolling(record)
            return
        }

        if (!record.relayTaskId.isNullOrBlank()) {
            bindRelayBackedRecord(record)
        } else {
            bindLocalRecord(record)
        }

        binding.taskValueText.text = record.relayTaskId ?: getString(R.string.task_id_placeholder)
        binding.durationValueText.text = currentDurationText(record)
        updateTimelinePreview(record.relayTimelineSnapshot)
        binding.cancelTaskButton.visibility = if (canCancel(record)) View.VISIBLE else View.GONE
        binding.cancelTaskButton.isEnabled = canCancel(record)
        if (isTerminal(record.state)) {
            stopDurationTicker()
        } else {
            startDurationTicker()
        }
        lastRenderKey = renderKey
        maybeStartRelayPolling(record)
    }

    private fun bindLocalRecord(record: SubmissionRecord) {
        val uiState = uiState(record.state)
        binding.statusText.text = uiState.headline
        binding.statusText.setTextColor(ContextCompat.getColor(this, uiState.headlineColor))
        binding.statusNoteText.text = uiState.note
        binding.progressIndicator.progress = uiState.progress
        binding.progressIndicator.setIndicatorColor(ContextCompat.getColor(this, uiState.indicatorColor))
        binding.stepAcceptedText.text = getString(R.string.stage_accepted)
        binding.manualVerificationPanel.visibility = View.GONE
        binding.suggestedActionsPanel.visibility = View.GONE

        applyStep(binding.stepReceivedDot, binding.stepReceivedText, StepVisualState.DONE)
        applyStep(binding.stepNormalizedDot, binding.stepNormalizedText, StepVisualState.DONE)
        applyStep(binding.stepSubmittingDot, binding.stepSubmittingText, uiState.submittingStep)
        applyStep(binding.stepAcceptedDot, binding.stepAcceptedText, uiState.acceptedStep)
        updateDetailPreview(buildDetailMessage(record))
    }

    private fun bindRelayBackedRecord(record: SubmissionRecord) {
        binding.statusText.text = relayHeadline(record)
        binding.statusText.setTextColor(ContextCompat.getColor(this, relayHeadlineColor(record)))
        binding.statusNoteText.text = relayNote(record)
        binding.progressIndicator.progress = relayProgress(record)
        binding.progressIndicator.setIndicatorColor(ContextCompat.getColor(this, relayIndicatorColor(record)))
        binding.stepAcceptedText.text = relayStepLabel(record)
        bindActionPanel(record)

        applyStep(binding.stepReceivedDot, binding.stepReceivedText, StepVisualState.DONE)
        applyStep(binding.stepNormalizedDot, binding.stepNormalizedText, StepVisualState.DONE)
        applyStep(binding.stepSubmittingDot, binding.stepSubmittingText, StepVisualState.DONE)
        applyStep(binding.stepAcceptedDot, binding.stepAcceptedText, relayStepState(record))
        updateDetailPreview(buildDetailMessage(record))
    }

    private fun maybeStartRelayPolling(record: SubmissionRecord) {
        val relayTaskId = record.relayTaskId ?: return
        val relayBaseUrl = record.relayBaseUrlSnapshot ?: return
        if (isRelayTerminal(record.relayStatusSnapshot)) {
            stopRelayPolling()
            return
        }
        if (observedRelayTaskId == relayTaskId && relayPollingJob?.isActive == true) {
            return
        }

        stopRelayPolling()
        observedRelayTaskId = relayTaskId
        relayPollingJob = lifecycleScope.launch {
            while (isActive) {
                val result = relayClient.safeFetchTaskStatus(relayBaseUrl, relayTaskId, settingsStore.currentRelayAuthToken())
                val remoteStatus = result.status
                if (result.success && remoteStatus != null) {
                    val updatedRecord = mergeRelayStatus(record.workId, remoteStatus)
                    if (updatedRecord != null) {
                        bindRecord(updatedRecord)
                        if (isRelayTerminal(updatedRecord.relayStatusSnapshot)) {
                            stopObservingWork()
                            break
                        }
                    }
                } else if (result.httpCode == 404) {
                    break
                }
                delay(relayPollIntervalMs(taskStore.getByWorkId(record.workId)?.relayStatusSnapshot))
            }
        }
    }

    private fun stopRelayPolling() {
        relayPollingJob?.cancel()
        relayPollingJob = null
        observedRelayTaskId = null
    }

    private fun mergeRelayStatus(workId: String, remoteStatus: RelayTaskStatus): SubmissionRecord? {
        val current = taskStore.getByWorkId(workId) ?: return null
        val mappedState = when (remoteStatus.status) {
            "queued" -> TaskState.ENQUEUED
            "preparing", "running", "finalizing", "cancelling" -> TaskState.RUNNING
            "completed" -> TaskState.SUCCEEDED
            "failed" -> TaskState.FAILED
            "cancelled" -> TaskState.CANCELLED
            else -> current.state
        }
        val nextMessage = when (remoteStatus.status) {
            "completed" -> remoteStatus.resultSummary.ifBlank { remoteStatus.relayMessage.ifBlank { remoteStatus.stageLabel } }
            "failed" -> remoteStatus.errorMessage.ifBlank { remoteStatus.relayMessage.ifBlank { remoteStatus.stageLabel } }
            "cancelled" -> remoteStatus.relayMessage.ifBlank { getString(R.string.relay_cancelled_note) }
            else -> remoteStatus.stageLabel.ifBlank { remoteStatus.relayMessage.ifBlank { current.message } }
        }
        val timelineSnapshot = buildTimelineSnapshot(remoteStatus)

        val updated = current.copy(
            relayStatusSnapshot = remoteStatus.status.ifBlank { current.relayStatusSnapshot },
            relayErrorCodeSnapshot = remoteStatus.errorCode.ifBlank { current.relayErrorCodeSnapshot },
            relayDurationMsSnapshot = remoteStatus.durationMs ?: current.relayDurationMsSnapshot,
            relayTimelineSnapshot = timelineSnapshot.ifBlank { current.relayTimelineSnapshot },
            relayProblemTitleSnapshot = remoteStatus.problemTitle.ifBlank { null },
            relaySuggestedActionsSnapshot = remoteStatus.suggestedActions,
            relayDiagnosticSummarySnapshot = remoteStatus.diagnosticSummary.ifBlank { null },
            state = mappedState,
            message = nextMessage,
            updatedAtEpochMs = System.currentTimeMillis(),
        )
        taskStore.upsert(updated)
        return updated
    }

    private fun bindFallback(workInfo: WorkInfo?) {
        if (workInfo == null) {
            return
        }
        val fallbackState = when (workInfo.state) {
            WorkInfo.State.ENQUEUED -> TaskState.ENQUEUED
            WorkInfo.State.RUNNING -> TaskState.RUNNING
            WorkInfo.State.SUCCEEDED -> TaskState.SUCCEEDED
            WorkInfo.State.FAILED -> TaskState.FAILED
            WorkInfo.State.CANCELLED -> TaskState.CANCELLED
            WorkInfo.State.BLOCKED -> TaskState.ENQUEUED
        }
        bindRecord(
            SubmissionRecord(
                clientSubmissionId = "",
                workId = "",
                sourceType = SourceType.UNKNOWN,
                rawUrl = null,
                normalizedUrl = "",
                relayBaseUrlSnapshot = null,
                modeIdSnapshot = null,
                modeLabelSnapshot = null,
                relayStatusSnapshot = null,
                relayErrorCodeSnapshot = null,
                relayDurationMsSnapshot = null,
                relayTimelineSnapshot = null,
                state = fallbackState,
                message = workInfo.outputData.keyValueMap.values.firstOrNull()?.toString().orEmpty(),
                relayTaskId = null,
                createdAtEpochMs = 0L,
                updatedAtEpochMs = 0L,
            ),
        )
    }

    private fun buildDetailMessage(record: SubmissionRecord): String =
        buildString {
            val localizedHeadline = UiText.relayProblemTitle(
                this@SubmissionStatusActivity,
                record.relayStatusSnapshot,
                record.relayErrorCodeSnapshot,
                record.relayProblemTitleSnapshot,
            )
            val fallback = when (record.relayErrorCodeSnapshot) {
                "manual_verification_required" -> getString(R.string.manual_verification_detail)
                "profile_revalidation_required" -> getString(R.string.profile_revalidation_detail)
                "wechat_parameter_error" -> getString(R.string.wechat_parameter_error_detail)
                "executor_session_locked" -> getString(R.string.session_lock_detail)
                "executor_network_error" -> getString(R.string.network_error_detail)
                else -> UiText.localizeRelayDynamicText(
                    this@SubmissionStatusActivity,
                    record.message.ifBlank {
                        when (record.state) {
                            TaskState.SUCCEEDED -> getString(R.string.task_message_default)
                            else -> UiText.recentMessage(this@SubmissionStatusActivity, record.state)
                        }
                    },
                )
            }
            if (!localizedHeadline.isNullOrBlank()) {
                append(localizedHeadline)
                if (fallback.isNotBlank() && fallback != localizedHeadline) {
                    append('\n')
                    append(fallback)
                }
            } else {
                append(fallback)
            }
        }

    private fun bindActionPanel(record: SubmissionRecord) {
        when (record.relayErrorCodeSnapshot) {
            "manual_verification_required" -> {
                binding.manualVerificationPanel.visibility = View.VISIBLE
                binding.manualVerificationTitleText.text = getString(R.string.manual_verification_panel_title)
                binding.manualVerificationBodyText.text = getString(R.string.manual_verification_panel_body)
            }

            "profile_revalidation_required" -> {
                binding.manualVerificationPanel.visibility = View.VISIBLE
                binding.manualVerificationTitleText.text = getString(R.string.profile_revalidation_panel_title)
                binding.manualVerificationBodyText.text = getString(R.string.profile_revalidation_panel_body)
            }

            else -> {
                binding.manualVerificationPanel.visibility = View.GONE
            }
        }

        val localizedActions = UiText.relaySuggestedActions(
            this,
            record.relayStatusSnapshot,
            record.relayErrorCodeSnapshot,
            record.relaySuggestedActionsSnapshot,
        )
        if (localizedActions.isNotEmpty()) {
            binding.suggestedActionsPanel.visibility = View.VISIBLE
            binding.suggestedActionsBodyText.text = localizedActions.joinToString("\n") { "- $it" }
        } else {
            binding.suggestedActionsPanel.visibility = View.GONE
            binding.suggestedActionsBodyText.text = ""
        }
    }

    private fun applyStep(dotView: View, labelView: TextView, state: StepVisualState) {
        val (dotColor, textColor) = when (state) {
            StepVisualState.DONE -> Pair(R.color.success, R.color.text_primary)
            StepVisualState.ACTIVE -> Pair(R.color.seed, R.color.text_primary)
            StepVisualState.PENDING -> Pair(R.color.pending, R.color.text_secondary)
            StepVisualState.CANCELLED -> Pair(R.color.pending, R.color.text_secondary)
            StepVisualState.ERROR -> Pair(R.color.danger, R.color.danger)
        }

        val wrapped = DrawableCompat.wrap(dotView.background.mutate())
        DrawableCompat.setTint(wrapped, ContextCompat.getColor(this, dotColor))
        dotView.background = wrapped
        labelView.setTextColor(ContextCompat.getColor(this, textColor))
        labelView.alpha = if (state == StepVisualState.PENDING) 0.75f else 1f
    }

    private fun renderMissingWorkId() {
        binding.statusText.text = UiText.statusHeadline(this, TaskState.FAILED)
        binding.statusText.setTextColor(ContextCompat.getColor(this, R.color.danger))
        binding.statusNoteText.text = getString(R.string.status_missing_work_id)
        binding.progressIndicator.progress = 0
        updateDetailPreview(getString(R.string.status_missing_work_id))
        binding.taskValueText.text = getString(R.string.task_id_placeholder)
        binding.durationValueText.text = getString(R.string.status_duration_placeholder)
        updateTimelinePreview(null)
        binding.copyButton.isEnabled = false
        binding.viewDetailButton.visibility = View.GONE
        binding.cancelTaskButton.visibility = View.GONE
        binding.cancelTaskButton.isEnabled = false
        binding.manualVerificationPanel.visibility = View.GONE
        binding.suggestedActionsPanel.visibility = View.GONE
        applyStep(binding.stepReceivedDot, binding.stepReceivedText, StepVisualState.PENDING)
        applyStep(binding.stepNormalizedDot, binding.stepNormalizedText, StepVisualState.PENDING)
        applyStep(binding.stepSubmittingDot, binding.stepSubmittingText, StepVisualState.PENDING)
        applyStep(binding.stepAcceptedDot, binding.stepAcceptedText, StepVisualState.PENDING)
        lastRenderKey = "missing"
    }

    private fun copyCurrentResult() {
        val record = taskStore.getByWorkId(currentWorkId.orEmpty())
        val text = record?.relayDiagnosticSummarySnapshot?.takeIf { it.isNotBlank() } ?: buildString {
            append(binding.statusText.text)
            append('\n')
            append(binding.detailText.text)
            append('\n')
            append(binding.durationValueText.text)
            append('\n')
            append(record?.relayTimelineSnapshot ?: getString(R.string.status_timeline_placeholder))
            append('\n')
            append(binding.taskValueText.text)
        }
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("submission-status", text))
        Toast.makeText(
            this,
            if (record?.relayDiagnosticSummarySnapshot.isNullOrBlank()) getString(R.string.copy_done) else getString(R.string.copy_diagnostic_done),
            Toast.LENGTH_SHORT,
        ).show()
    }

    private fun requestCancel() {
        val workId = currentWorkId ?: return
        val record = taskStore.getByWorkId(workId) ?: return
        val relayTaskId = record.relayTaskId ?: return
        val relayBaseUrl = record.relayBaseUrlSnapshot ?: return
        binding.cancelTaskButton.isEnabled = false
        lifecycleScope.launch {
            val result = relayClient.safeCancelTask(relayBaseUrl, relayTaskId, settingsStore.currentRelayAuthToken())
            val updated = if (result.success) {
                val now = System.currentTimeMillis()
                val nextRelayStatus = result.status?.status ?: "cancelling"
                val nextState = when (nextRelayStatus) {
                    "cancelled" -> TaskState.CANCELLED
                    "completed" -> TaskState.SUCCEEDED
                    "failed" -> TaskState.FAILED
                    else -> TaskState.RUNNING
                }
                val next = record.copy(
                    relayStatusSnapshot = nextRelayStatus,
                    state = nextState,
                    message = result.status?.message ?: when (nextRelayStatus) {
                        "cancelled" -> getString(R.string.relay_cancelled_note)
                        "completed" -> getString(R.string.task_already_completed_note)
                        "failed" -> getString(R.string.task_already_failed_note)
                        else -> getString(R.string.cancel_requested_note)
                    },
                    updatedAtEpochMs = now,
                )
                taskStore.upsert(next)
                next
            } else {
                Toast.makeText(this@SubmissionStatusActivity, getString(R.string.cancel_request_failed), Toast.LENGTH_SHORT).show()
                record
            }
            bindRecord(updated)
        }
    }

    private fun startDurationTicker() {
        if (durationTickerJob?.isActive == true) {
            return
        }
        durationTickerJob = lifecycleScope.launch {
            while (isActive) {
                val workId = currentWorkId
                if (!workId.isNullOrBlank()) {
                    taskStore.getByWorkId(workId)?.let { record ->
                        binding.durationValueText.text = currentDurationText(record)
                    }
                }
                delay(1000)
            }
        }
    }

    private fun stopDurationTicker() {
        durationTickerJob?.cancel()
        durationTickerJob = null
    }

    private fun currentDurationText(record: SubmissionRecord): String =
        when {
            record.state == TaskState.SUCCEEDED || record.state == TaskState.FAILED || record.state == TaskState.CANCELLED ->
                UiText.formatDuration(this, record.relayDurationMsSnapshot)
            record.createdAtEpochMs > 0L -> UiText.formatDuration(this, System.currentTimeMillis() - record.createdAtEpochMs)
            else -> getString(R.string.status_duration_placeholder)
        }

    private fun relayPollIntervalMs(relayStatus: String?): Long =
        when (relayStatus) {
            "queued", "preparing" -> 1800L
            "cancelling" -> 1200L
            "running", "finalizing" -> 4000L
            else -> RELAY_POLL_INTERVAL_IDLE_MS
        }

    private fun updateTimelinePreview(fullTimeline: String?) {
        val lines = fullTimeline
            ?.lines()
            ?.map { it.trim() }
            ?.filter { it.isNotBlank() }
            .orEmpty()

        if (lines == lastPreviewTimelineLines) {
            return
        }

        val appendOnly = lines.size >= lastPreviewTimelineLines.size &&
            lines.take(lastPreviewTimelineLines.size) == lastPreviewTimelineLines

        if (!appendOnly) {
            binding.timelinePreviewContainer.removeAllViews()
        }

        if (lines.isEmpty()) {
            val placeholder = TextView(this).apply {
                text = getString(R.string.status_timeline_placeholder)
                gravity = android.view.Gravity.CENTER
                setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyMedium)
                setTextColor(ContextCompat.getColor(this@SubmissionStatusActivity, R.color.text_secondary))
            }
            binding.timelinePreviewContainer.removeAllViews()
            binding.timelinePreviewContainer.addView(placeholder)
            binding.timelinePreviewContainer.gravity = android.view.Gravity.CENTER
            lastPreviewTimelineLines = emptyList()
            return
        }

        val startIndex = if (appendOnly) lastPreviewTimelineLines.size else 0
        val newViews = mutableListOf<View>()
        for (index in startIndex until lines.size) {
            val entryBinding = ViewTimelinePreviewEntryBinding.inflate(layoutInflater, binding.timelinePreviewContainer, false)
            val (timeText, labelText) = parseTimelineLine(lines[index])
            entryBinding.timeText.text = timeText
            entryBinding.labelText.text = UiText.localizeTimelineLabel(this, labelText)
            binding.timelinePreviewContainer.addView(entryBinding.root)
            newViews += entryBinding.root
        }

        binding.timelinePreviewContainer.gravity =
            if (lines.size <= 3) android.view.Gravity.CENTER_VERTICAL else android.view.Gravity.TOP

        lastPreviewTimelineLines = lines
        animateNewTimelineEntries(newViews)
    }

    private fun animateNewTimelineEntries(newViews: List<View>) {
        if (newViews.isEmpty()) {
            return
        }
        newViews.forEachIndexed { index, view ->
            view.alpha = 0f
            view.translationY = 10f
            view.animate()
                .alpha(1f)
                .translationY(0f)
                .setStartDelay(index * 70L)
                .setDuration(180L)
                .start()
        }

        binding.timelinePreviewScrollView.post {
            val contentHeight = binding.timelinePreviewContainer.height
            val viewportHeight = binding.timelinePreviewScrollView.height
            if (contentHeight > viewportHeight) {
                binding.timelinePreviewScrollView.smoothScrollTo(0, contentHeight - viewportHeight)
            }
        }
    }

    private fun buildTimelineSnapshot(remoteStatus: RelayTaskStatus): String =
        remoteStatus.timeline.joinToString("\n") { entry ->
            "${formatIsoDateTime(entry.at)}  ${entry.label}"
        }.ifBlank { getString(R.string.status_timeline_placeholder) }

    private fun updateDetailPreview(detailText: String) {
        binding.detailText.text = detailText
        val shouldShowFull = detailText.length > DETAIL_PREVIEW_CHAR_LIMIT || detailText.count { it == '\n' } >= 3
        binding.viewDetailButton.visibility = if (shouldShowFull) View.VISIBLE else View.GONE
        binding.detailText.setOnClickListener(if (shouldShowFull) View.OnClickListener { showFullDetailDialog() } else null)
    }

    private fun showFullDetailDialog() {
        val detail = binding.detailText.text?.toString().orEmpty().trim()
        if (detail.isBlank()) {
            return
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.status_detail_dialog_title))
            .setMessage(detail)
            .setPositiveButton(getString(R.string.action_copy_result)) { _, _ ->
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("submission-response", detail))
                Toast.makeText(this, getString(R.string.copy_done), Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton(getString(R.string.task_flow_close), null)
            .show()
    }

    private fun parseTimelineLine(line: String): Pair<String, String> {
        val spacedParts = line.split(Regex("\\s{2,}"), limit = 2)
        if (spacedParts.size == 2) {
            return spacedParts[0] to spacedParts[1]
        }
        val dottedParts = line.split(" \u00B7 ", limit = 2)
        if (dottedParts.size == 2) {
            val first = dottedParts[0]
            val second = dottedParts[1]
            return if (second.contains(':') && second.any { it.isDigit() }) {
                second to first
            } else {
                "" to line
            }
        }
        return "" to line
    }

    private fun formatIsoDateTime(value: String): String =
        runCatching {
            OffsetDateTime.parse(value)
                .atZoneSameInstant(ZoneId.systemDefault())
                .format(TIMELINE_FORMATTER)
        }.getOrElse { value.replace("T", " ") }

    private fun isTerminal(state: TaskState): Boolean =
        state == TaskState.SUCCEEDED || state == TaskState.FAILED || state == TaskState.CANCELLED

    private fun isTerminal(state: WorkInfo.State): Boolean =
        state == WorkInfo.State.SUCCEEDED || state == WorkInfo.State.FAILED || state == WorkInfo.State.CANCELLED

    private fun isRelayTerminal(relayStatus: String?): Boolean =
        relayStatus == "completed" || relayStatus == "failed" || relayStatus == "cancelled"

    private fun relayHeadline(record: SubmissionRecord): String =
        when {
            record.relayErrorCodeSnapshot == "manual_verification_required" -> getString(R.string.manual_verification_headline)
            record.relayErrorCodeSnapshot == "profile_revalidation_required" -> getString(R.string.profile_revalidation_headline)
            record.relayErrorCodeSnapshot == "wechat_parameter_error" -> getString(R.string.wechat_parameter_error_headline)
            record.relayStatusSnapshot == "queued" -> getString(R.string.relay_accepted_headline)
            record.relayStatusSnapshot == "cancelling" -> getString(R.string.relay_cancelling_headline)
            record.relayStatusSnapshot == "completed" -> getString(R.string.relay_completed_headline)
            record.relayStatusSnapshot == "cancelled" -> getString(R.string.relay_cancelled_headline)
            record.relayStatusSnapshot == "failed" -> getString(R.string.relay_failed_headline)
            else -> getString(R.string.relay_running_headline)
        }

    private fun relayHeadlineColor(record: SubmissionRecord): Int =
        when {
            record.relayErrorCodeSnapshot == "manual_verification_required" -> R.color.warning
            record.relayErrorCodeSnapshot == "profile_revalidation_required" -> R.color.warning
            record.relayStatusSnapshot == "completed" -> R.color.success
            record.relayStatusSnapshot == "cancelled" -> R.color.pending
            record.relayStatusSnapshot == "failed" -> R.color.danger
            else -> R.color.text_primary
        }

    private fun relayProgress(record: SubmissionRecord): Int =
        when {
            record.relayErrorCodeSnapshot == "manual_verification_required" -> 88
            record.relayErrorCodeSnapshot == "profile_revalidation_required" -> 88
            record.relayStatusSnapshot == "queued" -> 64
            record.relayStatusSnapshot == "preparing" -> 74
            record.relayStatusSnapshot == "running" -> 84
            record.relayStatusSnapshot == "finalizing" -> 94
            record.relayStatusSnapshot == "cancelling" -> 92
            record.relayStatusSnapshot == "completed" -> 100
            record.relayStatusSnapshot == "cancelled" -> 100
            record.relayStatusSnapshot == "failed" -> 88
            else -> 84
        }

    private fun relayIndicatorColor(record: SubmissionRecord): Int =
        when {
            record.relayErrorCodeSnapshot == "manual_verification_required" -> R.color.warning
            record.relayErrorCodeSnapshot == "profile_revalidation_required" -> R.color.warning
            record.relayStatusSnapshot == "completed" -> R.color.success
            record.relayStatusSnapshot == "cancelled" -> R.color.pending
            record.relayStatusSnapshot == "failed" -> R.color.danger
            else -> R.color.seed
        }

    private fun relayStepLabel(record: SubmissionRecord): String =
        when {
            record.relayErrorCodeSnapshot == "manual_verification_required" -> getString(R.string.stage_manual_verification)
            record.relayErrorCodeSnapshot == "profile_revalidation_required" -> getString(R.string.stage_manual_verification)
            record.relayStatusSnapshot == "queued" -> getString(R.string.stage_accepted)
            record.relayStatusSnapshot == "cancelling" -> getString(R.string.stage_cancelling)
            record.relayStatusSnapshot == "completed" -> getString(R.string.stage_completed)
            record.relayStatusSnapshot == "cancelled" -> getString(R.string.relay_cancelled_headline)
            record.relayStatusSnapshot == "failed" -> getString(R.string.stage_failed)
            else -> getString(R.string.stage_running)
        }

    private fun relayStepState(record: SubmissionRecord): StepVisualState =
        when {
            record.relayErrorCodeSnapshot == "manual_verification_required" -> StepVisualState.ERROR
            record.relayErrorCodeSnapshot == "profile_revalidation_required" -> StepVisualState.ERROR
            record.relayStatusSnapshot == "queued" -> StepVisualState.DONE
            record.relayStatusSnapshot == "completed" -> StepVisualState.DONE
            record.relayStatusSnapshot == "cancelled" -> StepVisualState.CANCELLED
            record.relayStatusSnapshot == "failed" -> StepVisualState.ERROR
            else -> StepVisualState.ACTIVE
        }

    private fun relayNote(record: SubmissionRecord): String =
        when (record.relayStatusSnapshot) {
            "queued" -> UiText.localizeRelayDynamicText(this, record.message).ifBlank { getString(R.string.relay_accepted_note) }
            "cancelling" -> getString(R.string.cancel_requested_note)
            "completed" -> getString(R.string.relay_completed_note)
            "cancelled" -> getString(R.string.relay_cancelled_note)
            "failed" -> when (record.relayErrorCodeSnapshot) {
                "manual_verification_required" -> getString(R.string.manual_verification_note)
                "profile_revalidation_required" -> getString(R.string.profile_revalidation_note)
                "wechat_parameter_error" -> getString(R.string.wechat_parameter_error_note)
                "executor_session_locked" -> getString(R.string.session_lock_note)
                "executor_network_error" -> getString(R.string.network_error_note)
                else -> getString(R.string.relay_failed_note)
            }
            else -> UiText.localizeRelayDynamicText(this, record.message).ifBlank { getString(R.string.relay_running_note) }
        }

    private fun canCancel(record: SubmissionRecord): Boolean =
        record.relayTaskId != null && record.relayStatusSnapshot in setOf("queued", "preparing", "running", "finalizing")

    private fun uiState(state: TaskState): StatusUiState =
        when (state) {
            TaskState.ENQUEUED -> StatusUiState(
                headline = UiText.statusHeadline(this, state),
                note = UiText.statusNote(this, state),
                progress = 45,
                indicatorColor = R.color.pending,
                headlineColor = R.color.text_primary,
                submittingStep = StepVisualState.ACTIVE,
                acceptedStep = StepVisualState.PENDING,
            )
            TaskState.RUNNING -> StatusUiState(
                headline = UiText.statusHeadline(this, state),
                note = UiText.statusNote(this, state),
                progress = 72,
                indicatorColor = R.color.seed,
                headlineColor = R.color.text_primary,
                submittingStep = StepVisualState.ACTIVE,
                acceptedStep = StepVisualState.PENDING,
            )
            TaskState.RETRYING -> StatusUiState(
                headline = UiText.statusHeadline(this, state),
                note = UiText.statusNote(this, state),
                progress = 72,
                indicatorColor = R.color.warning,
                headlineColor = R.color.warning,
                submittingStep = StepVisualState.ACTIVE,
                acceptedStep = StepVisualState.PENDING,
            )
            TaskState.SUCCEEDED -> StatusUiState(
                headline = UiText.statusHeadline(this, state),
                note = UiText.statusNote(this, state),
                progress = 100,
                indicatorColor = R.color.success,
                headlineColor = R.color.success,
                submittingStep = StepVisualState.DONE,
                acceptedStep = StepVisualState.DONE,
            )
            TaskState.FAILED -> StatusUiState(
                headline = UiText.statusHeadline(this, state),
                note = UiText.statusNote(this, state),
                progress = 72,
                indicatorColor = R.color.danger,
                headlineColor = R.color.danger,
                submittingStep = StepVisualState.ERROR,
                acceptedStep = StepVisualState.PENDING,
            )
            TaskState.CANCELLED -> StatusUiState(
                headline = UiText.statusHeadline(this, state),
                note = UiText.statusNote(this, state),
                progress = 45,
                indicatorColor = R.color.pending,
                headlineColor = R.color.text_secondary,
                submittingStep = StepVisualState.PENDING,
                acceptedStep = StepVisualState.PENDING,
            )
        }

    companion object {
        private const val RELAY_POLL_INTERVAL_IDLE_MS = 5000L
        private const val DETAIL_PREVIEW_CHAR_LIMIT = 220
        private val TIMELINE_FORMATTER: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
        const val EXTRA_WORK_ID = "extra_work_id"
    }
}

private data class StatusUiState(
    val headline: String,
    val note: String,
    val progress: Int,
    val indicatorColor: Int,
    val headlineColor: Int,
    val submittingStep: StepVisualState,
    val acceptedStep: StepVisualState,
)

private enum class StepVisualState {
    DONE,
    ACTIVE,
    PENDING,
    CANCELLED,
    ERROR,
}
