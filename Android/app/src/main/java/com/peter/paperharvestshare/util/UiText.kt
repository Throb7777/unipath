package com.peter.paperharvestshare.util

import android.content.Context
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.model.SourceType
import com.peter.paperharvestshare.model.TaskState

object UiText {
    fun processingModeLabel(context: Context, modeId: String, rawLabel: String? = null): String {
        val label = rawLabel.orEmpty().trim()
        if (label.isNotBlank() && label != modeId) {
            return label
        }
        return when (modeId.trim()) {
            "paper_harvest_v1" -> context.getString(R.string.mode_label_paper_harvest)
            "paper_harvest_relaxed_v1" -> context.getString(R.string.mode_label_paper_harvest_relaxed)
            "link_only_v1" -> context.getString(R.string.mode_label_link_only)
            else -> label.ifBlank { modeId }
        }
    }

    fun sourceLabel(context: Context, sourceType: SourceType): String =
        when (sourceType) {
            SourceType.WECHAT_ARTICLE -> context.getString(R.string.source_wechat)
            SourceType.XIAOHONGSHU -> context.getString(R.string.source_xiaohongshu)
            SourceType.UNKNOWN -> context.getString(R.string.source_unknown)
        }

    fun recentState(context: Context, state: TaskState): String =
        when (state) {
            TaskState.ENQUEUED -> context.getString(R.string.recent_state_enqueued)
            TaskState.RUNNING -> context.getString(R.string.recent_state_running)
            TaskState.RETRYING -> context.getString(R.string.recent_state_retrying)
            TaskState.SUCCEEDED -> context.getString(R.string.recent_state_succeeded)
            TaskState.FAILED -> context.getString(R.string.recent_state_failed)
            TaskState.CANCELLED -> context.getString(R.string.recent_state_cancelled)
        }

    fun recentMessage(context: Context, state: TaskState): String =
        when (state) {
            TaskState.ENQUEUED -> context.getString(R.string.recent_message_enqueued)
            TaskState.RUNNING -> context.getString(R.string.recent_message_running)
            TaskState.RETRYING -> context.getString(R.string.recent_message_retrying)
            TaskState.SUCCEEDED -> context.getString(R.string.recent_message_succeeded)
            TaskState.FAILED -> context.getString(R.string.recent_message_failed)
            TaskState.CANCELLED -> context.getString(R.string.recent_message_cancelled)
        }

    fun statusHeadline(context: Context, state: TaskState): String =
        when (state) {
            TaskState.ENQUEUED -> context.getString(R.string.local_status_headline_enqueued)
            TaskState.RUNNING -> context.getString(R.string.local_status_headline_running)
            TaskState.RETRYING -> context.getString(R.string.local_status_headline_retrying)
            TaskState.SUCCEEDED -> context.getString(R.string.local_status_headline_succeeded)
            TaskState.FAILED -> context.getString(R.string.local_status_headline_failed)
            TaskState.CANCELLED -> context.getString(R.string.local_status_headline_cancelled)
        }

    fun statusNote(context: Context, state: TaskState): String =
        when (state) {
            TaskState.ENQUEUED -> context.getString(R.string.local_status_note_enqueued)
            TaskState.RUNNING -> context.getString(R.string.local_status_note_running)
            TaskState.RETRYING -> context.getString(R.string.local_status_note_retrying)
            TaskState.SUCCEEDED -> context.getString(R.string.local_status_note_succeeded)
            TaskState.FAILED -> context.getString(R.string.local_status_note_failed)
            TaskState.CANCELLED -> context.getString(R.string.local_status_note_cancelled)
        }

    fun relativeTimeMinutes(context: Context, minutes: Long): String =
        context.getString(R.string.recent_time_min, minutes)

    fun relativeTimeHours(context: Context, hours: Long): String =
        context.getString(R.string.recent_time_hour, hours)

    fun relativeTimeDays(context: Context, days: Long): String =
        context.getString(R.string.recent_time_day, days)

    fun taskIdLabel(context: Context, taskId: String): String =
        context.getString(R.string.task_id_short, taskId)

    fun formatDuration(context: Context, durationMs: Long?): String {
        if (durationMs == null || durationMs < 0) {
            return context.getString(R.string.status_duration_placeholder)
        }
        val totalSeconds = durationMs / 1000
        val hours = totalSeconds / 3600
        val minutes = totalSeconds / 60
        val minutesPart = (totalSeconds % 3600) / 60
        val seconds = totalSeconds % 60
        return when {
            hours > 0 -> context.getString(
                R.string.duration_hours_minutes_seconds,
                hours,
                minutesPart,
                seconds,
            )
            minutes > 0 -> context.getString(
                R.string.duration_minutes_seconds,
                minutes,
                seconds,
            )
            else -> context.getString(R.string.duration_seconds, seconds)
        }
    }

