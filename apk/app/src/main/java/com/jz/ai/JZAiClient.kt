package com.jz.ai

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/** Un tour de conversation. */
data class ChatTurn(val role: String, val content: String)

/** Erreur remontee par le serveur JZ-AI, avec un message lisible par l'utilisateur. */
class JZAiException(message: String) : Exception(message)

/**
 * Client HTTP du serveur JZ-AI (API compatible OpenAI).
 * Toutes les fonctions suspendent et s'executent sur Dispatchers.IO.
 */
class JZAiClient(
    private var baseUrl: String,
    private var apiKey: String,
    private val model: String = "jz-mini-1",
) {

    private val history = mutableListOf<ChatTurn>()

    fun configure(baseUrl: String, apiKey: String) {
        this.baseUrl = baseUrl.trimEnd('/')
        this.apiKey = apiKey.trim()
    }

    fun history(): List<ChatTurn> = history.toList()

    fun reset() = history.clear()

    private fun open(path: String, accept: String): HttpURLConnection =
        (URL("${baseUrl.trimEnd('/')}$path").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 15_000
            readTimeout = 180_000
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", accept)
            setRequestProperty("Authorization", "Bearer $apiKey")
        }

    private fun payload(stream: Boolean): String {
        val messages = JSONArray()
        history.forEach {
            messages.put(JSONObject().put("role", it.role).put("content", it.content))
        }
        return JSONObject()
            .put("model", model)
            .put("messages", messages)
            .put("temperature", 0.7)
            .put("max_tokens", 512)
            .put("stream", stream)
            .toString()
    }

    /** Traduit les codes HTTP en messages comprehensibles. */
    private fun failure(conn: HttpURLConnection): JZAiException {
        val raw = try {
            conn.errorStream?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
        } catch (_: Exception) {
            ""
        }
        val detail = try {
            JSONObject(raw).getJSONObject("error").getString("message")
        } catch (_: Exception) {
            raw.take(200)
        }
        return JZAiException(
            when (conn.responseCode) {
                401 -> "Cle d'API refusee. Verifie la cle dans les reglages."
                403 -> "Acces interdit."
                404 -> "Route introuvable : l'URL du serveur est-elle correcte ?"
                429 -> "Trop de requetes, patiente un instant."
                else -> "Erreur serveur ${conn.responseCode}${if (detail.isBlank()) "" else " : $detail"}"
            }
        )
    }

    /** Envoie [prompt] et renvoie la reponse complete. */
    suspend fun ask(prompt: String): String = withContext(Dispatchers.IO) {
        history.add(ChatTurn("user", prompt))
        val conn = open("/v1/chat/completions", "application/json")
        try {
            conn.outputStream.use { it.write(payload(stream = false).toByteArray(Charsets.UTF_8)) }
            if (conn.responseCode !in 200..299) {
                history.removeAt(history.lastIndex)
                throw failure(conn)
            }
            val body = conn.inputStream.bufferedReader().use(BufferedReader::readText)
            val answer = JSONObject(body)
                .getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .getString("content")
            history.add(ChatTurn("assistant", answer))
            answer
        } finally {
            conn.disconnect()
        }
    }

    /** Idem, mais [onToken] est appele au fil de la generation (SSE). */
    suspend fun askStreaming(prompt: String, onToken: suspend (String) -> Unit): String =
        withContext(Dispatchers.IO) {
            history.add(ChatTurn("user", prompt))
            val conn = open("/v1/chat/completions", "text/event-stream")
            val full = StringBuilder()
            try {
                conn.outputStream.use { it.write(payload(stream = true).toByteArray(Charsets.UTF_8)) }
                if (conn.responseCode !in 200..299) {
                    history.removeAt(history.lastIndex)
                    throw failure(conn)
                }
                conn.inputStream.bufferedReader().useLines { lines ->
                    for (line in lines) {
                        if (!line.startsWith("data: ")) continue
                        val data = line.removePrefix("data: ").trim()
                        if (data == "[DONE]") break
                        val piece = try {
                            JSONObject(data)
                                .getJSONArray("choices")
                                .getJSONObject(0)
                                .optJSONObject("delta")
                                ?.optString("content", "")
                                .orEmpty()
                        } catch (_: Exception) {
                            ""  // ligne de keep-alive ou fragment non parsable : on ignore
                        }
                        if (piece.isNotEmpty()) {
                            full.append(piece)
                            onToken(piece)
                        }
                    }
                }
            } finally {
                conn.disconnect()
            }
            history.add(ChatTurn("assistant", full.toString()))
            full.toString()
        }

    /** Ping /health : renvoie le nom du backend actif, ou leve une JZAiException. */
    suspend fun health(): String = withContext(Dispatchers.IO) {
        val conn = (URL("${baseUrl.trimEnd('/')}/health").openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8_000
            readTimeout = 8_000
        }
        try {
            if (conn.responseCode !in 200..299) throw failure(conn)
            val body = conn.inputStream.bufferedReader().use(BufferedReader::readText)
            val json = JSONObject(body)
            "${json.optString("model")} (backend ${json.optString("backend")})"
        } finally {
            conn.disconnect()
        }
    }
}
