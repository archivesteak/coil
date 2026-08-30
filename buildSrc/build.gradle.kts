import java.io.File
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.tasks.KotlinJvmCompile

plugins {
    `kotlin-dsl-base`
    `java-gradle-plugin`
}

val explicitForkRepositoryPath = System.getProperty("maven.repo.local")
    ?.trim()
    ?.takeIf(String::isNotEmpty)
    ?: error(
        "This build requires an explicit isolated fork repository. " +
            "Pass -Dmaven.repo.local=<absolute repository path>; " +
            "ambient ~/.m2 resolution is disabled.",
    )
val suppliedForkRepository = File(explicitForkRepositoryPath)
check(suppliedForkRepository.isAbsolute) {
    "The isolated fork repository path must be absolute: $explicitForkRepositoryPath"
}
val explicitForkRepository = suppliedForkRepository.canonicalFile
val ambientMavenDirectory = File(System.getProperty("user.home"))
    .resolve(".m2")
    .canonicalFile
check(explicitForkRepository.isDirectory) {
    "The isolated fork repository must be an existing absolute directory: " +
        explicitForkRepository.path
}
check(!explicitForkRepository.toPath().startsWith(ambientMavenDirectory.toPath())) {
    "The isolated fork repository must not be inside the ambient Maven directory " +
        "${ambientMavenDirectory.path}: ${explicitForkRepository.path}"
}

repositories {
    google()
    maven {
        name = "isolatedForkRepository"
        url = uri(explicitForkRepository)
        content {
            includeGroupByRegex("io\\.github\\.archivesteak\\.compose(\\..*)?")
        }
    }
    mavenCentral()
}

dependencies {
    implementation(libs.gradlePlugin.android)
    implementation(libs.gradlePlugin.dokka)
    implementation(libs.gradlePlugin.jetbrainsCompose)
    implementation(libs.gradlePlugin.composeCompiler)
    implementation(libs.gradlePlugin.kotlin)
    implementation(libs.gradlePlugin.mavenPublish)
}

gradlePlugin {
    plugins {
        register("verifySkikoVersions") {
            id = "coil3.verify-skiko-versions"
            implementationClass = "coil3.VerifySkikoVersionsPlugin"
        }
    }
}

// Target JVM 17.
tasks.withType<JavaCompile>().configureEach {
    sourceCompatibility = JavaVersion.VERSION_17.toString()
    targetCompatibility = JavaVersion.VERSION_17.toString()
}
tasks.withType<KotlinJvmCompile>().configureEach {
    compilerOptions.jvmTarget = JvmTarget.JVM_17
}
