package com.jz.ai

import android.os.Bundle
import android.view.Gravity
import android.view.LayoutInflater
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.widget.doOnTextChanged
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import com.jz.ai.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var settings: Settings
    private lateinit var client: JZAiClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        settings = Settings(this)
        client = JZAiClient(settings.baseUrl, settings.apiKey)

        binding.toolbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_settings -> { showSettings(); true }
                R.id.action_clear -> { clearChat(); true }
                else -> false
            }
        }

        binding.sendButton.setOnClickListener { send() }
        binding.input.doOnTextChanged { text, _, _, _ ->
            binding.sendButton.isEnabled = !text.isNullOrBlank()
        }
        binding.sendButton.isEnabled = false

        if (!settings.isConfigured) {
            addMessage("Configure d'abord le serveur et ta cle d'API (menu ⋮ en haut a droite).", isUser = false)
            showSettings()
        } else {
            checkHealth()
        }
    }

    // --------------------------- reglages ---------------------------
    private fun showSettings() {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_settings, null)
        val urlField = view.findViewById<EditText>(R.id.urlField)
        val keyField = view.findViewById<EditText>(R.id.keyField)
        urlField.setText(settings.baseUrl.ifBlank { Settings.DEFAULT_URL })
        keyField.setText(settings.apiKey)

        AlertDialog.Builder(this)
            .setTitle(R.string.settings_title)
            .setView(view)
            .setPositiveButton(R.string.save) { _, _ ->
                val url = urlField.text.toString().trim()
                val key = keyField.text.toString().trim()
                if (url.isBlank() || key.isBlank()) {
                    toast(getString(R.string.settings_incomplete))
                    return@setPositiveButton
                }
                settings.baseUrl = url
                settings.apiKey = key
                client.configure(settings.baseUrl, settings.apiKey)
                checkHealth()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun checkHealth() {
        lifecycleScope.launch {
            binding.status.text = getString(R.string.status_checking)
            try {
                val info = client.health()
                binding.status.text = getString(R.string.status_connected, info)
            } catch (e: Exception) {
                binding.status.text = getString(R.string.status_offline, e.message ?: "")
            }
        }
    }

    // ----------------------------- chat -----------------------------
    private fun clearChat() {
        client.reset()
        binding.chatContainer.removeAllViews()
    }

    private fun send() {
        val prompt = binding.input.text.toString().trim()
        if (prompt.isEmpty()) return
        if (!settings.isConfigured) {
            showSettings()
            return
        }

        binding.input.setText("")
        addMessage(prompt, isUser = true)

        val bubble = addMessage("…", isUser = false)
        setBusy(true)

        lifecycleScope.launch {
            val answer = StringBuilder()
            try {
                client.askStreaming(prompt) { piece ->
                    answer.append(piece)
                    bubble.text = answer.toString()
                    binding.chatScroll.post {
                        binding.chatScroll.fullScroll(android.view.View.FOCUS_DOWN)
                    }
                }
                if (answer.isBlank()) bubble.text = getString(R.string.empty_answer)
            } catch (e: Exception) {
                bubble.text = e.message ?: getString(R.string.unknown_error)
                Snackbar.make(binding.root, R.string.request_failed, Snackbar.LENGTH_LONG)
                    .setAction(R.string.settings_short) { showSettings() }
                    .show()
            } finally {
                setBusy(false)
            }
        }
    }

    private fun setBusy(busy: Boolean) {
        binding.progress.visibility = if (busy) android.view.View.VISIBLE else android.view.View.GONE
        binding.sendButton.isEnabled = !busy && binding.input.text.isNotBlank()
        binding.input.isEnabled = !busy
    }

    /** Ajoute une bulle et renvoie son TextView (pour le streaming). */
    private fun addMessage(text: String, isUser: Boolean): TextView {
        val bubble = TextView(this).apply {
            this.text = text
            setTextIsSelectable(true)
            setBackgroundResource(if (isUser) R.drawable.bubble_user else R.drawable.bubble_ai)
            setPadding(32, 24, 32, 24)
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text))
        }
        val params = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ).apply {
            gravity = if (isUser) Gravity.END else Gravity.START
            topMargin = 12
            bottomMargin = 12
            marginStart = if (isUser) 96 else 0
            marginEnd = if (isUser) 0 else 96
        }
        binding.chatContainer.addView(bubble, params)
        binding.chatScroll.post { binding.chatScroll.fullScroll(android.view.View.FOCUS_DOWN) }
        return bubble
    }

    private fun toast(message: String) =
        Snackbar.make(binding.root, message, Snackbar.LENGTH_LONG).show()
}
