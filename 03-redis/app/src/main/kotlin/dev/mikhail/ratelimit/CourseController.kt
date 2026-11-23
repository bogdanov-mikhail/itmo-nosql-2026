package dev.mikhail.ratelimit

import io.koraframework.common.annotation.Component
import io.koraframework.http.common.HttpMethod
import io.koraframework.http.common.annotation.HttpRoute
import io.koraframework.http.common.annotation.Path
import io.koraframework.http.common.annotation.Query
import io.koraframework.http.server.common.annotation.HttpController
import io.koraframework.http.server.common.response.HttpServerResponseException
import io.koraframework.json.common.annotation.Json
import dev.mikhail.ratelimit.ratelimit.GlobalApiLimiter
import io.koraframework.resilient.ratelimiter.annotation.RateLimited

@Component
@HttpController
open class CourseController(private val catalog: Catalog) {

    @HttpRoute(method = HttpMethod.GET, path = "/courses")
    @Json
    @RateLimited(GlobalApiLimiter::class)
    open fun listCourses(): List<Course> = catalog.findAll()

    @HttpRoute(method = HttpMethod.GET, path = "/courses/{id}")
    @Json
    @RateLimited(GlobalApiLimiter::class)
    open fun getCourse(@Path id: Long): Course =
        catalog.findById(id) ?: throw HttpServerResponseException.of(404, "Course not found: $id")

    @HttpRoute(method = HttpMethod.GET, path = "/courses/search")
    @Json
    @RateLimited(GlobalApiLimiter::class)
    open fun searchCourses(@Query("q") q: String?): List<Course> = catalog.search(q)
}
