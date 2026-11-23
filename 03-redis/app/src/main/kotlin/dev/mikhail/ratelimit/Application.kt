package dev.mikhail.ratelimit

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule
import io.koraframework.json.common.JsonModule
import io.koraframework.logging.logback.LogbackModule
import io.koraframework.micrometer.module.MetricsModule
import io.koraframework.resilient.ResilientModule
import io.koraframework.resilient.distributed.LettuceDistributedResilientModule

@KoraApp
interface Application :
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowPublicHttpServerModule,
    MetricsModule,
    ResilientModule,
    LettuceDistributedResilientModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
