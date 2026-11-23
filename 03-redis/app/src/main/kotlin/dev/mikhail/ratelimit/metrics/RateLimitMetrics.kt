package dev.mikhail.ratelimit.metrics

import io.koraframework.common.annotation.Component
import io.micrometer.core.instrument.Counter
import io.micrometer.core.instrument.MeterRegistry
import io.micrometer.core.instrument.Timer
import java.time.Duration
import java.util.concurrent.ConcurrentHashMap

@Component
class RateLimitMetrics(private val registry: MeterRegistry) {

    private val decisions = ConcurrentHashMap<Pair<String, String>, Counter>()

    private val redisErrors: Counter = Counter.builder("ratelimit.redis.errors")
        .description("Per-client limiter Redis failures (fail-open path)")
        .register(registry)

    private val checkDuration: Timer = Timer.builder("ratelimit.check.duration")
        .description("Per-client token bucket check duration")
        .serviceLevelObjectives(
            Duration.ofMillis(1), Duration.ofMillis(5), Duration.ofMillis(10),
            Duration.ofMillis(25), Duration.ofMillis(50), Duration.ofMillis(100), Duration.ofMillis(500)
        )
        .register(registry)

    fun recordDecision(tier: String, allowed: Boolean) {
        val key = tier to if (allowed) "allowed" else "rejected"
        decisions.computeIfAbsent(key) { (tierName, result) ->
            Counter.builder("ratelimit.decisions")
                .description("Per-client rate limiter decisions")
                .tag("tier", tierName)
                .tag("result", result)
                .register(registry)
        }.increment()
    }

    fun recordRedisError() {
        redisErrors.increment()
    }

    fun <T> measureCheck(block: () -> T): T {
        val started = System.nanoTime()
        try {
            return block()
        } finally {
            checkDuration.record(Duration.ofNanos(System.nanoTime() - started))
        }
    }
}
