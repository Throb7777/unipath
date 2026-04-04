package com.peter.paperharvestshare.ui

import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.RadioButton
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelayClient
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.databinding.ActivitySettingsBinding
import com.peter.paperharvestshare.model.RelayClientConfig
import com.peter.paperharvestshare.model.RelayModeOption
import com.peter.paperharvestshare.util.AppLanguage
import com.peter.paperharvestshare.util.AppLanguageManager
import com.peter.paperharvestshare.util.SystemBarInsets
import kotlinx.coroutines.launch

class SettingsActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySettingsBinding
    private lateinit var settingsStore: RelaySettingsStore
    private val relayClient = RelayClient()

    private var loadedConfig: RelayClientConfig? = null
    private var loadedBaseUrl: String? = null
    private var lastStatusText: String? = null
    private var lastModeRenderKey: String? = null
    private var selectedLanguage: AppLanguage? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        SystemBarInsets.applyTo(binding.root)

        settingsStore = RelaySettingsStore(this)
        setupStaticTexts()
        loadStoredState()

        binding.topBarBackButton.setOnClickListener { finish() }
        binding.testConnectionButton.setOnClickListener { fetchModes() }
        binding.saveSettingsButton.setOnClickListener { saveSettings() }
        binding.resetDefaultsButton.setOnClickListener { restoreDefaults() }
    }

    private fun setupStaticTexts() {
        binding.topBarTitleText.text = getString(R.string.topbar_settings)
        binding.topBarBackButton.contentDescription = getString(R.string.action_back)
        binding.serviceSectionTitleText.text = getString(R.string.settings_service_section_title)
        binding.serviceSectionHintText.text = getString(R.string.settings_service_section_hint)
        binding.serviceLabelText.text = getString(R.string.settings_service_label)
        binding.serviceHintText.text = getString(R.string.settings_service_hint)
        binding.appSectionTitleText.text = getString(R.string.settings_app_section_title)
        binding.appSectionHintText.text = getString(R.string.settings_app_section_hint)
        binding.languageLabelText.text = getString(R.string.settings_language_label)
        binding.languageHintText.text = getString(R.string.settings_language_hint)
        binding.languageEnglishRadio.text = getString(R.string.language_english)
        binding.languageChineseRadio.text = getString(R.string.language_simplified_chinese)
        binding.statusLabelText.text = getString(R.string.settings_status_label)
        binding.modeLabelText.text = getString(R.string.settings_mode_label)
        binding.modeHintText.text = getString(R.string.settings_mode_hint)
        binding.modeEmptyText.text = getString(R.string.settings_no_modes)
        binding.testConnectionButton.text = getString(R.string.settings_test)
        binding.saveSettingsButton.text = getString(R.string.settings_save)
        binding.resetDefaultsButton.text = getString(R.string.settings_reset)
    }

    private fun loadStoredState() {
        val relayBaseUrl = settingsStore.currentRelayBaseUrl()
        binding.relayBaseUrlInput.setText(relayBaseUrl)
        selectedLanguage = AppLanguageManager.currentSelectionForUi(this)
        renderLanguageSelection()
        loadedConfig = settingsStore.cachedClientConfigFor(relayBaseUrl)
        loadedBaseUrl = relayBaseUrl.takeIf { loadedConfig != null }
        renderStatus(
            loadedConfig?.let { "${settingsStore.lastServiceSummary().orEmpty()}\n${getString(R.string.settings_service_ready)}" }
                ?: (settingsStore.lastServiceSummary() ?: getString(R.string.settings_fetch_required)),
        )
        renderModes(loadedConfig, settingsStore.selectedModeId())
    }

    private fun renderLanguageSelection() {
        when (selectedLanguage ?: AppLanguageManager.currentSelectionForUi(this)) {
            AppLanguage.ENGLISH -> binding.languageEnglishRadio.isChecked = true
            AppLanguage.SIMPLIFIED_CHINESE -> binding.languageChineseRadio.isChecked = true
        }
    }

    private fun fetchModes() {
        val relayBaseUrl = validateRelayBaseUrl() ?: return
        lifecycleScope.launch {
            setLoading(true)
            renderStatus(getString(R.string.settings_loading))
            val result = relayClient.safeFetchClientConfig(relayBaseUrl)
            val config = result.config
            if (result.success && config != null) {
                loadedConfig = config
                loadedBaseUrl = relayBaseUrl
                settingsStore.saveClientConfig(relayBaseUrl, config)
                val preferredModeId = config.modes.firstOrNull { it.id == settingsStore.selectedModeId() && it.enabled }?.id
                    ?: config.modes.firstOrNull { it.id == config.defaultModeId && it.enabled }?.id
                    ?: config.modes.firstOrNull { it.enabled }?.id
                renderModes(config, preferredModeId)
                renderStatus(buildString {
                    append(formatServiceSummary(config))
                    append('\n')
                    append(getString(R.string.settings_service_ready))
                })
            } else {
                renderModes(null, null)
                renderStatus(result.message.ifBlank { getString(R.string.settings_fetch_failed) })
            }
            setLoading(false)
        }
    }

    private fun saveSettings() {
        applySelectedLanguageIfNeeded()
        val relayBaseUrl = validateRelayBaseUrl() ?: return
        val config = if (loadedBaseUrl == relayBaseUrl) {
            loadedConfig
        } else {
            settingsStore.cachedClientConfigFor(relayBaseUrl)
        }
        if (config == null) {
            renderStatus(getString(R.string.settings_fetch_required))
            Toast.makeText(this, getString(R.string.settings_fetch_required), Toast.LENGTH_SHORT).show()
            return
        }

        val selectedMode = resolveSelectedMode(config)
        if (selectedMode == null) {
            renderStatus(getString(R.string.settings_no_modes))
            Toast.makeText(this, getString(R.string.settings_no_modes), Toast.LENGTH_SHORT).show()
            return
        }

        settingsStore.saveSelection(relayBaseUrl, config, selectedMode)
        Toast.makeText(this, getString(R.string.settings_save_done), Toast.LENGTH_SHORT).show()
        finish()
    }

    private fun restoreDefaults() {
        settingsStore.restoreDefaults()
        Toast.makeText(this, getString(R.string.settings_reset_done), Toast.LENGTH_SHORT).show()
        loadedConfig = null
        loadedBaseUrl = null
        lastModeRenderKey = null
        lastStatusText = null
        loadStoredState()
    }

    private fun renderStatus(message: String) {
        if (message == lastStatusText) {
            return
        }
        binding.statusValueText.text = message
        lastStatusText = message
    }

    private fun renderModes(config: RelayClientConfig?, selectedModeId: String?) {
        val modes = config?.modes?.filter { it.enabled }.orEmpty()
        val renderKey = buildString {
            append(selectedModeId.orEmpty())
            append("||")
            modes.forEach { mode ->
                append(mode.id)
                append('|')
                append(mode.label)
                append('|')
                append(mode.description)
                append("||")
            }
        }
        if (renderKey == lastModeRenderKey) {
            return
        }

        binding.modeRadioGroup.removeAllViews()
        binding.modeEmptyText.visibility = if (modes.isEmpty()) View.VISIBLE else View.GONE
        binding.modeRadioGroup.visibility = if (modes.isEmpty()) View.GONE else View.VISIBLE

        modes.forEach { mode ->
            val radioButton = RadioButton(this).apply {
                id = View.generateViewId()
                text = buildString {
                    append(mode.label)
                    if (mode.description.isNotBlank()) {
                        append('\n')
                        append(mode.description)
                    }
                }
                tag = mode.id
                setTextColor(getColor(com.peter.paperharvestshare.R.color.text_primary))
                textSize = 15f
            }
            binding.modeRadioGroup.addView(radioButton)
            if (mode.id == selectedModeId) {
                radioButton.isChecked = true
            }
        }

        if (binding.modeRadioGroup.checkedRadioButtonId == View.NO_ID && binding.modeRadioGroup.childCount > 0) {
            (binding.modeRadioGroup.getChildAt(0) as? RadioButton)?.isChecked = true
        }
        lastModeRenderKey = renderKey
    }

    private fun resolveSelectedMode(config: RelayClientConfig): RelayModeOption? {
        val checkedId = binding.modeRadioGroup.checkedRadioButtonId
        val checkedView = binding.modeRadioGroup.findViewById<RadioButton?>(checkedId)
        val selectedModeId = checkedView?.tag as? String
        return config.modes.firstOrNull { it.id == selectedModeId && it.enabled }
            ?: config.modes.firstOrNull { it.id == config.defaultModeId && it.enabled }
            ?: config.modes.firstOrNull { it.enabled }
    }

    private fun validateRelayBaseUrl(): String? {
        val normalized = RelaySettingsStore.normalizeBaseUrl(binding.relayBaseUrlInput.text?.toString().orEmpty())
        val uri = runCatching { Uri.parse(normalized) }.getOrNull()
        val isValid = uri != null &&
            (uri.scheme == "http" || uri.scheme == "https") &&
            !uri.host.isNullOrBlank()
        return if (isValid) {
            normalized
        } else {
            binding.relayBaseUrlInput.error = getString(R.string.settings_invalid_url)
            Toast.makeText(this, getString(R.string.settings_invalid_url), Toast.LENGTH_SHORT).show()
            null
        }
    }

    private fun applySelectedLanguageIfNeeded() {
        val nextLanguage = when (binding.languageRadioGroup.checkedRadioButtonId) {
            R.id.languageChineseRadio -> AppLanguage.SIMPLIFIED_CHINESE
            else -> AppLanguage.ENGLISH
        }
        if (nextLanguage != selectedLanguage) {
            selectedLanguage = nextLanguage
            AppLanguageManager.saveAndApply(this, nextLanguage)
        }
    }

    private fun setLoading(loading: Boolean) {
        binding.testConnectionButton.isEnabled = !loading
        binding.saveSettingsButton.isEnabled = !loading
        binding.resetDefaultsButton.isEnabled = !loading
        binding.relayBaseUrlInput.isEnabled = !loading
    }

    private fun formatServiceSummary(config: RelayClientConfig): String =
        if (config.serviceVersion.isBlank()) {
            config.serviceName
        } else {
            "${config.serviceName} ${config.serviceVersion}"
        }
}
