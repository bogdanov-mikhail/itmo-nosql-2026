package dev.mikhail.ratelimit.metrics

import dev.mikhail.ratelimit.Application
import dev.mikhail.ratelimit.support.SharedRedis
import io.koraframework.http.server.common.HttpServer
import io.koraframework.test.extension.junit5.KoraAppTest
import io.koraframework.test.extension.junit5.KoraAppTestConfigModifier
import io.koraframework.test.extension.junit5.KoraConfigModification
import io.koraframework.test.extension.junit5.TestComponent
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestInstance
import java.net.URI
import dev.mikhail.ratelimit.support.TestHttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class MetricsTest : KoraAppTestConfigModifier {

    @TestComponent
    lateinit var httpServer: HttpServer

    @TestComponent
    @io.koraframework.common.annotation.Tag(io.koraframework.http.server.common.system.SystemApi::class)
    lateinit var systemHttpServer: HttpServer

    private val httpClient = TestHttpClient.create()

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("HTTP_PORT", "0")
            .withSystemProperty("SYSTEM_PORT", "0")
            .withSystemProperty("REDIS_URL", SharedRedis.url)
            .withSystemProperty("API_KEY_FREE", "metrics-free-key")

    @Test
    fun testMetricsExposeRateLimitSeries() {
        repeat(2) { attempt ->
            val response = get("/courses")
            assertEquals(200, response.statusCode(), "request $attempt: ${response.body()}")
        }

        val metrics = getMetrics()

        assertTrue(metrics.contains("ratelimit_decisions_total"), "missing ratelimit_decisions_total")
        assertTrue(metrics.contains("ratelimit_check_duration"), "missing ratelimit_check_duration")
        assertTrue(metrics.contains("ratelimit_redis_errors_total"), "missing ratelimit_redis_errors_total")
        // Ряд фреймворка, но это единственное доказательство, что наш флаг
        // resilient.telemetry.rateLimiter.metrics.enabled реально применился.
        assertTrue(metrics.contains("resilient_ratelimiter_acquire"), "missing resilient_ratelimiter_acquire")
        assertTrue(
            metrics.contains("ratelimit_decisions_total{") && metrics.contains("tier="),
            "decisions counter must carry tier tag"
        )
        assertTrue(
            metrics.contains("result=\"allowed\""),
            "decisions counter must carry result tag"
        )
    }

    @Test
    fun testHttpServerDurationIsSane() {
        // Kora RC2 читает Undertow requestStartTime, который Undertow пишет только
        // при RECORD_REQUEST_START_TIME=true. Без нашего UndertowRequestTimeConfigurer
        // «длительность» равна System.nanoTime() наблюдателя (десятки тысяч секунд).
        val first = get("/courses")
        assertEquals(200, first.statusCode(), first.body())
        val second = get("/courses")
        assertEquals(200, second.statusCode(), second.body())

        val metrics = getMetrics()
        val count = metrics.lineTotal("http_server_request_duration_seconds_count")
        val sum = metrics.lineTotal("http_server_request_duration_seconds_sum")
        assertTrue(count > 0, "no observations recorded")
        val averageSeconds = sum / count
        assertTrue(
            averageSeconds in 0.0..1.0,
            "average request duration looks like a unit bug: $averageSeconds s"
        )
    }

    private fun String.lineTotal(name: String): Double =
        lines()
            .filter { it.startsWith(name) }
            .mapNotNull { line -> line.substringAfterLast(' ').toDoubleOrNull() }
            .sum()

    private fun get(path: String): HttpResponse<String> {
        val request = HttpRequest.newBuilder()
            .GET()
            .uri(URI.create("http://localhost:${httpServer.port()}$path"))
            .timeout(Duration.ofSeconds(10))
            .header("X-API-Key", "metrics-free-key")
            .build()
        return httpClient.send(request, HttpResponse.BodyHandlers.ofString())
    }

    private fun getMetrics(): String {
        val request = HttpRequest.newBuilder()
            .GET()
            .uri(URI.create("http://localhost:${systemHttpServer.port()}/metrics"))
            .timeout(Duration.ofSeconds(10))
            .build()
        val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
        assertEquals(200, response.statusCode(), response.body())
        return response.body()
    }
}
