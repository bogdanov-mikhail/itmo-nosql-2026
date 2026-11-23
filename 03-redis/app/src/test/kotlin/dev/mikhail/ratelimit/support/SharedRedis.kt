package dev.mikhail.ratelimit.support

import org.testcontainers.containers.GenericContainer
import org.testcontainers.containers.wait.strategy.Wait
import org.testcontainers.containers.wait.strategy.WaitAllStrategy
import org.testcontainers.utility.DockerImageName
import java.time.Duration

/**
 * Один Redis-контейнер на тестовую JVM: классы, которые не останавливают Redis,
 * делят его (у каждого свой API-ключ => бакеты не пересекаются).
 * Классам с redis.stop() нужен собственный контейнер.
 */
object SharedRedis {

    @JvmField
    val container: GenericContainer<*> =
        GenericContainer<Nothing>(DockerImageName.parse("redis:8-alpine")).apply {
            withExposedPorts(6379)
            waitingFor(
                WaitAllStrategy()
                    .withStrategy(Wait.forLogMessage(".*Ready to accept connections.*", 1))
                    .withStrategy(Wait.forListeningPort())
            )
            withStartupTimeout(Duration.ofSeconds(60))
        }

    val url: String
        get() = "redis://${container.host}:${container.firstMappedPort}"

    init {
        container.start()
    }
}
