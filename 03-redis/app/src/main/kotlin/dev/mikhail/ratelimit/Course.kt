package dev.mikhail.ratelimit

import io.koraframework.json.common.annotation.Json

@Json
data class Course(
    val id: Long,
    val title: String,
    val seats: Int
)
