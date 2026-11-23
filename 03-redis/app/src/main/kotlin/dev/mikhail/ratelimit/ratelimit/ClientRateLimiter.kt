package dev.mikhail.ratelimit.ratelimit

import dev.mikhail.ratelimit.metrics.RateLimitMetrics
import io.koraframework.common.annotation.Component
import io.lettuce.core.AbstractRedisClient
import io.lettuce.core.RedisClient
import io.lettuce.core.RedisException
import io.lettuce.core.ScriptOutputType
import io.lettuce.core.api.sync.RedisScriptingCommands
import io.lettuce.core.cluster.RedisClusterClient
import io.lettuce.core.codec.StringCodec

@Component
class ClientRateLimiter(
    private val redisClient: AbstractRedisClient,
    config: RateLimitConfig,
    private val metrics: RateLimitMetrics,
) {

    private val ttlMs: Long = config.ttl().toMillis()

    @Volatile
    private var commands: RedisScriptingCommands<String, String>? = null

    fun check(key: String, rate: Double, capacity: Long, nowMs: Long): Decision {
        return metrics.measureCheck {
            try {
                val result = commands().eval(
                    LUA,
                    ScriptOutputType.MULTI,
                    arrayOf("ratelimit:client:$key"),
                    capacity.toString(),
                    rate.toString(),
                    nowMs.toString(),
                    ttlMs.toString()
                ) as List<*>
                Decision(
                    allowed = (result[0] as Number).toLong() == 1L,
                    remaining = (result[1] as Number).toLong(),
                    retryAfterMs = (result[2] as Number).toLong()
                )
            } catch (e: RedisException) {
                metrics.recordRedisError()
                Decision(allowed = true, remaining = -1, retryAfterMs = 0)
            }
        }
    }

    private fun commands(): RedisScriptingCommands<String, String> {
        commands?.let { return it }
        return synchronized(this) {
            commands ?: connect().also { commands = it }
        }
    }

    private fun connect(): RedisScriptingCommands<String, String> = when (redisClient) {
        is RedisClient -> redisClient.connect(StringCodec.UTF8).sync()
        is RedisClusterClient -> redisClient.connect(StringCodec.UTF8).sync()
        else -> throw UnsupportedOperationException(
            "Unsupported Redis client type for rate limiter: ${redisClient.javaClass.name}"
        )
    }

    private companion object {
        private val LUA = """
            local capacity, rate, now, ttl = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3]), tonumber(ARGV[4])
            local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
            local tokens, ts = tonumber(bucket[1]), tonumber(bucket[2])
            if tokens == nil then
                tokens, ts = capacity, now
            end
            tokens = math.min(capacity, tokens + math.max(0, now - ts) / 1000 * rate)
            local allowed, retryAfterMs = 0, 0
            if tokens >= 1 then
                allowed, tokens = 1, tokens - 1
            else
                retryAfterMs = math.ceil((1 - tokens) / rate * 1000)
            end
            redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
            redis.call('PEXPIRE', KEYS[1], ttl)
            return {allowed, math.floor(tokens), retryAfterMs}
        """.trimIndent()
    }
}
