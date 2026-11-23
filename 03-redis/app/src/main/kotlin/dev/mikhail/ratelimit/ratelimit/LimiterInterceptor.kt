package dev.mikhail.ratelimit.ratelimit

import dev.mikhail.ratelimit.metrics.RateLimitMetrics
import io.koraframework.common.annotation.Component
import io.koraframework.common.annotation.Tag
import io.koraframework.http.server.common.HttpServer
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor
import io.koraframework.http.server.common.request.HttpServerRequest
import io.koraframework.http.server.common.response.HttpServerResponse
import io.koraframework.http.server.common.response.HttpServerResponseException

@Tag(HttpServer::class)
@Component
class LimiterInterceptor(
    private val registry: ClientRegistry,
    private val limiter: ClientRateLimiter,
    private val metrics: RateLimitMetrics,
) : HttpServerInterceptor {

    override fun intercept(
        request: HttpServerRequest,
        chain: HttpServerInterceptor.InterceptChain
    ): HttpServerResponse {
        val apiKey = request.headers().getFirst(API_KEY_HEADER)
            ?: return HttpServerResponseException.of(401, "Missing API key")
        val tier = registry.resolve(apiKey)
            ?: return HttpServerResponseException.of(401, "Unknown API key")
        val decision = limiter.check(apiKey, tier.rate, tier.capacity, System.currentTimeMillis())
        metrics.recordDecision(tier.name, decision.allowed)
        if (!decision.allowed) {
            throw ClientRateLimitException.of(decision)
        }
        return chain.process(request)
    }

    private companion object {
        private const val API_KEY_HEADER = "X-API-Key"
    }
}
