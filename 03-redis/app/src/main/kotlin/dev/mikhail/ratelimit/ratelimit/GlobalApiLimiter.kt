package dev.mikhail.ratelimit.ratelimit

import io.koraframework.resilient.distributed.ratelimiter.annotation.RateLimiterDistributedSpec
import io.koraframework.resilient.ratelimiter.RateLimiter

@RateLimiterDistributedSpec("resilient.ratelimiter.global")
interface GlobalApiLimiter : RateLimiter