    fun relayProblemTitle(
        context: Context,
        relayStatus: String?,
        errorCode: String?,
        rawTitle: String?,
    ): String? {
        val mapped = when (errorCode) {
            "manual_verification_required" -> context.getString(R.string.manual_verification_headline)
            "profile_revalidation_required" -> context.getString(R.string.profile_revalidation_headline)
            "wechat_parameter_error" -> context.getString(R.string.wechat_parameter_error_headline)
            "executor_session_locked" -> context.getString(R.string.problem_title_processing_busy)
            "executor_network_error" -> context.getString(R.string.problem_title_network_error)
            "executor_auth_error" -> context.getString(R.string.problem_title_auth_not_ready)
            "executor_timeout" -> context.getString(R.string.problem_title_processing_timeout)
            "executor_start_failed" -> context.getString(R.string.problem_title_processing_start_failed)
            "executor_command_not_found" -> context.getString(R.string.problem_title_command_not_found)
            "executor_command_not_configured" -> context.getString(R.string.problem_title_command_not_configured)
            "executor_nonzero_exit" -> context.getString(R.string.problem_title_processing_error)
            "executor_reported_failure" -> context.getString(R.string.problem_title_processing_reported_failure)
            else -> when (relayStatus) {
                "completed" -> context.getString(R.string.problem_title_task_completed)
                "cancelled" -> context.getString(R.string.problem_title_task_cancelled)
                "failed" -> context.getString(R.string.problem_title_task_failed)
                "cancelling" -> context.getString(R.string.problem_title_cancelling)
                else -> null
            }
        }
        return mapped ?: localizeRelayDynamicText(context, rawTitle).takeIf { it.isNotBlank() }
    }

    fun relaySuggestedActions(
        context: Context,
        relayStatus: String?,
        errorCode: String?,
        rawActions: List<String>,
    ): List<String> {
        val mapped = when (errorCode) {
            "manual_verification_required" -> listOf(
                context.getString(R.string.action_manual_verification_1),
                context.getString(R.string.action_manual_verification_2),
            )
            "profile_revalidation_required" -> listOf(
                context.getString(R.string.action_profile_revalidation_1),
                context.getString(R.string.action_profile_revalidation_2),
            )
            "wechat_parameter_error" -> listOf(
                context.getString(R.string.action_wechat_parameter_error_1),
                context.getString(R.string.action_wechat_parameter_error_2),
            )
            "wechat_body_too_short" -> listOf(
                context.getString(R.string.action_body_too_short_1),
                context.getString(R.string.action_body_too_short_2),
            )
            "executor_session_locked" -> listOf(
                context.getString(R.string.action_session_locked_1),
                context.getString(R.string.action_session_locked_2),
            )
            "executor_network_error" -> listOf(
                context.getString(R.string.action_network_error_1),
                context.getString(R.string.action_network_error_2),
            )
            "executor_auth_error" -> listOf(
                context.getString(R.string.action_auth_error_1),
                context.getString(R.string.action_auth_error_2),
            )
            "executor_timeout" -> listOf(
                context.getString(R.string.action_timeout_1),
                context.getString(R.string.action_timeout_2),
            )
            "executor_start_failed" -> listOf(
                context.getString(R.string.action_start_failed_1),
                context.getString(R.string.action_start_failed_2),
            )
            "executor_command_not_found" -> listOf(
                context.getString(R.string.action_command_not_found_1),
                context.getString(R.string.action_command_not_found_2),
            )
            "executor_command_not_configured" -> listOf(
                context.getString(R.string.action_command_not_configured_1),
                context.getString(R.string.action_command_not_configured_2),
            )
            "executor_nonzero_exit" -> listOf(
                context.getString(R.string.action_nonzero_exit_1),
                context.getString(R.string.action_nonzero_exit_2),
            )
            "executor_reported_failure" -> listOf(
                context.getString(R.string.action_reported_failure_1),
                context.getString(R.string.action_reported_failure_2),
            )
            else -> when (relayStatus) {
                "completed" -> listOf(
                    context.getString(R.string.action_completed_1),
                    context.getString(R.string.action_completed_2),
                )
                "cancelled" -> listOf(
                    context.getString(R.string.action_cancelled_1),
                    context.getString(R.string.action_cancelled_2),
                )
                "queued", "preparing", "running", "finalizing", "cancelling" -> listOf(
                    context.getString(R.string.action_running_1),
                )
                "failed" -> listOf(
                    context.getString(R.string.action_failed_1),
                    context.getString(R.string.action_failed_2),
                )
                else -> emptyList()
            }
        }
        if (mapped.isNotEmpty()) {
            return mapped
        }
        return rawActions
            .map { localizeRelayDynamicText(context, it) }
            .filter { it.isNotBlank() }
    }

    fun localizeRelayDynamicText(context: Context, rawText: String?): String {
        val text = rawText.orEmpty().trim()
        if (text.isBlank()) {
            return ""
        }
        val lines = text.lines().map { localizeRelayDynamicLine(context, it.trimEnd()) }
        return lines.joinToString("\n").trim()
    }

