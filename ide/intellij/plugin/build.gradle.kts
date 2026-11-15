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
    pluginVerification {
        ides {
            providers.environmentVariable("ANDROID_STUDIO_HOME").orNull?.let { local(file(it)) }
        }
    }
    pluginConfiguration {
        id = "com.asjnaang.buildaicontext"
        name = "Build AI Context"
        version.set(providers.gradleProperty("version"))
        description.set(
            """
            Export files as AI-readable text bundles.
            <p>Choose files in the AI Context tool window, then Export. Cataloging is automatic. No Python required.</p>
            <p>gzip (tar-gz) is the default, matching the <code>baic</code> CLI. Export writes bundles, a manifest, and
            <code>baic_prompt.md</code>. Restore unpacks a gzip export.</p>
            <p>Works on IntelliJ IDEA, Android Studio, WebStorm, PyCharm, and other IntelliJ Platform IDEs
            (depends on <code>com.intellij.modules.platform</code> only). The plugin does not upload your code.</p>
            """.trimIndent(),
        )
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
            <p>0.1.0 — Export-first Host: catalog loads with the project, search and file-format
            filters, gzip default, Restore, Add to AI Context, Generate Filetree / Code Graph.
            Secrets require a confirm dialog.</p>
            """.trimIndent(),
        )
    }
    instrumentCode = false
    buildSearchableOptions = false
}
