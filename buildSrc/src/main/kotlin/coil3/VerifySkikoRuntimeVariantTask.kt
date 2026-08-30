package coil3

import org.gradle.api.DefaultTask
import org.gradle.api.provider.MapProperty
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.TaskAction

abstract class VerifySkikoRuntimeVariantTask : DefaultTask() {

    @get:Input
    abstract val expectedRootCoordinate: Property<String>

    @get:Input
    abstract val expectedTargetModuleName: Property<String>

    @get:Input
    abstract val expectedVariantName: Property<String>

    @get:Input
    abstract val expectedPlatform: Property<String>

    @get:Input
    abstract val selection: MapProperty<String, String>

    @TaskAction
    fun verify() {
        val expectedRoot = expectedRootCoordinate.get()
        val expectedGroup = expectedRoot.substringBefore(":")
        val expectedVersion = expectedRoot.substringAfterLast(":")
        val expectedTarget = "$expectedGroup:${expectedTargetModuleName.get()}:$expectedVersion"
        val resolved = selection.get()
        check(resolved.getValue("requested") == expectedRoot) {
            "Expected $expectedRoot but $path requested ${resolved.getValue("requested")}."
        }
        check(resolved.getValue("selectedRoot") == expectedRoot) {
            "Expected root $expectedRoot but $path selected ${resolved.getValue("selectedRoot")}."
        }
        check(resolved.getValue("selectedTarget") == expectedTarget) {
            "Expected target $expectedTarget but $path selected ${resolved.getValue("selectedTarget")}."
        }
        check(expectedVariantName.get() in resolved.getValue("variant")) {
            "Expected variant ${expectedVariantName.get()} but $path selected " +
                "${resolved.getValue("variant")}."
        }
        check(resolved.getValue("usage") == "skiko-runtime") {
            "Expected skiko-runtime usage but $path selected ${resolved.getValue("usage")}."
        }
        check(resolved.getValue("platform") == expectedPlatform.get()) {
            "Expected ${expectedPlatform.get()} platform but $path selected " +
                "${resolved.getValue("platform")}."
        }
        logger.lifecycle(
            "Verified {} -> {} via {} ({}/{})",
            expectedRoot,
            expectedTarget,
            resolved.getValue("variant"),
            resolved.getValue("usage"),
            resolved.getValue("platform"),
        )
    }
}
