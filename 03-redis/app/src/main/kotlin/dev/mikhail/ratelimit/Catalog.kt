package dev.mikhail.ratelimit

import io.koraframework.common.annotation.Component

@Component
open class Catalog {

    private val courses: List<Course> = (1..100).map { id ->
        val subject = SUBJECTS[(id - 1) % SUBJECTS.size]
        Course(id.toLong(), "$subject Course $id", id % 25 + 5)
    }

    open fun findAll(): List<Course> = courses

    open fun findById(id: Long): Course? = courses.firstOrNull { it.id == id }

    open fun search(query: String?): List<Course> =
        if (query.isNullOrBlank()) courses
        else courses.filter { it.title.contains(query, ignoreCase = true) }

    private companion object {
        private val SUBJECTS = listOf("Kotlin", "Java", "Go", "Python", "Rust", "Scala")
    }
}
