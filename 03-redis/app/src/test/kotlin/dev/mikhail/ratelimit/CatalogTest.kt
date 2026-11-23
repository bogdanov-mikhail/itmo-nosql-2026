package dev.mikhail.ratelimit

import io.koraframework.http.server.common.response.HttpServerResponseException
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * Каталог и контроллер — чистые функции без DI/HTTP; HTTP-контракт (200 + JSON-тело)
 * доказан в LimiterInterceptorTest, отдельно поднимать граф и Redis здесь не для чего.
 */
class CatalogTest {

    private val controller = CourseController(Catalog())

    @Test
    fun testListCoursesReturnsFullCatalog() {
        val courses = controller.listCourses()

        assertEquals(100, courses.size)
        assertEquals(Course(1, "Kotlin Course 1", 6), courses.first())
        assertEquals(Course(100, "Python Course 100", 5), courses.last())
    }

    @Test
    fun testMissingCourse404() {
        val exception = assertThrows(HttpServerResponseException::class.java) {
            controller.getCourse(999999)
        }

        assertEquals(404, exception.code())
        assertTrue(exception.message!!.contains("999999"), exception.message!!)
    }

    @Test
    fun testSearchFilter() {
        val kotlinCourses = controller.searchCourses("kotlin")
        assertTrue(kotlinCourses.isNotEmpty())
        assertTrue(
            kotlinCourses.all { it.title.contains("kotlin", ignoreCase = true) },
            kotlinCourses.toString()
        )

        val single = controller.searchCourses("100")
        assertEquals(listOf(Course(100, "Python Course 100", 5)), single)

        assertEquals(100, controller.searchCourses(null).size)
        assertEquals(100, controller.searchCourses("").size)
    }
}
