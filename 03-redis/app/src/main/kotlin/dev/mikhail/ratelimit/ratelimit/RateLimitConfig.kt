package dev.mikhail.ratelimit.ratelimit

import io.koraframework.config.common.annotation.ConfigMapper
import io.koraframework.config.common.annotation.ConfigSource
import java.time.Duration

@ConfigSource("ratelimit")
interface RateLimitConfig {

    fun ttl(): Duration = Duration.ofSeconds(60)

    fun clients(): Map<String, ClientTierConfig>

    @ConfigMapper
    interface ClientTierConfig {
        fun rate(): Double

        fun capacity(): Long

        fun apiKey(): String
    }
}
