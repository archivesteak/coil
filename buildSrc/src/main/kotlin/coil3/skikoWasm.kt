/*
 * Copyright 2020-2022 JetBrains s.r.o. and respective authors and developers.
 * Use of this source code is governed by the Apache 2.0 license that can be found in the LICENSE.txt file.
 */
package coil3

import org.gradle.api.Project
import org.gradle.api.artifacts.Configuration
import org.gradle.api.artifacts.MinimalExternalModuleDependency
import org.gradle.api.artifacts.component.ModuleComponentSelector
import org.gradle.api.artifacts.result.ResolvedDependencyResult
import org.gradle.api.artifacts.result.UnresolvedDependencyResult
import org.gradle.api.attributes.Attribute
import org.gradle.api.attributes.AttributeContainer
import org.gradle.api.attributes.Usage
import org.gradle.api.provider.Provider
import org.gradle.kotlin.dsl.findByType
import org.gradle.kotlin.dsl.register
import org.gradle.kotlin.dsl.support.uppercaseFirstChar
import org.jetbrains.compose.web.tasks.UnpackSkikoWasmRuntimeTask
import org.jetbrains.kotlin.gradle.dsl.KotlinMultiplatformExtension
import org.jetbrains.kotlin.gradle.targets.js.ir.KotlinJsIrTarget

// This file is copied and modified from the Compose Multiplatform plugin so we can create the Skiko
// web runtime without requiring every Coil module to apply the Compose plugin or depend on Compose
// runtime. The legacy path is retained for untouched upstream modules. MinGW closure modules resolve
// target-specific runtime variants from the same fork root as their Skiko API dependency.
// https://github.com/JetBrains/compose-multiplatform/blob/master/gradle-plugins/compose/src/main/kotlin/org/jetbrains/compose/experimental/web/internal/configureExperimentalWebApplication.kt

fun Project.createSkikoWasmJsRuntimeDependency(
    upstreamSkikoVersion: Provider<String>,
    forkSkikoDependency: Provider<MinimalExternalModuleDependency>?,
) {
    if (
        plugins.hasPlugin(UPSTREAM_COMPOSE_PLUGIN_ID) ||
        plugins.hasPlugin(FORK_COMPOSE_PLUGIN_ID)
    ) {
        // The Compose plugin owns runtime selection for every module that applies it. The forked
        // plugin handles both upstream and fork UI lineages, so no consumer override belongs here.
        return
    }

    afterEvaluate {
        val targets = extensions.findByType<KotlinMultiplatformExtension>()!!
            .targets.asMap.values.filterIsInstanceTo(mutableSetOf<KotlinJsIrTarget>())
        if (forkSkikoDependency == null) {
            targets.configureUpstreamRuntime(this, upstreamSkikoVersion)
        } else {
            targets.configureForkRuntime(this, forkSkikoDependency)
        }
    }
}

private fun Collection<KotlinJsIrTarget>.configureUpstreamRuntime(
    project: Project,
    skikoVersion: Provider<String>,
) {
    val runtime = project.configurations.create("skikoJsWasmRuntime") {
        description = "The upstream combined Skiko runtime used by Coil's JS and Wasm targets."
        isCanBeConsumed = false
        isCanBeResolved = true
    }
    val dependency = skikoVersion.map { version ->
        project.dependencies.create("$UPSTREAM_SKIKO_GROUP:skiko-js-wasm-runtime:$version")
    }
    runtime.defaultDependencies {
        addLater(dependency)
    }
    forEach { target ->
        target.configureRuntimeResources(project, runtime)
    }
}

private fun Collection<KotlinJsIrTarget>.configureForkRuntime(
    project: Project,
    dependency: Provider<MinimalExternalModuleDependency>,
) {
    val runtimes = associateWith { target ->
        project.createForkRuntimeConfiguration(target, dependency)
    }
    runtimes.forEach { (target, runtime) ->
        project.registerForkRuntimeVerification(target, runtime, dependency)
    }

    runtimes.forEach { (target, runtime) ->
        target.configureRuntimeResources(project, runtime)
    }
}

private fun Project.createForkRuntimeConfiguration(
    target: KotlinJsIrTarget,
    dependency: Provider<MinimalExternalModuleDependency>,
): Configuration {
    val mainCompilation = target.compilations.getByName("main")
    val targetRuntime = configurations.getByName(mainCompilation.runtimeDependencyConfigurationName)
    return configurations.create("coilSkikoRuntime${target.targetName.uppercaseFirstChar()}") {
        description = "The archivesteak Skiko runtime for Coil's ${target.targetName} target."
        isCanBeConsumed = false
        isCanBeResolved = true
        copyAttributesFrom(targetRuntime)
        attributes.attribute(
            Usage.USAGE_ATTRIBUTE,
            objects.named(Usage::class.java, SKIKO_RUNTIME_USAGE),
        )
        defaultDependencies {
            addLater(dependency)
        }
    }
}

private fun Configuration.copyAttributesFrom(source: Configuration) {
    source.attributes.keySet().forEach { rawAttribute ->
        @Suppress("UNCHECKED_CAST")
        val attribute = rawAttribute as Attribute<Any>
        source.attributes.getAttribute(attribute)?.let { value ->
            attributes.attribute(attribute, value)
        }
    }
}

