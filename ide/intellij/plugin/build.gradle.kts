import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    kotlin("jvm")
    id("org.jetbrains.intellij.platform")
}

group = providers.gradleProperty("group").get()
version = providers.gradleProperty("version").get()

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_21)
    }
}

java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

dependencies {
    implementation(project(":engine"))
    intellijPlatform {
        val type = providers.gradleProperty("platformType")
        val version = providers.gradleProperty("platformVersion")
        create(type, version)
    }
}

intellijPlatform {
    pluginConfiguration {
        id = "com.asjnaang.buildaicontext"
        name = "Build AI Context"
        version.set(providers.gradleProperty("version"))
        description.set("Scan a project, filter files, and export AI-readable source bundles without Python.")
        ideaVersion {
            sinceBuild = providers.gradleProperty("pluginSinceBuild")
            untilBuild = provider { null }
        }
        vendor {
            name = "ASJN"
            url = "https://github.com/asjnaang/Build-AI-Context"
        }
        changeNotes.set(
            """
            <p>0.1.0 — first Host: Scan, Export, Add to AI Context, Generate Filetree / Code Graph.</p>
            """.trimIndent(),
        )
    }
    instrumentCode = false
    buildSearchableOptions = false
}
