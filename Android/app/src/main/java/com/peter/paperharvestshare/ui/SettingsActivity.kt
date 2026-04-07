package com.peter.paperharvestshare.ui

import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.view.View
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.widget.RadioButton
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.widget.doAfterTextChanged
import androidx.lifecycle.lifecycleScope
import com.peter.paperharvestshare.R
import com.peter.paperharvestshare.data.RelayClient
import com.peter.paperharvestshare.data.RelaySettingsStore
import com.peter.paperharvestshare.databinding.ActivitySettingsBinding
import com.peter.paperharvestshare.model.ConnectionType
import com.peter.paperharvestshare.model.RelayClientConfig
import com.peter.paperharvestshare.model.RelayModeOption
import com.peter.paperharvestshare.util.AppLanguage
import com.peter.paperharvestshare.util.AppLanguageManager
import com.peter.paperharvestshare.util.SystemBarInsets
import kotlinx.coroutines.launch
import android.graphics.Typeface

class SettingsActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySettingsBinding
    private lateinit var settingsStore: RelaySettingsStore
    private val relayClient = RelayClient()

    private var loadedConfig: RelayClientConfig? = null
    private var loadedBaseUrl: String? = null
    private var lastStatusText: String? = null
    private var lastModeRenderKey: String? = null
    private var selectedLanguage: AppLanguage? = null
    private var authOptionalExpanded = false

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
        binding.connectionTypeRadioGroup.setOnCheckedChangeListener { _, _ -> updateConnectionUi() }
        binding.showAuthButton.setOnClickListener {
            authOptionalExpanded = true
            updateConnectionUi()
        }
        binding.relayBaseUrlInput.doAfterTextChanged { updateConnectionUi() }
        binding.relayAuthInput.doAfterTextChanged { updateConnectionUi() }
    }

    private fun setupStaticTexts() {
        binding.topBarTitleText.text = getString(R.string.topbar_settings)
        binding.topBarBackButton.contentDescription = getString(R.string.action_back)
        binding.serviceSectionTitleText.text = getString(R.string.settings_service_section_title)
        binding.serviceSectionHintText.text = getString(R.string.settings_service_section_hint)
        binding.connectionTypeLabelText.text = getString(R.string.settings_connection_type_label)
        binding.connectionTypeHintText.text = getString(R.string.settings_connection_type_hint)
        binding.connectionEmulatorRadio.text = getString(R.string.settings_connection_type_emulator)
        binding.connectionLocalRadio.text = getString(R.string.settings_connection_type_local)
        binding.connectionPrivateRadio.text = getString(R.string.settings_connection_type_private)
        binding.serviceLabelText.text = getString(R.string.settings_service_label)
        binding.serviceAuthLabelText.text = getString(R.string.settings_service_auth_label)
        binding.serviceAuthHintText.text = getString(R.string.settings_service_auth_hint_optional)
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
        binding.showAuthButton.text = getString(R.string.settings_show_auth_optional)
    }

    private fun loadStoredState() {
        val relayBaseUrl = settingsStore.currentRelayBaseUrl()
        binding.relayBaseUrlInput.setText(relayBaseUrl)
        binding.relayAuthInput.setText(settingsStore.currentRelayAuthToken())
        renderConnectionSelection(settingsStore.currentConnectionType())
        selectedLanguage = AppLanguageManager.currentSelectionForUi(this)
        renderLanguageSelection()
        loadedConfig = settingsStore.cachedClientConfigFor(relayBaseUrl)
        loadedBaseUrl = relayBaseUrl.takeIf { loadedConfig != null }
        authOptionalExpanded = settingsStore.currentRelayAuthToken().isNotBlank()
        updateConnectionUi()
        renderStatus(if (loadedConfig != null) getString(R.string.settings_service_ready) else getString(R.string.settings_fetch_required))
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
        val relayAuthToken = binding.relayAuthInput.text?.toString().orEmpty().trim()
        lifecycleScope.launch {
            setLoading(true)
            renderStatus(getString(R.string.settings_loading))
            val result = relayClient.safeFetchClientConfig(relayBaseUrl, relayAuthToken)
            val config = result.config
            if (result.success && config != null) {
                loadedConfig = config
                loadedBaseUrl = relayBaseUrl
                settingsStore.saveClientConfig(relayBaseUrl, config)
                val preferredModeId = config.modes.firstOrNull { it.id == settingsStore.selectedModeId() && it.enabled }?.id
                    ?: config.modes.firstOrNull { it.id == config.defaultModeId && it.enabled }?.id
                    ?: config.modes.firstOrNull { it.enabled }?.id
                renderModes(config, preferredModeId)
                renderStatus(getString(R.string.settings_service_ready))
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
        val relayAuthToken = binding.relayAuthInput.text?.toString().orEmpty().trim()
        val connectionType = selectedConnectionType()
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

        settingsStore.saveSelection(relayBaseUrl, relayAuthToken, connectionType, config, selectedMode)
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
        authOptionalExpanded = false
        loadStoredState()
    }

    private fun renderStatus(message: String) {
        if (message == lastStatusText) {
            return
        }
        binding.statusValueText.text = message
        lastStatusText = message
    }

    private fun renderConnectionSelection(connectionType: ConnectionType) {
        val showEmulator = shouldShowEmulatorOption()
        binding.connectionEmulatorRadio.visibility = if (showEmulator) View.VISIBLE else View.GONE
        when {
            connectionType == ConnectionType.EMULATOR && showEmulator -> binding.connectionEmulatorRadio.isChecked = true
            connectionType == ConnectionType.LOCAL_NETWORK -> binding.connectionLocalRadio.isChecked = true
            connectionType == ConnectionType.PRIVATE_NETWORK -> binding.connectionPrivateRadio.isChecked = true
            else -> binding.connectionLocalRadio.isChecked = true
        }
    }

    private fun selectedConnectionType(): ConnectionType =
        when (binding.connectionTypeRadioGroup.checkedRadioButtonId) {
            R.id.connectionEmulatorRadio -> ConnectionType.EMULATOR
            R.id.connectionPrivateRadio -> ConnectionType.PRIVATE_NETWORK
            else -> ConnectionType.LOCAL_NETWORK
        }

    private fun updateConnectionUi() {
        val connectionType = selectedConnectionType()
        val placeholder = when (connectionType) {
            ConnectionType.EMULATOR -> getString(R.string.settings_service_placeholder_emulator)
            ConnectionType.LOCAL_NETWORK -> getString(R.string.settings_service_placeholder_local)
            ConnectionType.PRIVATE_NETWORK -> getString(R.string.settings_service_placeholder_private)
        }
        binding.relayBaseUrlInput.hint = placeholder
        binding.serviceHintText.text = buildRelayAddressHint(connectionType)
        binding.serviceAuthHintText.text = buildRelayAuthHint(connectionType)
        val shouldShowAuthFields = connectionType == ConnectionType.PRIVATE_NETWORK ||
            binding.relayAuthInput.text?.toString().orEmpty().trim().isNotBlank() ||
            authOptionalExpanded
        binding.serviceAuthLabelText.visibility = if (shouldShowAuthFields) View.VISIBLE else View.GONE
        binding.serviceAuthContainer.visibility = if (shouldShowAuthFields) View.VISIBLE else View.GONE
        binding.showAuthButton.visibility = if (shouldShowAuthFields) View.GONE else View.VISIBLE
    }

    private fun buildRelayAddressHint(connectionType: ConnectionType): String {
        val normalized = RelaySettingsStore.normalizeBaseUrl(binding.relayBaseUrlInput.text?.toString().orEmpty())
        val host = runCatching { Uri.parse(normalized).host.orEmpty() }.getOrDefault("")
        val baseHint = when (connectionType) {
            ConnectionType.EMULATOR -> getString(R.string.settings_service_hint_emulator)
            ConnectionType.LOCAL_NETWORK -> getString(R.string.settings_service_hint_local)
            ConnectionType.PRIVATE_NETWORK -> getString(R.string.settings_service_hint_private)
        }
        val extraHint = when {
            RelaySettingsStore.looksLikeWildcardHost(host) -> getString(R.string.settings_service_hint_bind_note)
            RelaySettingsStore.looksLikeLoopbackHost(host) -> getString(R.string.settings_service_hint_loopback_note)
            connectionType == ConnectionType.PRIVATE_NETWORK && RelaySettingsStore.looksLikeLanHost(host) ->
                getString(R.string.settings_service_hint_private_with_lan)
            connectionType == ConnectionType.LOCAL_NETWORK && RelaySettingsStore.looksLikePrivateNetworkHost(host) ->
                getString(R.string.settings_service_hint_local_with_private)
            else -> ""
        }
        return if (extraHint.isBlank()) {
            baseHint
        } else {
            "$baseHint\n$extraHint"
        }
    }

    private fun buildRelayAuthHint(connectionType: ConnectionType): String {
        val hasToken = binding.relayAuthInput.text?.toString().orEmpty().trim().isNotBlank()
        return when {
            connectionType == ConnectionType.PRIVATE_NETWORK && hasToken ->
                getString(R.string.settings_service_auth_hint_private_ready)
            connectionType == ConnectionType.PRIVATE_NETWORK ->
                getString(R.string.settings_service_auth_hint_private)
            hasToken -> getString(R.string.settings_service_auth_hint_saved)
            else -> getString(R.string.settings_service_auth_hint_optional)
        }
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
                text = buildModeText(mode)
                tag = mode.id
                setTextColor(getColor(com.peter.paperharvestshare.R.color.text_primary))
                textSize = 15f
                setLineSpacing(dp(4).toFloat(), 1f)
                minimumHeight = dp(72)
                setPadding(dp(12), dp(14), dp(12), dp(14))
            }
            val params = android.widget.RadioGroup.LayoutParams(
                android.widget.RadioGroup.LayoutParams.MATCH_PARENT,
                android.widget.RadioGroup.LayoutParams.WRAP_CONTENT,
            ).apply {
                if (binding.modeRadioGroup.childCount > 0) {
                    topMargin = dp(12)
                }
            }
            radioButton.layoutParams = params
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
        val host = uri?.host.orEmpty()
        val isValid = uri != null &&
            (uri.scheme == "http" || uri.scheme == "https") &&
            host.isNotBlank()
        return if (isValid) {
            val validationError = when {
                RelaySettingsStore.looksLikeWildcardHost(host) -> getString(R.string.settings_invalid_bind_address)
                RelaySettingsStore.looksLikeLoopbackHost(host) -> getString(R.string.settings_invalid_loopback_address)
                else -> null
            }
            if (validationError != null) {
                binding.relayBaseUrlInput.error = validationError
                Toast.makeText(this, validationError, Toast.LENGTH_SHORT).show()
                null
            } else {
                binding.relayBaseUrlInput.error = null
                normalized
            }
        } else {
            binding.relayBaseUrlInput.error = getString(R.string.settings_invalid_url)
            Toast.makeText(this, getString(R.string.settings_invalid_url), Toast.LENGTH_SHORT).show()
            null
        }
    }

    private fun buildModeText(mode: RelayModeOption): CharSequence {
        val label = com.peter.paperharvestshare.util.UiText.processingModeLabel(this, mode.id, mode.label)
        if (mode.description.isBlank()) {
            return label
        }
        return SpannableStringBuilder().apply {
            append(label)
            setSpan(StyleSpan(Typeface.BOLD), 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            append('\n')
            val descriptionStart = length
            append(mode.description)
            setSpan(
                ForegroundColorSpan(getColor(R.color.text_secondary)),
                descriptionStart,
                length,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
            )
            setSpan(
                RelativeSizeSpan(0.92f),
                descriptionStart,
                length,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
            )
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
        binding.relayAuthInput.isEnabled = !loading
        binding.showAuthButton.isEnabled = !loading
        binding.connectionEmulatorRadio.isEnabled = !loading
        binding.connectionLocalRadio.isEnabled = !loading
        binding.connectionPrivateRadio.isEnabled = !loading
    }

    private fun shouldShowEmulatorOption(): Boolean =
        com.peter.paperharvestshare.BuildConfig.DEBUG ||
            settingsStore.currentConnectionType() == ConnectionType.EMULATOR ||
            isProbablyEmulator()

    private fun isProbablyEmulator(): Boolean =
        Build.FINGERPRINT.contains("generic", ignoreCase = true) ||
            Build.MODEL.contains("Emulator", ignoreCase = true) ||
            Build.MANUFACTURER.contains("Genymotion", ignoreCase = true) ||
            Build.PRODUCT.contains("sdk", ignoreCase = true)

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()
}
