package coil3

import org.gradle.api.DefaultTask
import org.gradle.api.provider.ListProperty
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.TaskAction

abstract class VerifyPublicationFreezeTask : DefaultTask() {

    @get:Input
    abstract val forbiddenTaskPaths: ListProperty<String>

    @get:Input
    abstract val remotePublishingRepositories: ListProperty<String>

    @TaskAction
    fun verify() {
        check(forbiddenTaskPaths.get().isEmpty()) {
            "Remote Maven/signing tasks are forbidden in this fork: " +
                forbiddenTaskPaths.get().joinToString()
        }
        check(remotePublishingRepositories.get().isEmpty()) {
            "Remote Maven publishing repositories are forbidden in this fork: " +
                remotePublishingRepositories.get().joinToString()
        }
        logger.lifecycle("Verified local-only Maven publication configuration.")
    }
}
