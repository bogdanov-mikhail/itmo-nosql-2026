package dev.mikhail.ratelimit.support

import java.net.Proxy
import java.net.ProxySelector
import java.net.SocketAddress
import java.net.URI
import java.net.http.HttpClient
import java.time.Duration

object TestHttpClient {

    /**
     * Работает в обход системного прокси: он перехватывает localhost-запросы
     * тестов и отвечает 407.
     */
    fun create(): HttpClient =
        HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .proxy(object : ProxySelector() {
                override fun select(uri: URI): List<Proxy> = listOf(Proxy.NO_PROXY)
                override fun connectFailed(uri: URI, sa: SocketAddress, ioe: java.io.IOException) {}
            })
            .build()
}