    fun localizeTimelineLabel(context: Context, rawLabel: String): String =
        when (rawLabel.trim()) {
            "Queued for execution" -> context.getString(R.string.timeline_label_queued)
            "Preparing task" -> context.getString(R.string.timeline_label_preparing)
            "Opening browser" -> context.getString(R.string.timeline_label_opening_browser)
            "Running executor" -> context.getString(R.string.timeline_label_running_executor)
            "Running processing method" -> context.getString(R.string.timeline_label_running_executor)
            "Finalizing result" -> context.getString(R.string.timeline_label_finalizing)
            "Completed" -> context.getString(R.string.timeline_label_completed)
            "Failed" -> context.getString(R.string.timeline_label_failed)
            "Cancelled" -> context.getString(R.string.timeline_label_cancelled)
            "Cancellation requested" -> context.getString(R.string.timeline_label_cancelling)
            else -> localizeRelayDynamicText(context, rawLabel)
        }

    private fun localizeRelayDynamicLine(context: Context, rawLine: String): String {
        val line = rawLine.trim()
        if (line.isBlank()) {
            return ""
        }
        return when {
            line == "Highlights:" -> context.getString(R.string.summary_highlights)
            line.startsWith("- Topic: ") -> "- ${context.getString(R.string.summary_topic)}${line.removePrefix("- Topic: ")}"
            line.startsWith("- Takeaway: ") -> "- ${context.getString(R.string.summary_takeaway)}${line.removePrefix("- Takeaway: ")}"
            line.startsWith("- Note: ") -> "- ${context.getString(R.string.summary_note)}${line.removePrefix("- Note: ")}"
            line.startsWith("- Paper: ") -> "- ${context.getString(R.string.summary_paper)}${line.removePrefix("- Paper: ")}"
            line.startsWith("- Possible: ") -> "- ${context.getString(R.string.summary_possible)}${line.removePrefix("- Possible: ")}"
            line == "Link processed successfully." -> context.getString(R.string.summary_link_processed)
            line == "No explicitly mentioned papers found." -> context.getString(R.string.summary_no_explicit_papers)
            line == "No clearly related papers found." -> context.getString(R.string.summary_no_related_papers)
            line.startsWith("Found ") && line.endsWith(" explicitly mentioned paper.") ->
                context.getString(
                    R.string.summary_found_explicit_papers,
                    line.removePrefix("Found ").removeSuffix(" explicitly mentioned paper.").toIntOrNull() ?: 0,
                )
            line.startsWith("Found ") && line.endsWith(" explicitly mentioned papers.") ->
                context.getString(
                    R.string.summary_found_explicit_papers,
                    line.removePrefix("Found ").removeSuffix(" explicitly mentioned papers.").toIntOrNull() ?: 0,
                )
            line.startsWith("No explicit papers found. ") && line.endsWith(" possible papers detected.") ->
                context.getString(
                    R.string.summary_possible_papers_detected,
                    line.removePrefix("No explicit papers found. ").removeSuffix(" possible papers detected.").toIntOrNull() ?: 0,
                )
            line.startsWith("No explicit papers found. ") && line.endsWith(" possible paper detected.") ->
                context.getString(
                    R.string.summary_possible_papers_detected,
                    line.removePrefix("No explicit papers found. ").removeSuffix(" possible paper detected.").toIntOrNull() ?: 0,
                )
            line == "Task completed" -> context.getString(R.string.problem_title_task_completed)
            line == "Task cancelled" -> context.getString(R.string.problem_title_task_cancelled)
            line == "Task failed" -> context.getString(R.string.problem_title_task_failed)
            line == "Cancellation in progress" -> context.getString(R.string.problem_title_cancelling)
            line == "Processing method is busy" -> context.getString(R.string.problem_title_processing_busy)
            line == "Network or provider request failed" -> context.getString(R.string.problem_title_network_error)
            line == "Authentication is not ready" -> context.getString(R.string.problem_title_auth_not_ready)
            line == "Processing timed out" -> context.getString(R.string.problem_title_processing_timeout)
            line == "Processing could not start" -> context.getString(R.string.problem_title_processing_start_failed)
            line == "Processing command was not found" -> context.getString(R.string.problem_title_command_not_found)
            line == "Command template is missing" -> context.getString(R.string.problem_title_command_not_configured)
            line == "Processing command exited with an error" -> context.getString(R.string.problem_title_processing_error)
            line == "Processing method reported a failure" -> context.getString(R.string.problem_title_processing_reported_failure)
            line == "Manual verification required" -> context.getString(R.string.manual_verification_headline)
            line == "Managed browser needs verification again" -> context.getString(R.string.profile_revalidation_headline)
            line == "WeChat link is no longer valid" -> context.getString(R.string.wechat_parameter_error_headline)
            line == "Article body was too short" -> context.getString(R.string.problem_title_body_too_short)
            else -> line
        }
    }
}
