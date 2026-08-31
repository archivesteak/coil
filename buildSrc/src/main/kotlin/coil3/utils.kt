package coil3

import kotlin.math.pow
import org.gradle.api.Project
import org.gradle.api.Task
import org.gradle.api.publish.maven.tasks.PublishToMavenRepository
import org.gradle.plugins.signing.Sign

val publicModules = setOf(
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
    "coil-svg",
    "coil-video",
    "coil-test",
)

/** The complete public dependency closure carried by this fork. */
val forkClosureModules = setOf(
    "coil",
    "coil-core",
    "coil-compose",
    "coil-compose-core",
    "coil-network-core",
    "coil-network-ktor3",
)

const val localPublicationOwnerProperty = "coil.localPublication.owner"

val localPublicationTaskPathsByOwner: Map<String, Set<String>> = mapOf(
    "windows" to publicationTaskPaths(
        modules = forkClosureModules,
        publications = setOf("KotlinMultiplatform", "Jvm", "MingwX64"),
    ),
    "apple" to publicationTaskPaths(
        modules = forkClosureModules,
        publications = setOf(
            "KotlinMultiplatform",
            "IosArm64",
            "IosSimulatorArm64",
            "MacosArm64",
        ),
    ),
    "web" to buildSet {
        addAll(
            publicationTaskPaths(
                modules = forkClosureModules,
                publications = setOf("KotlinMultiplatform", "Android", "Js", "WasmJs"),
            ),
        )
        addAll(
            publicationTaskPaths(
                modules = forkClosureModules - setOf("coil-compose", "coil-compose-core"),
                publications = setOf("LinuxArm64", "LinuxX64"),
            ),
        )
    },
)

private fun publicationTaskPaths(
    modules: Set<String>,
    publications: Set<String>,
): Set<String> = modules.flatMapTo(sortedSetOf()) { module ->
    publications.map { publication ->
        ":$module:publish${publication}PublicationToMavenLocal"
    }
}

const val remotePublicationProperty = "coil.remotePublication.enabled"

fun Task.isRemotePublicationTask(): Boolean {
    if (this is PublishToMavenRepository || this is Sign) return true

    val taskName = name.lowercase()
    return "mavencentral" in taskName ||
        "sonatype" in taskName ||
        taskName == "uploadarchives" ||
        (
            "upload" in taskName &&
                ("publication" in taskName || "repository" in taskName)
        ) ||
        (
            ("close" in taskName || "release" in taskName || "drop" in taskName) &&
                ("repository" in taskName || "staging" in taskName)
        )
}

val Project.minSdk: Int
    get() = intProperty("minSdk")

val Project.targetSdk: Int
    get() = intProperty("targetSdk")

val Project.compileSdk: Int
    get() = intProperty("compileSdk")

val Project.groupId: String
    get() = stringProperty("GROUP")

val Project.versionName: String
    get() = stringProperty("VERSION_NAME")

val Project.versionCode: Int
    get() = versionName
        .takeWhile { it.isDigit() || it == '.' }
        .split('.')
        .map { it.toInt() }
        .reversed()
        .sumByIndexed { index, unit ->
            // 1.2.3 -> 102030
            (unit * 10.0.pow(2 * index + 1)).toInt()
        }

// ./gradlew coil-compose:assemble -PenableComposeMetrics=true
val Project.enableComposeMetrics: Boolean
    get() = booleanProperty("enableComposeMetrics") { false }

private fun Project.intProperty(
    name: String,
    default: () -> Int = { error("unknown property: $name") },
): Int = (properties[name] as String?)?.toInt() ?: default()

private fun Project.stringProperty(
    name: String,
    default: () -> String = { error("unknown property: $name") },
): String = (properties[name] as String?) ?: default()

private fun Project.booleanProperty(
    name: String,
    default: () -> Boolean = { error("unknown property: $name") },
): Boolean = (properties[name] as String?)?.toBooleanStrict() ?: default()

private inline fun <T> List<T>.sumByIndexed(selector: (Int, T) -> Int): Int {
    var index = 0
    var sum = 0
    for (element in this) {
        sum += selector(index++, element)
    }
    return sum
}
