package com.jz.ai

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Client JZ-AI pour l'apk.
 *
 * build.gradle : rien a ajouter (HttpURLConnection + org.json sont dans l'SDK).
 * AndroidManifest.xml : <uses-permission android:name="android.permission.INTERNET"/>
 *
 * En HTTP simple (pas de HTTPS) ajoute aussi, sur <application> :
 *   android:usesCleartextTraffic="true"
 */
class JZAiClient(
    private val baseUrl: String,   // ex: "http://192.168.1.20:8000"
    private val apiKey: String,    // ex: "jz-xxxxxxxx..."
    private val model: String = "jz-mini-1",
) {

    private val history = mutableListOf<Pair<String, String>>()  // role to content

    /** Envoie un message et renvoie la reponse complete du modele. */
    suspend fun ask(prompt: String): String = withContext(Dispatchers.IO) {
        history.add("user" to prompt)

        val messages = JSONArray()
        history.forEach { (role, content) ->
            messages.put(JSONObject().put("role", role).put("content", content))
        }

        val body = JSONObject()
            .put("model", model)
            .put("messages", messages)
            .put("temperature", 0.7)
            .put("max_tokens", 512)
            .put("stream", false)
            .toString()

        val conn = (URL("$baseUrl/v1/chat/completions").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 15_000
            readTimeout = 120_000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Authorization", "Bearer $apiKey")
        }

        try {
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

            if (conn.responseCode !in 200..299) {
                val err = conn.errorStream?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
                throw RuntimeException("JZ-AI HTTP ${conn.responseCode}: $err")
            }

            val json = JSONObject(conn.inputStream.bufferedReader().use(BufferedReader::readText))
            val answer = json.getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .getString("content")

            history.add("assistant" to answer)
            answer
        } finally {
            conn.disconnect()
        }
    }

    /** Version streaming : [onToken] est appele au fil de la generation. */
    suspend fun askStreaming(prompt: String, onToken: (String) -> Unit): String =
        withContext(Dispatchers.IO) {
            history.add("user" to prompt)

            val messages = JSONArray()
            history.forEach { (role, content) ->
                messages.put(JSONObject().put("role", role).put("content", content))
            }

            val body = JSONObject()
                .put("model", model)
                .put("messages", messages)
                .put("stream", true)
                .toString()

            val conn = (URL("$baseUrl/v1/chat/completions").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = 15_000
                readTimeout = 120_000
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Accept", "text/event-stream")
                setRequestProperty("Authorization", "Bearer $apiKey")
            }

            val full = StringBuilder()
            try {
                conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

                if (conn.responseCode !in 200..299) {
                    val err = conn.errorStream?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
                    throw RuntimeException("JZ-AI HTTP ${conn.responseCode}: $err")
                }

                conn.inputStream.bufferedReader().useLines { lines ->
                    for (line in lines) {
                        if (!line.startsWith("data: ")) continue
                        val payload = line.removePrefix("data: ").trim()
                        if (payload == "[DONE]") break
                        val delta = JSONObject(payload)
                            .getJSONArray("choices")
                            .getJSONObject(0)
                            .getJSONObject("delta")
                        val piece = delta.optString("content", "")
                        if (piece.isNotEmpty()) {
                            full.append(piece)
                            onToken(piece)
                        }
                    }
                }
            } finally {
                conn.disconnect()
            }

            history.add("assistant" to full.toString())
            full.toString()
        }

    fun reset() = history.clear()
}
