package dev.mikhail.ratelimit.ratelimit

import io.koraframework.http.common.header.HttpHeaders
import io.koraframework.http.server.common.response.HttpServerResponseException
import java.nio.charset.StandardCharsets.UTF_8

class ClientRateLimitException(retryAfterMs: Long) : HttpServerResponseException(
    null,
    "Rate limit exceeded",
    429,
    "text/plain;charset=utf-8",
    UTF_8.encode("Rate limit exceeded"),
    HttpHeaders.of(
        "X-Rate-Limit-Reason", "client",
        "Retry-After", (((retryAfterMs.coerceAtLeast(0)) + 999) / 1000).toString()
    )
) {
    companion object {
        fun of(decision: Decision): ClientRateLimitException = ClientRateLimitException(decision.retryAfterMs)
    }
}
