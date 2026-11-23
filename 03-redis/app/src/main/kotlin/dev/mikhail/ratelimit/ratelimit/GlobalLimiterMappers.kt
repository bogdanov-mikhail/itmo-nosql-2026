package dev.mikhail.ratelimit.ratelimit

import io.koraframework.common.annotation.Component
import io.koraframework.common.annotation.Tag
import io.koraframework.http.common.header.HttpHeaders
import io.koraframework.http.server.common.HttpServer
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor
import io.koraframework.http.server.common.request.HttpServerRequest
import io.koraframework.http.server.common.response.HttpServerResponse
import io.koraframework.http.server.common.response.HttpServerResponseException
import io.koraframework.resilient.ratelimiter.exception.RateLimitExceededException
import io.lettuce.core.RedisException

@Tag(HttpServer::class)
@Component
class GlobalLimiterMappers : HttpServerInterceptor {

    override fun intercept(
        request: HttpServerRequest,
        chain: HttpServerInterceptor.InterceptChain
    ): HttpServerResponse {
        return try {
            chain.process(request)
        } catch (e: HttpServerResponseException) {
            e
        } catch (e: RateLimitExceededException) {
            HttpServerResponseException.of(
                e,
                429,
                "Global rate limit exceeded",
                HttpHeaders.of("X-Rate-Limit-Reason", "platform")
            )
        } catch (e: RedisException) {
            HttpServerResponseException.of(e, 503, "Service unavailable: rate limit state backend unreachable")
        }
    }
}
