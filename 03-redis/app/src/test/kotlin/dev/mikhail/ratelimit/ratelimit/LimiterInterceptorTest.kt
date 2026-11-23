package dev.mikhail.ratelimit.ratelimit

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
import org.junit.jupiter.api.TestMethodOrder
import java.net.URI
import dev.mikhail.ratelimit.support.TestHttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

private const val API_KEY_HEADER = "X-API-Key"

/**
 * Глобальная квота на класс = 2 (по одному разрешённому 200 на метод), refresh 60 с.
 * Порядок методов зафиксирован: сначала testRejected429Headers (standard-ключ: 1-й токен
 * глобальной квоты), затем testClientCheckedBeforePlatform (free-ключ: 2-й токен; к его
 * probe ИСЧЕРПАНЫ оба слоя, и reason=client доказывает, что per-client проверяется раньше:
 * при обратном порядке второй запрос получил бы 200 или reason=platform).
 * testUnknownKey401 — без квоты, порядок не важен.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@TestMethodOrder(org.junit.jupiter.api.MethodOrderer.OrderAnnotation::class)
@KoraAppTest(Application::class)
class LimiterInterceptorTest : KoraAppTestConfigModifier {

    @TestComponent
    lateinit var httpServer: HttpServer

    private val httpClient = TestHttpClient.create()

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("HTTP_PORT", "0")
            .withSystemProperty("SYSTEM_PORT", "0")
            .withSystemProperty("REDIS_URL", SharedRedis.url)
            .withSystemProperty("API_KEY_FREE", "interceptor-free-key")
            .withSystemProperty("API_KEY_STANDARD", "interceptor-standard-key")
            .withSystemProperty("RATELIMIT_FREE_CAPACITY", "1")
            .withSystemProperty("RATELIMIT_FREE_RATE", "0.001")
            .withSystemProperty("RATELIMIT_STANDARD_CAPACITY", "1")
            .withSystemProperty("RATELIMIT_STANDARD_RATE", "0.001")
            .withSystemProperty("GLOBAL_LIMIT_FOR_PERIOD", "2")
            .withSystemProperty("GLOBAL_LIMIT_REFRESH_PERIOD", "60s")
            .withSystemProperty("RATELIMIT_GLOBAL_KEY_PREFIX", "test-interceptor")

    @Test
    fun testUnknownKey401() {
        val missing = get("/courses", apiKey = null)
        assertEquals(401, missing.statusCode(), missing.body())

        val unknown = get("/courses", apiKey = "not-a-known-key")
        assertEquals(401, unknown.statusCode(), unknown.body())
    }

    @Test
    @org.junit.jupiter.api.Order(1)
    fun testRejected429Headers() {
        val allowed = get("/courses", apiKey = "interceptor-standard-key")
        assertEquals(200, allowed.statusCode(), allowed.body())
        assertTrue(
            allowed.body().startsWith("""[{"id":""") && allowed.body().contains(""""title""""),
            "JSON-контракт каталога: ${allowed.body().take(80)}"
        )

        val rejected = get("/courses", apiKey = "interceptor-standard-key")

        assertEquals(429, rejected.statusCode(), rejected.body())
        assertEquals("client", rejected.headers().firstValue("X-Rate-Limit-Reason").orElse(null))
        assertEquals(
            "1000",
            rejected.headers().firstValue("Retry-After").orElse(null),
            "ceil(1 токена / 0.001 rps) = 1000 секунд"
        )
    }

    @Test
    @org.junit.jupiter.api.Order(2)
    fun testClientCheckedBeforePlatform() {
        val allowed = get("/courses", apiKey = "interceptor-free-key")
        assertEquals(200, allowed.statusCode(), allowed.body())

        val rejected = get("/courses", apiKey = "interceptor-free-key")

        assertEquals(429, rejected.statusCode(), rejected.body())
        assertEquals(
            "client",
            rejected.headers().firstValue("X-Rate-Limit-Reason").orElse(null),
            "оба слоя исчерпаны — отказ обязан нести reason клиента, а не платформы"
        )
    }

    private fun get(path: String, apiKey: String?): HttpResponse<String> {
        val builder = HttpRequest.newBuilder()
            .GET()
            .uri(URI.create("http://localhost:${httpServer.port()}$path"))
            .timeout(Duration.ofSeconds(10))
        if (apiKey != null) {
            builder.header(API_KEY_HEADER, apiKey)
        }
        return httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString())
    }
}