private fun KotlinJsIrTarget.configureRuntimeResources(
    project: Project,
    runtime: Configuration,
) {
    val mainCompilation = compilations.getByName("main")
    val testCompilation = compilations.getByName("test")
    val unpackedRuntimeDir = project.layout.buildDirectory.dir("compose/skiko-wasm/$targetName")
    mainCompilation.defaultSourceSet.resources.srcDir(unpackedRuntimeDir)
    testCompilation.defaultSourceSet.resources.srcDir(unpackedRuntimeDir)

    val taskName = "unpackSkikoWasmRuntime${targetName.uppercaseFirstChar()}"
    val unpackRuntime = project.tasks.register<UnpackSkikoWasmRuntimeTask>(taskName) {
        skikoRuntimeFiles = runtime
        outputDir.set(unpackedRuntimeDir)
    }
    project.tasks.named(mainCompilation.processResourcesTaskName).configure {
        dependsOn(unpackRuntime)
    }
    project.tasks.named(testCompilation.processResourcesTaskName).configure {
        dependsOn(unpackRuntime)
    }
}

private fun Project.registerForkRuntimeVerification(
    target: KotlinJsIrTarget,
    runtime: Configuration,
    dependency: Provider<MinimalExternalModuleDependency>,
) {
    val expectedTargetModule = when (target.targetName) {
        "js" -> "skiko-js"
        "wasmJs" -> "skiko-wasm-js"
        else -> error("Unsupported Skiko web runtime target '${target.targetName}'")
    }
    val expectedVariant = when (target.targetName) {
        "js" -> "skikoWasmRuntimeElementsForJs"
        "wasmJs" -> "skikoWasmRuntimeElementsForWasmJs"
        else -> error("Unsupported Skiko web runtime target '${target.targetName}'")
    }
    val expectedPlatformType = if (target.targetName == "js") "js" else "wasm"
    val task = tasks.register<VerifySkikoRuntimeVariantTask>(
        "verifySkikoRuntime${target.targetName.uppercaseFirstChar()}Variant",
    ) {
        group = "verification"
        description = "Verifies the ${target.targetName} Skiko runtime resolves from the fork root."
        expectedRootCoordinate.set(
            dependency.map { "${it.group}:${it.name}:${it.version}" },
        )
        expectedTargetModuleName.set(expectedTargetModule)
        expectedVariantName.set(expectedVariant)
        expectedPlatform.set(expectedPlatformType)
        selection.set(provider { runtime.skikoRuntimeSelection() })
    }
    tasks.matching { it.name == "check" }.configureEach {
        dependsOn(task)
    }
    rootProject.tasks.named("verifySkikoRuntimeVariants").configure {
        dependsOn(task)
    }
}

private fun Configuration.skikoRuntimeSelection(): Map<String, String> {
    val dependencies = incoming.resolutionResult.root.dependencies
    val unresolved = dependencies.filterIsInstance<UnresolvedDependencyResult>()
    check(unresolved.isEmpty()) {
        "Configuration '$name' could not resolve its Skiko runtime: " +
            unresolved.joinToString { "${it.attempted}: ${it.failure.message}" }
    }
    val direct = dependencies
        .filterIsInstance<ResolvedDependencyResult>()
        .singleOrNull()
        ?: error("Configuration '$name' must resolve exactly one direct Skiko runtime dependency")
    val requested = direct.requested as? ModuleComponentSelector
        ?: error("Configuration '$name' did not request an external Skiko runtime module")
    val selectedRoot = direct.selected.moduleVersion
        ?: error("Configuration '$name' did not select an external Skiko runtime root")
    val target = direct.selected.dependencies
        .filterIsInstance<ResolvedDependencyResult>()
        .mapNotNull { it.selected.moduleVersion }
        .singleOrNull { it.group == selectedRoot.group && it.version == selectedRoot.version }
        ?: error(
            "Configuration '$name' did not resolve exactly one fork target from the Skiko root variant",
        )
    val attributes = direct.resolvedVariant.attributes
    return mapOf(
        "requested" to "${requested.group}:${requested.module}:${requested.version}",
        "selectedRoot" to selectedRoot.toString(),
        "selectedTarget" to target.toString(),
        "variant" to direct.resolvedVariant.displayName,
        "usage" to (attributes.getAttribute(Usage.USAGE_ATTRIBUTE)?.name ?: "<missing>"),
        "platform" to (attributes.stringAttribute(KOTLIN_PLATFORM_TYPE_ATTRIBUTE) ?: "<missing>"),
    )
}

private fun AttributeContainer.stringAttribute(name: String): String? {
    val rawAttribute = keySet().singleOrNull { it.name == name } ?: return null
    @Suppress("UNCHECKED_CAST")
    val attribute = rawAttribute as Attribute<Any>
    return getAttribute(attribute)?.toString()
}

private const val UPSTREAM_SKIKO_GROUP = "org.jetbrains.skiko"
private const val UPSTREAM_COMPOSE_PLUGIN_ID = "org.jetbrains.compose"
private const val FORK_COMPOSE_PLUGIN_ID = "io.github.archivesteak.compose"
private const val SKIKO_RUNTIME_USAGE = "skiko-runtime"
private const val KOTLIN_PLATFORM_TYPE_ATTRIBUTE = "org.jetbrains.kotlin.platform.type"
