package com.jz.ai

import android.content.Context

/**
 * Reglages persistes localement.
 *
 * La cle d'API est saisie par l'utilisateur puis stockee dans les
 * SharedPreferences privees de l'app : elle n'est jamais compilee dans l'apk,
 * qui serait sinon decompilable par n'importe qui.
 */
class Settings(context: Context) {

    private val prefs = context.getSharedPreferences("jzai", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = prefs.getString(KEY_URL, DEFAULT_URL).orEmpty()
        set(value) = prefs.edit().putString(KEY_URL, value.trim().trimEnd('/')).apply()

    var apiKey: String
        get() = prefs.getString(KEY_API, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_API, value.trim()).apply()

    val isConfigured: Boolean
        get() = baseUrl.isNotBlank() && apiKey.isNotBlank()

    companion object {
        // 127.0.0.1 = Termux tourne sur le meme telephone que l'apk.
        const val DEFAULT_URL = "http://127.0.0.1:8000"
        private const val KEY_URL = "base_url"
        private const val KEY_API = "api_key"
    }
}
