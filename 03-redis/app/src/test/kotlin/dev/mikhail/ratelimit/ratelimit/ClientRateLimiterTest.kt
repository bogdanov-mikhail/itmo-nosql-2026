package dev.mikhail.ratelimit.ratelimit

import dev.mikhail.ratelimit.Application
import dev.mikhail.ratelimit.support.SharedRedis
import io.koraframework.test.extension.junit5.KoraAppTest
import io.koraframework.test.extension.junit5.KoraAppTestConfigModifier
import io.koraframework.test.extension.junit5.KoraConfigModification
import io.koraframework.test.extension.junit5.TestComponent
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestInstance
import kotlin.math.ceil

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class ClientRateLimiterTest : KoraAppTestConfigModifier {

    @TestComponent
    lateinit var limiter: ClientRateLimiter

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("REDIS_URL", SharedRedis.url)
            .withSystemProperty("RATELIMIT_TTL", "500ms")

    @Test
    fun testDrainsCapacityThenRejectsWithRetryAfter() {
        val now = 1_000_000L

        val decisions = (1..20).map { limiter.check("drains-capacity", 1.0, 20, now) }
        assertTrue(decisions.all { it.allowed }, decisions.toString())
        assertEquals(0L, decisions.last().remaining)

        val rejected = limiter.check("drains-capacity", 1.0, 20, now)

        assertFalse(rejected.allowed)
        assertEquals(0L, rejected.remaining)
        assertEquals(1000L, rejected.retryAfterMs)
    }

    @Test
    fun testRefillOverTime() {
        val now = 3_000_000L

        val first = limiter.check("refill-over-time", 2.0, 1, now)
        assertTrue(first.allowed)

        val second = limiter.check("refill-over-time", 2.0, 1, now)
        assertFalse(second.allowed)
        assertEquals(500L, second.retryAfterMs)

        val advanceMs = ceil(1000 / 2.0).toLong() + 100
        val third = limiter.check("refill-over-time", 2.0, 1, now + advanceMs)
        assertTrue(third.allowed)
        assertEquals(0L, third.remaining)
    }

    @Test
    fun testNegativeTimeSkewDoesNotPunish() {
        val t = 5_000_000L
        assertTrue(limiter.check("neg-skew", 1.0, 2, t).allowed)
        assertTrue(limiter.check("neg-skew", 1.0, 2, t).allowed)

        // часы «отступили» на 10 с: без math.max(0, now-ts) tokens ушли бы в минус
        val rejected = limiter.check("neg-skew", 1.0, 2, t - 10_000)
        assertFalse(rejected.allowed)
        assertEquals(1000L, rejected.retryAfterMs)
    }

    @Test
    fun testIdleClientResets() {
        val now = 4_000_000L
        repeat(20) { assertTrue(limiter.check("idle-client-resets", 0.001, 20, now).allowed) }
        assertFalse(limiter.check("idle-client-resets", 0.001, 20, now).allowed)

        Thread.sleep(800)

        val reset = limiter.check("idle-client-resets", 0.001, 20, now)
        assertTrue(reset.allowed)
        assertEquals(19L, reset.remaining)
    }
}
