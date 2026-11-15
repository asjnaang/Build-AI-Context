plugins {
    kotlin("jvm")
}

repositories {
    mavenCentral()
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_21)
    }
}

java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

dependencies {
    implementation(kotlin("stdlib"))
    testImplementation(kotlin("stdlib"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.4")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.processResources {
    from(rootProject.projectDir.resolve("../policy")) {
        include("policy.json")
    }
    from(rootProject.projectDir.resolve("../engine-ts")) {
        include("baic_prompt_text.md")
        include("baic_prompt_gzip.md")
    }
}

tasks.test {
    useJUnitPlatform()
    systemProperty("baic.testdata", rootProject.projectDir.resolve("../testdata").absolutePath)
    systemProperty("baic.policy", rootProject.projectDir.resolve("../policy/policy.json").absolutePath)
}
