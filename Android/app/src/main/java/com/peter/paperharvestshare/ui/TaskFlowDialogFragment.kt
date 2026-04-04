package com.peter.paperharvestshare.ui

import android.app.Dialog
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.os.bundleOf
import androidx.fragment.app.DialogFragment
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.databinding.DialogTaskFlowBinding
import com.peter.paperharvestshare.databinding.ViewTimelineEntryBinding
import com.peter.paperharvestshare.data.TaskStore
import com.peter.paperharvestshare.util.UiText

class TaskFlowDialogFragment : DialogFragment() {
    private var _binding: DialogTaskFlowBinding? = null
    private val binding: DialogTaskFlowBinding get() = _binding!!

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        _binding = DialogTaskFlowBinding.inflate(LayoutInflater.from(requireContext()))
        bindContent()
        return MaterialAlertDialogBuilder(requireContext())
            .setView(binding.root)
            .create()
    }

    override fun onStart() {
        super.onStart()
        dialog?.window?.setLayout(
            (resources.displayMetrics.widthPixels * 0.9f).toInt(),
            ViewGroup.LayoutParams.WRAP_CONTENT,
        )
    }

    override fun onDestroy() {
        _binding = null
        super.onDestroy()
    }

    private fun bindContent() {
        binding.titleText.text = getString(R.string.topbar_flow)
        binding.closeButton.setOnClickListener { dismiss() }
        val workId = requireArguments().getString(ARG_WORK_ID).orEmpty()
        val record = TaskStore(requireContext()).getByWorkId(workId)
        val timelineLines = record?.relayTimelineSnapshot
            ?.lines()
            ?.map { it.trim() }
            ?.filter { it.isNotBlank() }
            .orEmpty()

        binding.entriesContainer.removeAllViews()
        if (timelineLines.isEmpty()) {
            binding.emptyText.visibility = View.VISIBLE
            binding.emptyText.text = getString(R.string.status_timeline_placeholder)
            return
        }

        binding.emptyText.visibility = View.GONE
        timelineLines.forEach { line ->
            val itemBinding = ViewTimelineEntryBinding.inflate(layoutInflater, binding.entriesContainer, false)
            val parts = line.split(Regex("\\s{2,}"), limit = 2)
            if (parts.size == 2) {
                itemBinding.timeText.text = parts[0]
                itemBinding.labelText.text = UiText.localizeTimelineLabel(requireContext(), parts[1])
            } else {
                itemBinding.timeText.text = ""
                itemBinding.labelText.text = UiText.localizeTimelineLabel(requireContext(), line)
            }
            binding.entriesContainer.addView(itemBinding.root)
        }
    }

    companion object {
        private const val ARG_WORK_ID = "arg_work_id"

        fun newInstance(workId: String): TaskFlowDialogFragment =
            TaskFlowDialogFragment().apply {
                arguments = bundleOf(ARG_WORK_ID to workId)
            }
    }
}
