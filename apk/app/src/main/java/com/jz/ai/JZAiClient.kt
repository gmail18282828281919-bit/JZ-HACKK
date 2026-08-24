package com.jz.ai

import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/** Fichier choisi par l'utilisateur, pas encore envoye au serveur. */
data class Attachment(
    val filename: String,
    val bytes: ByteArray,
    val mime: String,
) {
    // ByteArray n'a pas d'equals structurel : on compare sur l'identite du fichier.
    override fun equals(other: Any?) =
        other is Attachment && other.filename == filename && other.bytes.contentEquals(bytes)

    override fun hashCode() = 31 * filename.hashCode() + bytes.contentHashCode()
}

/** Erreur remontee par le serveur JZ-AI, avec un message lisible par l'utilisateur. */
class JZAiException(message: String) : Exception(message)

/**
 * Client HTTP du serveur JZ-AI (API compatible OpenAI).
 *
 * Les fichiers sont d'abord televerses via /v1/files : l'historique ne garde
 * ensuite que leur identifiant, au lieu de renvoyer le base64 a chaque tour.
 */
class JZAiClient(
    private var baseUrl: String,
    private var apiKey: String,
    private val model: String = "jz-mini-1",
) {

    /** content vaut soit une String, soit un JSONArray de blocs. */
    private class Turn(val role: String, val content: Any)

    private val history = mutableListOf<Turn>()

    fun configure(baseUrl: String, apiKey: String) {
        this.baseUrl = baseUrl.trim().trimEnd('/')
        this.apiKey = apiKey.trim()
    }

    fun reset() = history.clear()

    // ---------------------------- reseau ----------------------------
    private fun open(path: String, method: String, accept: String): HttpURLConnection =
        (URL("$baseUrl$path").openConnection() as HttpURLConnection).apply {
            requestMethod = method
            doOutput = method == "POST"
            connectTimeout = 15_000
            readTimeout = 180_000
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", accept)
            setRequestProperty("Authorization", "Bearer $apiKey")
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
            raw.take(300)
        }
        val code = try { conn.responseCode } catch (_: Exception) { -1 }
        return JZAiException(
            when (code) {
                400 -> detail.ifBlank { "Requete refusee par le serveur." }
                401 -> "Cle d'API refusee. Verifie la cle dans les reglages."
                403 -> "Acces interdit."
                404 -> "Route introuvable : l'URL du serveur est-elle correcte ?"
                413 -> "Fichier trop volumineux pour le serveur."
                429 -> "Trop de requetes, patiente un instant."
                else -> "Erreur serveur $code${if (detail.isBlank()) "" else " : $detail"}"
            }
        )
    }

    /**
     * Televerse un fichier et renvoie son file_id.
     * Le serveur en extrait le texte (PDF, DOCX, code…) ou le garde en image.
     */
    suspend fun upload(attachment: Attachment): String = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("filename", attachment.filename)
            .put("mime", attachment.mime)
            .put("content_base64", Base64.encodeToString(attachment.bytes, Base64.NO_WRAP))
            .toString()

        val conn = open("/v1/files", "POST", "application/json")
        try {
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            if (conn.responseCode !in 200..299) throw failure(conn)
            val response = conn.inputStream.bufferedReader().use(BufferedReader::readText)
            JSONObject(response).getString("id")
        } finally {
            conn.disconnect()
        }
    }

    private fun payload(stream: Boolean): String {
        val messages = JSONArray()
        history.forEach { turn ->
            messages.put(JSONObject().put("role", turn.role).put("content", turn.content))
        }
        return JSONObject()
            .put("model", model)
            .put("messages", messages)
            .put("temperature", 0.7)
            .put("max_tokens", 512)
            .put("stream", stream)
            .toString()
    }

    /** Construit le tour utilisateur : texte seul, ou blocs texte + fichiers. */
    private fun userTurn(prompt: String, fileIds: List<String>): Turn {
        if (fileIds.isEmpty()) return Turn("user", prompt)
        val blocks = JSONArray()
        blocks.put(JSONObject().put("type", "text").put("text", prompt))
        fileIds.forEach {
            blocks.put(JSONObject().put("type", "file").put("file_id", it))
        }
        return Turn("user", blocks)
    }

    /**
     * Envoie [prompt] avec ses [fileIds] et diffuse la reponse via [onToken].
     * Les fichiers doivent avoir ete televerses au prealable avec [upload].
     */
    suspend fun askStreaming(
        prompt: String,
        fileIds: List<String> = emptyList(),
        onToken: suspend (String) -> Unit,
    ): String = withContext(Dispatchers.IO) {
        history.add(userTurn(prompt, fileIds))
        val conn = open("/v1/chat/completions", "POST", "text/event-stream")
        val full = StringBuilder()
        try {
            conn.outputStream.use { it.write(payload(stream = true).toByteArray(Charsets.UTF_8)) }
            if (conn.responseCode !in 200..299) {
                history.removeAt(history.lastIndex)   // ne pas polluer l'historique
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
                        ""   // ligne de keep-alive ou fragment non parsable
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
        history.add(Turn("assistant", full.toString()))
        full.toString()
    }

    /** Ping /health : decrit le modele et ses capacites, ou leve une JZAiException. */
    suspend fun health(): String = withContext(Dispatchers.IO) {
        val conn = (URL("$baseUrl/health").openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8_000
            readTimeout = 8_000
        }
        try {
            if (conn.responseCode !in 200..299) throw failure(conn)
            val json = JSONObject(conn.inputStream.bufferedReader().use(BufferedReader::readText))
            buildString {
                append(json.optString("model"))
                append(" (").append(json.optString("backend"))
                if (json.optBoolean("vision")) append(", vision") else append(", sans vision")
                append(")")
            }
        } finally {
            conn.disconnect()
        }
    }
}
