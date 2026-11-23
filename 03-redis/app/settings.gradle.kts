pluginManagement {
    repositories {
        maven("https://maven-central.storage-download.googleapis.com/maven2")
        gradlePluginPortal()
        mavenCentral()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "rate-limit-api"
