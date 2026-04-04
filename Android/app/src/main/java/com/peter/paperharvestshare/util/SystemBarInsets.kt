package com.peter.paperharvestshare.util

import android.view.View
import androidx.core.graphics.Insets
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding

object SystemBarInsets {
    fun applyTo(view: View) {
        val initialPaddingLeft = view.paddingLeft
        val initialPaddingTop = view.paddingTop
        val initialPaddingRight = view.paddingRight
        val initialPaddingBottom = view.paddingBottom

        ViewCompat.setOnApplyWindowInsetsListener(view) { target, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            target.updatePadding(
                left = initialPaddingLeft + systemBars.left,
                top = initialPaddingTop + systemBars.top,
                right = initialPaddingRight + systemBars.right,
                bottom = initialPaddingBottom + systemBars.bottom,
            )
            WindowInsetsCompat.Builder(insets)
                .setInsets(WindowInsetsCompat.Type.systemBars(), Insets.NONE)
                .build()
        }

        ViewCompat.requestApplyInsets(view)
    }
}
