package com.jz.ai

import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.widget.doOnTextChanged
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import com.jz.ai.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private companion object {
        /** Doit rester aligne sur MAX_FILE_BYTES cote serveur. */
        const val MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
        const val MAX_ATTACHMENTS = 8
    }

    private lateinit var binding: ActivityMainBinding
    private lateinit var settings: Settings
    private lateinit var client: JZAiClient

    private val pending = mutableListOf<Attachment>()

    private val pickFile = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri -> uri?.let { addAttachment(it) } }

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

        binding.attachButton.setOnClickListener {
            if (pending.size >= MAX_ATTACHMENTS) {
                toast(getString(R.string.too_many_files, MAX_ATTACHMENTS))
            } else {
                pickFile.launch(arrayOf("*/*"))
            }
        }

        binding.sendButton.setOnClickListener { send() }
        binding.input.doOnTextChanged { _, _, _, _ -> refreshSendButton() }
        refreshSendButton()

        if (!settings.isConfigured) {
            addMessage(getString(R.string.first_run_hint), isUser = false)
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
                binding.status.text = getString(R.string.status_connected, client.health())
            } catch (e: Exception) {
                binding.status.text = getString(R.string.status_offline, e.message.orEmpty())
            }
        }
    }

    // ------------------------- pieces jointes ------------------------
    private fun addAttachment(uri: Uri) {
        lifecycleScope.launch {
            try {
                val attachment = withContext(Dispatchers.IO) { readAttachment(uri) }
                pending.add(attachment)
                refreshAttachments()
                refreshSendButton()
            } catch (e: Exception) {
                toast(e.message ?: getString(R.string.unknown_error))
            }
        }
    }

    /** Lit le fichier pointe par [uri] en verifiant sa taille avant de l'avaler. */
    private fun readAttachment(uri: Uri): Attachment {
        var name = "fichier"
        var size = -1L
        contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    .takeIf { it >= 0 }
                    ?.let { name = cursor.getString(it) ?: name }
                cursor.getColumnIndex(OpenableColumns.SIZE)
                    .takeIf { it >= 0 && !cursor.isNull(it) }
                    ?.let { size = cursor.getLong(it) }
            }
        }
        if (size > MAX_ATTACHMENT_BYTES) {
            throw JZAiException(getString(R.string.file_too_big, name, MAX_ATTACHMENT_BYTES / 1024 / 1024))
        }

        val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw JZAiException(getString(R.string.file_unreadable, name))
        // Certains fournisseurs ne renseignent pas SIZE : on revalide apres lecture.
        if (bytes.size > MAX_ATTACHMENT_BYTES) {
            throw JZAiException(getString(R.string.file_too_big, name, MAX_ATTACHMENT_BYTES / 1024 / 1024))
        }
        if (bytes.isEmpty()) throw JZAiException(getString(R.string.file_empty, name))

        return Attachment(name, bytes, contentResolver.getType(uri).orEmpty())
    }

    private fun refreshAttachments() {
        binding.attachmentBar.removeAllViews()
        binding.attachmentBar.visibility = if (pending.isEmpty()) View.GONE else View.VISIBLE
        pending.forEach { attachment ->
            val chip = TextView(this).apply {
                text = getString(R.string.chip_file, attachment.filename)
                setBackgroundResource(R.drawable.chip_background)
                setPadding(24, 12, 24, 12)
                setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text))
                textSize = 12f
                setOnClickListener {
                    pending.remove(attachment)
                    refreshAttachments()
                    refreshSendButton()
                }
            }
            val params = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { marginEnd = 12 }
            binding.attachmentBar.addView(chip, params)
        }
    }

    private fun refreshSendButton() {
        binding.sendButton.isEnabled =
            binding.progress.visibility != View.VISIBLE &&
                (binding.input.text.isNotBlank() || pending.isNotEmpty())
    }

    // ----------------------------- chat -----------------------------
    private fun clearChat() {
        client.reset()
        pending.clear()
        refreshAttachments()
        binding.chatContainer.removeAllViews()
        refreshSendButton()
    }

    private fun send() {
        if (!settings.isConfigured) {
            showSettings()
            return
        }
        val typed = binding.input.text.toString().trim()
        val attachments = pending.toList()
        if (typed.isEmpty() && attachments.isEmpty()) return

        // Un fichier seul, sans consigne : on demande un resume par defaut.
        val prompt = typed.ifEmpty { getString(R.string.default_file_prompt) }

        binding.input.setText("")
        pending.clear()
        refreshAttachments()

        val shown = buildString {
            append(prompt)
            attachments.forEach { append("\n📎 ").append(it.filename) }
        }
        addMessage(shown, isUser = true)

        val bubble = addMessage("…", isUser = false)
        setBusy(true)

        lifecycleScope.launch {
            val answer = StringBuilder()
            try {
                val ids = attachments.map { attachment ->
                    bubble.text = getString(R.string.uploading, attachment.filename)
                    client.upload(attachment)
                }
                bubble.text = ""
                client.askStreaming(prompt, ids) { piece ->
                    answer.append(piece)
                    bubble.text = answer.toString()
                    scrollDown()
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
        binding.progress.visibility = if (busy) View.VISIBLE else View.GONE
        binding.input.isEnabled = !busy
        binding.attachButton.isEnabled = !busy
        refreshSendButton()
    }

    private fun scrollDown() =
        binding.chatScroll.post { binding.chatScroll.fullScroll(View.FOCUS_DOWN) }

    /** Ajoute une bulle et renvoie son TextView (mis a jour pendant le streaming). */
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
        scrollDown()
        return bubble
    }

    private fun toast(message: String) =
        Snackbar.make(binding.root, message, Snackbar.LENGTH_LONG).show()
}
