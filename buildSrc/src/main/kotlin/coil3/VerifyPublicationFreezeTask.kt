package coil3

import org.gradle.api.DefaultTask
import org.gradle.api.provider.ListProperty
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.TaskAction

abstract class VerifyPublicationFreezeTask : DefaultTask() {

    @get:Input
    abstract val remotePublicationEnabled: Property<Boolean>

    @get:Input
    abstract val enabledRemoteTaskPaths: ListProperty<String>

    @get:Input
    abstract val remotePublishingRepositories: ListProperty<String>

    @TaskAction
    fun verify() {
        check(!remotePublicationEnabled.get()) {
            "Remote publication opt-in '$remotePublicationProperty' must remain false until release approval."
        }
        check(enabledRemoteTaskPaths.get().isEmpty()) {
            "Remote Maven/signing/release/upload tasks must all be disabled: " +
                enabledRemoteTaskPaths.get().joinToString()
        }
        check(remotePublishingRepositories.get().isEmpty()) {
            "Remote Maven publishing repositories are forbidden in this fork: " +
                remotePublishingRepositories.get().joinToString()
        }
        logger.lifecycle("Verified local-only Maven publication configuration.")
    }
}
