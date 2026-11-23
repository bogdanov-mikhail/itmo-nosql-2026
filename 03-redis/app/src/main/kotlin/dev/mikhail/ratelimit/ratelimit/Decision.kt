package dev.mikhail.ratelimit.ratelimit

data class Decision(val allowed: Boolean, val remaining: Long, val retryAfterMs: Long)
