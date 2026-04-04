package com.peter.paperharvestshare

import android.app.Application
import com.peter.paperharvestshare.util.AppLanguageManager

class PaperHarvestShareApp : Application() {
    override fun onCreate() {
        super.onCreate()
        AppLanguageManager.applyStoredLanguage(this)
    }
}
