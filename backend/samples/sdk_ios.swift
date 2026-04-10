// iOS Swift example for OTP request + verify.
import Foundation

struct OTPClient {
    let baseURL = URL(string: "http://127.0.0.1:8000/api/v1")!

    func requestOTP(phone: String, email: String) async throws -> Data {
        let url = baseURL.appendingPathComponent("otp/request")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload: [String: Any] = [
            "phone": phone,
            "email": email,
            "locale": "en",
            "preferred_channel": "sms",
            "template_key": "default_otp"
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
        return data
    }

    func verifyOTP(sessionId: String, code: String) async throws -> Data {
        let url = baseURL.appendingPathComponent("otp/verify")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload: [String: Any] = [
            "session_id": sessionId,
            "code": code
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
        return data
    }
}
