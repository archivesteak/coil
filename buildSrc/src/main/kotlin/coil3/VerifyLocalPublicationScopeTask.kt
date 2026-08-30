package coil3

import org.gradle.api.DefaultTask
import org.gradle.api.provider.SetProperty
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.TaskAction

abstract class VerifyLocalPublicationScopeTask : DefaultTask() {

    @get:Input
    abstract val expectedTaskPaths: SetProperty<String>

    @get:Input
    abstract val enabledTaskPaths: SetProperty<String>

    @get:Input
    abstract val aggregateTaskPaths: SetProperty<String>

    @TaskAction
    fun verify() {
        val expected = expectedTaskPaths.get()
        check(enabledTaskPaths.get() == expected) {
            "Enabled local Maven publication tasks differ from the MinGW closure. " +
                "expected=${expected.sorted()}, actual=${enabledTaskPaths.get().sorted()}"
        }
        check(aggregateTaskPaths.get() == expected) {
            "The MinGW local publication aggregate has the wrong task set. " +
                "expected=${expected.sorted()}, actual=${aggregateTaskPaths.get().sorted()}"
        }
        logger.lifecycle("Verified {} MinGW-closure local publication tasks.", expected.size)
    }
}
