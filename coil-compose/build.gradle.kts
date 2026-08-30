import coil3.addAllMultiplatformTargets
import coil3.multiplatformAndroidLibrary

plugins {
    id("com.android.kotlin.multiplatform.library")
    id("kotlin-multiplatform")
    id("org.jetbrains.kotlinx.atomicfu")
    id("io.github.archivesteak.compose")
    id("org.jetbrains.kotlin.plugin.compose")
}

addAllMultiplatformTargets(
    libs.versions.skiko,
    skikoRuntimeDependency = libs.skiko,
    enableNativeLinux = false,
    enableNativeMingw = true,
)
multiplatformAndroidLibrary(name = "coil3.compose.singleton")

kotlin {
    sourceSets {
        commonMain {
            dependencies {
                api(projects.coil)
                api(projects.coilComposeCore)
            }
        }
    }
}
