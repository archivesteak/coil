pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

val explicitForkRepositoryPath = System.getProperty("maven.repo.local")
    ?.trim()
    ?.takeIf(String::isNotEmpty)
    ?: error(
        "This build requires an explicit isolated fork repository. " +
            "Pass -Dmaven.repo.local=<absolute repository path>; " +
            "ambient ~/.m2 resolution is disabled.",
    )
val suppliedForkRepository = java.io.File(explicitForkRepositoryPath)
check(suppliedForkRepository.isAbsolute) {
    "The isolated fork repository path must be absolute: $explicitForkRepositoryPath"
}
val explicitForkRepository = suppliedForkRepository.canonicalFile
val ambientMavenDirectory = file(System.getProperty("user.home"))
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

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        exclusiveContent {
            forRepository {
                maven {
                    name = "isolatedForkRepository"
                    url = uri(explicitForkRepository)
                }
            }
            filter {
                includeGroupByRegex("io\\.github\\.archivesteak(\\..*)?")
            }
        }
        mavenCentral()
    }
}

rootProject.name = "coil-root"

// https://docs.gradle.org/7.4/userguide/declaring_dependencies.html#sec:type-safe-project-accessors
enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")

// Public modules
include(
    "coil",
    "coil-core",
    "coil-compose",
    "coil-compose-core",
    "coil-network-core",
    "coil-network-ktor2",
    "coil-network-ktor3",
    "coil-network-okhttp",
    "coil-network-cache-control",
    "coil-gif",
    "coil-lint",
    "coil-svg",
    "coil-video",
    "coil-bom",
    "coil-test",
)

// Private modules
include(
    "internal:benchmark",
    "internal:test-compose-screenshot",
    "internal:test-compose-ui-multiplatform",
    "internal:test-paparazzi",
    "internal:test-roborazzi",
    "internal:test-utils",
    "samples:compose",
    "samples:compose-android",
    "samples:shared",
    "samples:view",
)
