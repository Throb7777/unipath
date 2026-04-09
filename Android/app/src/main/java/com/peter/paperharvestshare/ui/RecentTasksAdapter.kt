package com.peter.paperharvestshare.ui

import android.net.Uri
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.DrawableCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.databinding.ViewRecentTaskBinding
import com.peter.paperharvestshare.model.SourceType
import com.peter.paperharvestshare.model.SubmissionRecord
import com.peter.paperharvestshare.model.TaskState
import com.peter.paperharvestshare.util.UiText
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.max

class RecentTasksAdapter(
    private val host: MainActivity,
    private val onTaskClick: (SubmissionRecord) -> Unit,
) : ListAdapter<SubmissionRecord, RecentTasksAdapter.RecentTaskViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecentTaskViewHolder {
        val binding = ViewRecentTaskBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return RecentTaskViewHolder(binding)
    }

    override fun onBindViewHolder(holder: RecentTaskViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class RecentTaskViewHolder(
        private val binding: ViewRecentTaskBinding,
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(record: SubmissionRecord) {
            val (sourceLabel, sourceBackground, sourceForeground) = when (record.sourceType) {
                SourceType.WECHAT_ARTICLE -> Triple(UiText.sourceLabel(host, record.sourceType), R.color.success_soft, R.color.success)
                SourceType.XIAOHONGSHU -> Triple(UiText.sourceLabel(host, record.sourceType), R.color.danger_soft, R.color.danger)
                SourceType.UNKNOWN -> Triple(UiText.sourceLabel(host, record.sourceType), R.color.pending_soft, R.color.pending)
            }
            val (stateLabel, stateBackground, stateForeground) = host.stateAppearanceForAdapter(record)

            binding.sourceChipText.text = sourceLabel
            binding.stateChipText.text = stateLabel
            binding.serialText.text = "#${record.sequenceNumber}"
            tintChip(binding.sourceChipText, sourceBackground, sourceForeground)
            tintChip(binding.stateChipText, stateBackground, stateForeground)

            binding.targetText.text = buildTargetSummary(record)
            binding.messageText.text = host.buildMessageSummaryForAdapter(record)
            binding.timeText.text = buildMetaSummary(record)
            binding.root.setOnClickListener { onTaskClick(record) }
        }

        private fun tintChip(view: android.widget.TextView, backgroundColorRes: Int, foregroundColorRes: Int) {
            val wrapped = DrawableCompat.wrap(view.background.mutate())
            DrawableCompat.setTint(wrapped, ContextCompat.getColor(host, backgroundColorRes))
            view.background = wrapped
            view.setTextColor(ContextCompat.getColor(host, foregroundColorRes))
        }

        private fun buildTargetSummary(record: SubmissionRecord): String {
            val hostName = runCatching { Uri.parse(record.normalizedUrl).host.orEmpty() }.getOrDefault("")
                .removePrefix("www.")
                .ifBlank {
                    when (record.sourceType) {
                        SourceType.WECHAT_ARTICLE -> "mp.weixin.qq.com"
                        SourceType.XIAOHONGSHU -> "xiaohongshu.com"
                        SourceType.UNKNOWN -> host.getString(R.string.recent_target_unknown)
                    }
                }
            return hostName
        }

        private fun buildMetaSummary(record: SubmissionRecord): String {
            val parts = mutableListOf(formatRelativeTime(record.updatedAtEpochMs))
            buildDurationSummary(record)?.let(parts::add)
            record.modeIdSnapshot?.takeIf { it.isNotBlank() }?.let { modeId ->
                parts.add(UiText.processingModeLabel(host, modeId, record.modeLabelSnapshot))
            }
            record.relayTaskId?.takeIf { it.isNotBlank() }?.let { parts.add(UiText.taskIdLabel(host, it)) }
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
            val text = UiText.formatDuration(host, durationMs)
            return text.takeIf { it != host.getString(R.string.status_duration_placeholder) }
        }

        private fun formatRelativeTime(updatedAtEpochMs: Long): String {
            val diffMs = max(0L, System.currentTimeMillis() - updatedAtEpochMs)
            val diffMinutes = diffMs / 60_000
            val diffHours = diffMs / 3_600_000
            val diffDays = diffMs / 86_400_000

            return when {
                diffMinutes < 1 -> host.getString(R.string.recent_time_now)
                diffMinutes < 60 -> UiText.relativeTimeMinutes(host, diffMinutes)
                diffHours < 24 -> UiText.relativeTimeHours(host, diffHours)
                else -> UiText.relativeTimeDays(host, diffDays)
            }
        }
    }

    private object DiffCallback : DiffUtil.ItemCallback<SubmissionRecord>() {
        override fun areItemsTheSame(oldItem: SubmissionRecord, newItem: SubmissionRecord): Boolean =
            oldItem.workId == newItem.workId

        override fun areContentsTheSame(oldItem: SubmissionRecord, newItem: SubmissionRecord): Boolean =
            oldItem == newItem
    }
}
