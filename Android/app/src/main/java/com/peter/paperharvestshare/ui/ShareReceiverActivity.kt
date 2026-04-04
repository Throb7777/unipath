package com.peter.paperharvestshare.ui

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.databinding.ActivityShareReceiverBinding
import com.peter.paperharvestshare.model.ParsedShare
import com.peter.paperharvestshare.util.SystemBarInsets
import com.peter.paperharvestshare.util.UiText
import com.peter.paperharvestshare.util.UrlNormalizer
import com.peter.paperharvestshare.worker.SubmitWorker

class ShareReceiverActivity : AppCompatActivity() {
    private lateinit var binding: ActivityShareReceiverBinding
    private lateinit var parsedShare: ParsedShare
    private lateinit var settingsStore: RelaySettingsStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        binding = ActivityShareReceiverBinding.inflate(layoutInflater)
        setContentView(binding.root)
        SystemBarInsets.applyTo(binding.root)

        settingsStore = RelaySettingsStore(this)
        setupStaticTexts()
        parsedShare = UrlNormalizer.parse(this, resolveSharedText(intent))
        render(parsedShare)

        binding.topBarBackButton.setOnClickListener { finish() }
        binding.cancelButton.setOnClickListener { finish() }
        binding.submitButton.setOnClickListener {
            if (!parsedShare.isValid) {
                Toast.makeText(this, parsedShare.errorMessage ?: getString(R.string.share_error_unsupported), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val workId = SubmitWorker.enqueue(this, parsedShare)
            startActivity(
                Intent(this, SubmissionStatusActivity::class.java)
                    .putExtra(SubmissionStatusActivity.EXTRA_WORK_ID, workId.toString()),
            )
            finish()
        }
    }

    private fun setupStaticTexts() {
        binding.topBarTitleText.text = getString(R.string.topbar_share)
        binding.topBarBackButton.contentDescription = getString(R.string.action_back)
        binding.sourceLabelText.text = getString(R.string.share_source_label)
        binding.serviceLabelText.text = getString(R.string.share_service_label)
        binding.normalizedLabelText.text = getString(R.string.share_normalized_label)
        binding.rawLabelText.text = getString(R.string.share_raw_label)
        binding.instructionLabelText.text = getString(R.string.share_instruction_label)
        binding.cancelButton.text = getString(R.string.action_cancel)
        binding.submitButton.text = getString(R.string.action_submit)
    }

    private fun render(parsedShare: ParsedShare) {
        binding.sourceValueText.text = UiText.sourceLabel(this, parsedShare.sourceType)
        binding.serviceValueText.text = settingsStore.currentRelayBaseUrl()
        binding.normalizedValueText.text = parsedShare.normalizedUrl ?: "-"
        binding.rawValueText.text = parsedShare.rawSharedText.ifBlank { "-" }
        binding.instructionValueText.text = settingsStore.selectedModeSummary()
        binding.submitButton.isEnabled = parsedShare.isValid
        if (!parsedShare.isValid) {
            Toast.makeText(this, parsedShare.errorMessage ?: getString(R.string.share_error_unsupported), Toast.LENGTH_SHORT).show()
        }
    }

    private fun resolveSharedText(intent: Intent): String? {
        intent.getStringExtra(Intent.EXTRA_TEXT)?.let { return it }
        val clipData = intent.clipData ?: return null
        if (clipData.itemCount == 0) {
            return null
        }
        return clipData.getItemAt(0).coerceToText(this)?.toString()
    }
}
