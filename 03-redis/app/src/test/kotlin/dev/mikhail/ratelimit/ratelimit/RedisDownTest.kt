package dev.mikhail.ratelimit.ratelimit

import dev.mikhail.ratelimit.Application
import io.koraframework.http.server.common.HttpServer
import io.koraframework.test.extension.junit5.KoraAppTest
import io.koraframework.test.extension.junit5.KoraAppTestConfigModifier
import io.koraframework.test.extension.junit5.KoraConfigModification
import io.koraframework.test.extension.junit5.TestComponent
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestInstance
import org.testcontainers.containers.GenericContainer
import org.testcontainers.containers.wait.strategy.Wait
import org.testcontainers.containers.wait.strategy.WaitAllStrategy
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.utility.DockerImageName
import java.net.URI
import dev.mikhail.ratelimit.support.TestHttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

/**
 * Единый негативный тест «Redis недоступен» (раньше был дублем в двух классах):
 * per-client fail-open пропускает запрос, глобальная квота fail-closed отвечает 503,
 * ошибка учтена в ratelimit_redis_errors_total. Контейнер собственный: тест его останавливает.
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class RedisDownTest : KoraAppTestConfigModifier {

    companion object {
        @Container
        @JvmStatic
        val redis: GenericContainer<*> = GenericContainer<Nothing>(DockerImageName.parse("redis:8-alpine"))
            .apply {
                withExposedPorts(6379)
                waitingFor(
                    WaitAllStrategy()
                        .withStrategy(Wait.forLogMessage(".*Ready to accept connections.*", 1))
                        .withStrategy(Wait.forListeningPort())
                )
                withStartupTimeout(Duration.ofSeconds(60))
            }
    }

    @TestComponent
    lateinit var httpServer: HttpServer

    @TestComponent
    @io.koraframework.common.annotation.Tag(io.koraframework.http.server.common.system.SystemApi::class)
    lateinit var systemHttpServer: HttpServer

    private val httpClient = TestHttpClient.create()

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("HTTP_PORT", "0")
            .withSystemProperty("SYSTEM_PORT", "0")
            .withSystemProperty("REDIS_URL", "redis://${redis.host}:${redis.firstMappedPort}")
            .withSystemProperty("API_KEY_FREE", "redis-down-free-key")

    @Test
    fun testFailOpenOnRedisDown() {
        val before = get("/courses", port = httpServer.port())
        assertEquals(200, before.statusCode(), before.body())

        redis.stop()

        val statuses = (1..5).map { get("/courses", port = httpServer.port()).statusCode() }
        assertEquals(listOf(503, 503, 503, 503, 503), statuses)

        val errors = readMetric("ratelimit_redis_errors_total")
        assertTrue(errors >= 1.0, "ratelimit_redis_errors_total=$errors, ожидалось >= 1.0")
    }

    private fun readMetric(name: String): Double {
        val body = get("/metrics", port = systemHttpServer.port(), apiKey = false).body()
        return body.lines()
            .filter { it.startsWith(name) }
            .mapNotNull { it.substringAfterLast(' ').toDoubleOrNull() }
            .sum()
    }

    private fun get(path: String, port: Int, apiKey: Boolean = true): HttpResponse<String> {
        val builder = HttpRequest.newBuilder()
            .GET()
            .uri(URI.create("http://localhost:$port$path"))
            .timeout(Duration.ofSeconds(10))
        if (apiKey) {
            builder.header("X-API-Key", "redis-down-free-key")
        }
        return httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString())
    }
}
