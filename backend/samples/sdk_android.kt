// Android Kotlin example for OTP request + verify.
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

private val client = OkHttpClient()
private const val API_BASE = "http://10.0.2.2:8000/api/v1"
private val jsonType = "application/json".toMediaType()

fun requestOtp(phone: String, email: String): String {
    val payload = """
        {
          "phone": "$phone",
          "email": "$email",
          "locale": "en",
          "preferred_channel": "sms",
          "template_key": "default_otp"
        }
    """.trimIndent()

    val req = Request.Builder()
        .url("$API_BASE/otp/request")
        .post(payload.toRequestBody(jsonType))
        .build()

    client.newCall(req).execute().use { resp ->
        if (!resp.isSuccessful) throw IllegalStateException("requestOtp failed: ${resp.code}")
        return resp.body?.string().orEmpty()
    }
}

fun verifyOtp(sessionId: String, code: String): String {
    val payload = """
        {
          "session_id": "$sessionId",
          "code": "$code"
        }
    """.trimIndent()

    val req = Request.Builder()
        .url("$API_BASE/otp/verify")
        .post(payload.toRequestBody(jsonType))
        .build()

    client.newCall(req).execute().use { resp ->
        if (!resp.isSuccessful) throw IllegalStateException("verifyOtp failed: ${resp.code}")
        return resp.body?.string().orEmpty()
    }
}
