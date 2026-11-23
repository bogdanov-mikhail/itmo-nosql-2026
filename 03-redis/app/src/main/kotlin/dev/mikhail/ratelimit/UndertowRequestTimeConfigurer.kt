package dev.mikhail.ratelimit

import io.koraframework.common.Configurer
import io.koraframework.common.annotation.Component
import io.undertow.Undertow
import io.undertow.UndertowOptions

// Undertow пишет exchange.requestStartTime только при RECORD_REQUEST_START_TIME=true,
// а Kora RC2 читает его в таймере http.server.request.duration: без этой опции
// «длительность» равна System.nanoTime() наблюдателя (десятки тысяч секунд).
// Untagged-компонент матчит публичный сервер; system-серверу (@SystemApi) конфигуратор не дан —
// его метрики запросов на дашборде не используются.
@Component
class UndertowRequestTimeConfigurer : Configurer<Undertow.Builder> {

    override fun configure(builder: Undertow.Builder): Undertow.Builder =
        builder.setServerOption(UndertowOptions.RECORD_REQUEST_START_TIME, true)
}
