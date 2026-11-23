import org.gradle.jvm.toolchain.JavaLanguageVersion

plugins {
    application
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

repositories {
    maven("https://maven-central.storage-download.googleapis.com/maven2")
    mavenCentral()
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))

    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:http-server-undertow")
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:logging-logback")
    implementation("io.koraframework:micrometer-module")
    implementation("io.koraframework:resilient-kora")
    implementation("io.koraframework:resilient-kora-distributed-redis-lettuce")

    testImplementation(platform("org.junit:junit-bom:${property("junitVersion")}"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("io.koraframework:test-junit5")
    testImplementation("org.testcontainers:junit-jupiter:1.21.4")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
    }
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
    sourceSets.test { kotlin.srcDir("build/generated/ksp/test/kotlin") }
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
    }
}

application {
    applicationName = "rate-limit-api"
    mainClass.set("dev.mikhail.ratelimit.ApplicationKt")
    applicationDefaultJvmArgs = listOf("-Dfile.encoding=UTF-8")
}

tasks.test {
    useJUnitPlatform()
}
