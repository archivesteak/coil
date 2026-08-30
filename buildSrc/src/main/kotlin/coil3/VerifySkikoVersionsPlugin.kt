package coil3

import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.artifacts.component.ModuleComponentSelector
import org.gradle.api.artifacts.result.ResolvedDependencyResult
import org.gradle.api.publish.PublishingExtension

class VerifySkikoVersionsPlugin : Plugin<Project> {

    override fun apply(target: Project) {
        val verifyVersions = target.tasks.register(
            "verifySkikoVersionsMatch",
            VerifySkikoVersionsTask::class.java,
        ) {
            group = "verification"
            description = "Ensures Skiko versions in coil-core and coil-compose-core match."

            val coreRequested = target.provider {
                requestedSkikoVersionFromJvmByOrigin(
                    targetProject = target.project(":coil-core"),
                    originGroupPrefix = target.group.toString(),
                )
            }
            val composeRequested = target.provider {
                requestedSkikoVersionFromJvmByOrigin(
                    targetProject = target.project(":coil-compose-core"),
                    originGroupPrefix = "io.github.archivesteak.compose",
                )
            }
            coreRequestedSkikoVersion.set(coreRequested)
            composeRequestedSkikoVersion.set(composeRequested)
        }

        val verifyRuntimeVariants = target.tasks.register("verifySkikoRuntimeVariants") {
            group = "verification"
            description = "Verifies fork Skiko JS/Wasm runtime variants in the MinGW module closure."
        }

        val verifyPublicationFreeze = target.tasks.register(
            "verifyPublicationFreeze",
            VerifyPublicationFreezeTask::class.java,
        ) {
            group = "verification"
            description = "Ensures this fork cannot publish to a remote Maven repository or sign."
            remotePublicationEnabled.set(
                target.providers.gradleProperty(remotePublicationProperty)
                    .map { value -> value.toBooleanStrict() }
                    .orElse(false),
            )
            enabledRemoteTaskPaths.set(
                target.provider {
                    target.allprojects.flatMap { project ->
                        project.tasks
                            .filter { task -> task.enabled && task.isRemotePublicationTask() }
                            .map { task -> task.path }
                    }.sorted()
                },
            )
            remotePublishingRepositories.set(
                target.provider {
                    target.allprojects.flatMap { project ->
                        project.extensions.findByType(PublishingExtension::class.java)
                            ?.repositories
                            ?.map { repository -> "${project.path}:${repository.name}" }
                            .orEmpty()
                    }.sorted()
                },
            )
        }

        // Attach verification only to the root `check` task.
        target.tasks.matching { it.name == "check" }.configureEach {
            dependsOn(verifyVersions, verifyRuntimeVariants, verifyPublicationFreeze)
        }
    }

    private fun requestedSkikoVersionFromJvmByOrigin(
        targetProject: Project,
        originGroupPrefix: String,
    ): String {
        val configurationNames = listOf("jvmRuntimeClasspath", "jvmTestRuntimeClasspath")
        for (name in configurationNames) {
            val cfg = targetProject.configurations.findByName(name) ?: continue

            // Force dependency graph calculation.
            cfg.dependencies

            val result = cfg.incoming.resolutionResult
            for (dep in result.allDependencies) {
                val resolved = dep as? ResolvedDependencyResult ?: continue
                val fromId = resolved.from.moduleVersion
                val requested = resolved.requested as? ModuleComponentSelector ?: continue
                if (
                    fromId != null &&
                    fromId.group.startsWith(originGroupPrefix) &&
                    requested.group == "io.github.archivesteak.skiko"
                ) {
                    return requested.version
                }
            }
        }
        error(
            "Couldn't find requested Skiko JVM dependency in ${targetProject.path} from " +
                "'$originGroupPrefix' (checked ${configurationNames.joinToString()}).",
        )
    }
}
