package dev.mikhail.ratelimit.ratelimit

import io.koraframework.common.annotation.Component

@Component
class ClientRegistry(config: RateLimitConfig) {

    data class ClientTier(val name: String, val rate: Double, val capacity: Long)

    private val tiersByApiKey: Map<String, ClientTier> = config.clients().entries.associate { (name, tier) ->
        require(tier.rate() > 0.0) { "ratelimit.clients.$name.rate must be > 0" }
        require(tier.capacity() >= 1) { "ratelimit.clients.$name.capacity must be >= 1" }
        tier.apiKey() to ClientTier(name, tier.rate(), tier.capacity())
    }

    fun resolve(apiKey: String): ClientTier? = tiersByApiKey[apiKey]
}
