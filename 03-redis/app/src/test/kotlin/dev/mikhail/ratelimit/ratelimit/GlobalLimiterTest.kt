package dev.mikhail.ratelimit.ratelimit

import dev.mikhail.ratelimit.Application
import dev.mikhail.ratelimit.support.SharedRedis
import io.koraframework.http.server.common.HttpServer
import io.koraframework.test.extension.junit5.KoraAppTest
import io.koraframework.test.extension.junit5.KoraAppTestConfigModifier
import io.koraframework.test.extension.junit5.KoraConfigModification
import io.koraframework.test.extension.junit5.TestComponent
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestInstance
import java.net.URI
import dev.mikhail.ratelimit.support.TestHttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

/**
 * Доказательство, что @RateLimited реально сплетён (AOP-аспект), distributed limiter
 * ходит в Redis и RateLimitExceededException маппится в 429 с reason=platform.
 * Refresh 60 с делает отказ детерминированным (пополнение ~0.05 ток/с за время теста).
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class GlobalLimiterTest : KoraAppTestConfigModifier {

    @TestComponent
    lateinit var httpServer: HttpServer

    private val httpClient = TestHttpClient.create()

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("HTTP_PORT", "0")
            .withSystemProperty("SYSTEM_PORT", "0")
            .withSystemProperty("REDIS_URL", SharedRedis.url)
            .withSystemProperty("API_KEY_FREE", "global-free-key")
            .withSystemProperty("GLOBAL_LIMIT_FOR_PERIOD", "3")
            .withSystemProperty("GLOBAL_LIMIT_REFRESH_PERIOD", "60s")
            .withSystemProperty("RATELIMIT_GLOBAL_KEY_PREFIX", "test-global")

    @Test
    fun testPlatformReject429() {
        repeat(3) { attempt ->
            val response = get("/courses")
            assertEquals(200, response.statusCode(), "request $attempt: ${response.body()}")
        }

        val rejected = get("/courses")

        assertEquals(429, rejected.statusCode(), rejected.body())
        assertEquals("platform", rejected.headers().firstValue("X-Rate-Limit-Reason").orElse(null))
    }

    private fun get(path: String): HttpResponse<String> {
        val request = HttpRequest.newBuilder()
            .GET()
            .uri(URI.create("http://localhost:${httpServer.port()}$path"))
            .timeout(Duration.ofSeconds(10))
            .header("X-API-Key", "global-free-key")
            .build()
        return httpClient.send(request, HttpResponse.BodyHandlers.ofString())
    }
}
