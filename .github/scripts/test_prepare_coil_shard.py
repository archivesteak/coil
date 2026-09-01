from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from prepare_coil_shard import (
    COMPOSE_ARTIFACTS,
    ContractError,
    EXPECTED_PLATFORM_OWNERS,
    GROUP,
    OWNERS,
    PLUGIN_FILES,
    PLUGIN_IMPLEMENTATION,
    PLUGIN_MARKER,
    ROOT_ARTIFACTS,
    VERSION,
    expected_artifacts,
    load_json,
    module_requirements,
    primary_extension,
    restrict_root_module_variants,
    validate_publication,
    validate_release_contract,
)


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REQUIREMENTS_PATH = SCRIPT_DIRECTORY.parent / "coil-maven-variant-requirements.json"
GRADLE_PROPERTIES_PATH = SCRIPT_DIRECTORY.parents[1] / "gradle.properties"
RELEASE_WORKFLOW_PATH = SCRIPT_DIRECTORY.parent / "workflows/release-host-shards.yml"
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[1]
COMMITS = {
    "compose": "1" * 40,
    "skia": "2" * 40,
    "skiko": "3" * 40,
    "resources": "4" * 40,
    "coil": "5" * 40,
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance_record(owner: str, sources: dict[str, str]) -> dict[str, object]:
    return {
        "marker": f"provenance/{owner}.json",
        "sha256": hashlib.sha256(owner.encode()).hexdigest(),
        "sources": sources,
    }


def write_publication_fixture(
    version_directory: Path,
    artifact: str,
    root_artifact: str,
    variants: tuple[str, ...] | None = None,
) -> Path | None:
    base = f"{artifact}-{VERSION}"
    (version_directory / f"{base}.pom").write_text(
        f"""<project>
  <groupId>{GROUP}</groupId>
  <artifactId>{artifact}</artifactId>
  <version>{VERSION}</version>
  <name>Coil</name>
  <description>Image loading for Kotlin Multiplatform</description>
  <url>https://github.com/archivesteak/coil</url>
  <licenses><license><name>Apache-2.0</name><url>https://www.apache.org/licenses/LICENSE-2.0.txt</url></license></licenses>
  <developers><developer><id>archivesteak</id><name>Jack Harrington</name><url>https://github.com/archivesteak</url></developer></developers>
  <scm>
    <url>https://github.com/archivesteak/coil</url>
    <connection>scm:git:https://github.com/archivesteak/coil.git</connection>
    <developerConnection>scm:git:ssh://git@github.com/archivesteak/coil.git</developerConnection>
  </scm>
</project>
""",
        encoding="utf-8",
        newline="\n",
    )
    component = {
        "group": GROUP,
        "module": root_artifact,
        "version": VERSION,
    }
    if artifact != root_artifact:
        component["url"] = (
            f"../../{root_artifact}/{VERSION}/{root_artifact}-{VERSION}.module"
        )
    write_json(
        version_directory / f"{base}.module",
        {
            "component": component,
            "variants": [
                {"name": name}
                for name in (variants or ("metadataApiElements",))
            ],
        },
    )
    primary = f"{base}.{primary_extension(artifact)}"
    for filename in (
        primary,
        f"{base}-sources.jar",
        f"{base}-javadoc.jar",
    ):
        with zipfile.ZipFile(version_directory / filename, "w") as archive:
            entry = (
                "default/manifest"
                if filename == primary and filename.endswith(".klib")
                else "content.txt"
            )
            archive.writestr(entry, "verified")
    if variants and any(
        name.endswith("MetadataElements-published") for name in variants
    ):
        with zipfile.ZipFile(
            version_directory / f"{base}-metadata.jar", "w"
        ) as archive:
            archive.writestr("metadata/content.knm", "verified")
    if variants and any(
        name.endswith("ResourcesElements-published") for name in variants
    ):
        with zipfile.ZipFile(
            version_directory / f"{base}-kotlin_resources.kotlin_resources.zip",
            "w",
        ) as archive:
            archive.writestr("composeResources/verified.txt", "verified")
    if artifact != root_artifact:
        return None
    tooling_path = version_directory / f"{base}-kotlin-tooling-metadata.json"
    write_json(
        tooling_path,
        {
            "schemaVersion": "1.1.0",
            "buildSystem": "Gradle",
            "buildPlugin": "org.jetbrains.kotlin.gradle.plugin.KotlinMultiplatformPluginWrapper",
            "projectTargets": [{"platformType": "common"}],
        },
    )
    return tooling_path


class ReleaseFixture:
    def __init__(self, root: Path) -> None:
        self.repository = root / "repository"
        self.repository.mkdir()
        self.core_requirements = root / "core-requirements.json"
        self.core_report = root / "core-report.json"
        self.resources_requirements = root / "resources-requirements.json"
        self.resources_report = root / "resources-report.json"
        self.coil_requirements = root / "coil-requirements.json"
        self.plugin_report = root / "plugin-report.json"

        core_sources = {
            "windows": {
                "compose": COMMITS["compose"],
                "skia": COMMITS["skia"],
                "skiko": COMMITS["skiko"],
            },
            "apple": {
                "compose": COMMITS["compose"],
                "skiko": COMMITS["skiko"],
            },
            "web": {
                "compose": COMMITS["compose"],
                "skiko": COMMITS["skiko"],
            },
        }
        write_json(
            self.core_requirements,
            {"schemaVersion": 2, "sourceProvenance": core_sources},
        )
        write_json(
            self.core_report,
            {
                "requirementsSha256": sha256(self.core_requirements),
                "sourceProvenance": {
                    owner: provenance_record(owner, core_sources[owner])
                    for owner in OWNERS
                },
            },
        )

        resources_sources = {
            "compose-core": COMMITS["compose"],
            "resources": COMMITS["resources"],
            "skia": COMMITS["skia"],
            "skiko": COMMITS["skiko"],
        }
        resources_provenance = {
            owner: dict(resources_sources) for owner in OWNERS
        }
        write_json(
            self.resources_requirements,
            {"schemaVersion": 2, "sourceProvenance": resources_provenance},
        )
        write_json(
            self.resources_report,
            {
                "requirementsSha256": sha256(self.resources_requirements),
                "sourceProvenance": {
                    owner: provenance_record(owner, resources_provenance[owner])
                    for owner in OWNERS
                },
            },
        )

        coil_requirements = load_json(REQUIREMENTS_PATH, "checked-in requirements")
        exact_sources = {"coil": COMMITS["coil"], **resources_sources}
        coil_requirements["sourceProvenance"] = {
            owner: dict(exact_sources) for owner in OWNERS
        }
        write_json(self.coil_requirements, coil_requirements)

        plugin_files: dict[str, dict[str, object]] = {}
        for relative in sorted(PLUGIN_FILES):
            path = self.repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"payload:{relative}".encode())
            plugin_files[relative] = {
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
        write_json(
            self.plugin_report,
            {
                "schemaVersion": 1,
                "sourceRef": COMMITS["resources"],
                "pluginId": "io.github.archivesteak.compose",
                "legacyPluginId": "org.jetbrains.compose",
                "implementationClass": "org.jetbrains.compose.ComposePlugin",
                "implementationCoordinate": PLUGIN_IMPLEMENTATION,
                "markerCoordinate": PLUGIN_MARKER,
                "files": plugin_files,
            },
        )

    def validate(self) -> None:
        validate_release_contract(
            repository=self.repository,
            requirements_path=self.coil_requirements,
            coil_ref=COMMITS["coil"],
            resources_ref=COMMITS["resources"],
            core_report_path=self.core_report,
            core_requirements_path=self.core_requirements,
            resources_report_path=self.resources_report,
            resources_requirements_path=self.resources_requirements,
            plugin_report_path=self.plugin_report,
        )


class PrepareCoilShardTest(unittest.TestCase):
    def test_root_metadata_is_narrowed_to_the_exact_host_variant_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            version_directory = Path(directory)
            artifact = ROOT_ARTIFACTS[0]
            module_path = version_directory / f"{artifact}-{VERSION}.module"
            write_json(
                module_path,
                {
                    "component": {
                        "group": GROUP,
                        "module": artifact,
                        "version": VERSION,
                    },
                    "variants": [
                        {"name": "metadataApiElements", "attributes": {"owner": "common"}},
                        {"name": "jvmApiElements-published", "attributes": {"owner": "windows"}},
                        {"name": "jsApiElements-published", "attributes": {"owner": "web"}},
                    ],
                },
            )

            restrict_root_module_variants(
                version_directory,
                artifact,
                {"metadataApiElements", "jvmApiElements-published"},
            )

            module = load_json(module_path, "narrowed root metadata")
            self.assertEqual(
                [variant["name"] for variant in module["variants"]],
                ["metadataApiElements", "jvmApiElements-published"],
            )

    def test_skiko_browser_runtime_matches_published_module_and_polyfills_node(self) -> None:
        for relative in (
            "coil-core/src/jsMain/kotlin/coil3/decode/WebWorker.js.kt",
            "coil-core/src/wasmJsMain/kotlin/coil3/decode/SkikoModule.wasmJs.kt",
        ):
            source = (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn('"./js-skiko-reexport-symbols.mjs"', source)
            self.assertNotIn('"./js-reexport-symbols.mjs"', source)

        karma_config = (
            REPOSITORY_ROOT / "karma.config.d/20-skiko-browser-runtime.js"
        ).read_text(encoding="utf-8")
        self.assertIn('require("node-polyfill-webpack-plugin")', karma_config)
        self.assertIn("new NodePolyfillPlugin()", karma_config)
        self.assertIn("isKotlinJsTest", karma_config)
        self.assertIn("static/load.mjs", karma_config)
        self.assertIn("if (isKotlinJsTest)", karma_config)


    def test_root_publication_requires_valid_kotlin_tooling_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            version_directory = Path(directory)
            artifact = ROOT_ARTIFACTS[0]
            tooling_path = write_publication_fixture(
                version_directory,
                artifact,
                artifact,
            )
            self.assertIsNotNone(tooling_path)

            expected_variants = {"metadataApiElements"}
            validate_publication(
                version_directory,
                artifact,
                artifact,
                expected_variants,
            )

            write_json(
                tooling_path,
                {
                    "schemaVersion": "1.1.0",
                    "buildSystem": "Gradle",
                    "buildPlugin": "org.jetbrains.kotlin.gradle.plugin.KotlinMultiplatformPluginWrapper",
                    "projectTargets": [],
                },
            )
            with self.assertRaisesRegex(
                ContractError, "Kotlin tooling metadata is incomplete"
            ):
                validate_publication(
                    version_directory,
                    artifact,
                    artifact,
                    expected_variants,
                )

    def test_leaf_publication_redirects_to_its_declared_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            version_directory = Path(directory)
            artifact = "coil-core-jvm"
            root_artifact = "coil-core"
            variants = (
                "jvmApiElements-published",
                "jvmRuntimeElements-published",
                "jvmSourcesElements-published",
            )
            write_publication_fixture(
                version_directory,
                artifact,
                root_artifact,
                variants,
            )

            validate_publication(
                version_directory,
                artifact,
                root_artifact,
                set(variants),
            )

            module_path = version_directory / f"{artifact}-{VERSION}.module"
            module = load_json(module_path, "fixture metadata")
            module["component"]["url"] = "../../coil/3.6.0-mingw/coil.module"
            write_json(module_path, module)
            with self.assertRaisesRegex(ContractError, "wrong root redirect"):
                validate_publication(
                    version_directory,
                    artifact,
                    root_artifact,
                    set(variants),
                )

    def test_compose_apple_leaf_requires_metadata_and_resources_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            version_directory = Path(directory)
            artifact = "coil-compose-core-macosarm64"
            root_artifact = "coil-compose-core"
            variants = (
                "macosArm64ApiElements-published",
                "macosArm64SourcesElements-published",
                "macosArm64MetadataElements-published",
                "macosArm64ResourcesElements-published",
            )
            write_publication_fixture(
                version_directory,
                artifact,
                root_artifact,
                variants,
            )

            validate_publication(
                version_directory,
                artifact,
                root_artifact,
                set(variants),
            )

            metadata = version_directory / f"{artifact}-{VERSION}-metadata.jar"
            metadata.unlink()
            with self.assertRaisesRegex(ContractError, "publication files differ"):
                validate_publication(
                    version_directory,
                    artifact,
                    root_artifact,
                    set(variants),
                )

    def test_central_verifier_runs_before_validated_repository_upload(self) -> None:
        workflow = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")
        verifier = (
            "python3 core-contract/.github/scripts/verify-central-publications.py "
            "\\\n            \"$RUNNER_TEMP/validated-coil/repository\""
        )
        upload = "- name: Upload validated core, resources, plugin, and Coil repository"
        self.assertIn(verifier, workflow)
        self.assertLess(workflow.index(verifier), workflow.index(upload))

    def test_publication_properties_identify_the_fork_maintainer(self) -> None:
        properties = {}
        for raw_line in GRADLE_PROPERTIES_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            properties[key] = value

        self.assertEqual(properties["POM_DEVELOPER_ID"], "archivesteak")
        self.assertEqual(properties["POM_DEVELOPER_NAME"], "Jack Harrington")
        self.assertEqual(
            properties["POM_DEVELOPER_URL"],
            "https://github.com/archivesteak",
        )
        self.assertEqual(
            properties["POM_SCM_DEV_CONNECTION"],
            "scm:git:ssh://git@github.com/archivesteak/coil.git",
        )

    def test_every_host_owns_root_metadata_and_exact_target_count(self) -> None:
        requirements = load_json(REQUIREMENTS_PATH, "checked-in requirements")
        expected_counts = {"windows": 18, "apple": 24, "web": 32}
        for owner, count in expected_counts.items():
            artifacts = expected_artifacts(requirements, owner)
            self.assertEqual(len(artifacts), count)
            self.assertTrue(set(ROOT_ARTIFACTS).issubset(artifacts))

    def test_checked_in_variant_contract_matches_coil_3_6_targets(self) -> None:
        requirements = load_json(REQUIREMENTS_PATH, "checked-in requirements")
        modules = module_requirements(requirements)
        for artifact, module in modules.items():
            variants = module["requiredVariants"]
            self.assertEqual(
                variants["common"],
                ["metadataApiElements", "metadataSourcesElements"],
            )
            expected_mingw_variants = [
                "mingwX64ApiElements-published",
                "mingwX64SourcesElements-published",
            ]
            if artifact in COMPOSE_ARTIFACTS:
                expected_mingw_variants.append("mingwX64ResourcesElements-published")
            self.assertEqual(variants["mingwX64"], expected_mingw_variants)
            expected_platforms = set(EXPECTED_PLATFORM_OWNERS)
            if artifact in COMPOSE_ARTIFACTS:
                expected_platforms -= {"linuxX64", "linuxArm64"}
            self.assertEqual(set(variants), expected_platforms)
            for platform in ("macosArm64", "iosArm64", "iosSimulatorArm64"):
                self.assertIn(
                    f"{platform}MetadataElements-published",
                    variants[platform],
                )
            resource_platforms = {
                platform
                for platform, names in variants.items()
                if any(name.endswith("ResourcesElements-published") for name in names)
            }
            self.assertEqual(
                resource_platforms,
                {
                    "mingwX64",
                    "macosArm64",
                    "iosArm64",
                    "iosSimulatorArm64",
                    "js",
                    "wasmJs",
                }
                if artifact in COMPOSE_ARTIFACTS
                else set(),
            )

    def test_validates_exact_upstream_reports_and_plugin_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            fixture.validate()

    def test_upstream_requirements_hash_is_independent_of_checkout_line_endings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            for path in (
                fixture.core_requirements,
                fixture.resources_requirements,
            ):
                content = path.read_text(encoding="utf-8")
                path.write_text(
                    content.replace("\n", "\r\n"),
                    encoding="utf-8",
                    newline="",
                )
            fixture.validate()

    def test_rejects_tampered_plugin_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            relative = sorted(PLUGIN_FILES)[0]
            (fixture.repository / relative).write_bytes(b"tampered")
            with self.assertRaisesRegex(ContractError, "size differs|hash differs"):
                fixture.validate()

    def test_rejects_report_from_different_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            requirements = load_json(
                fixture.resources_requirements,
                "resources requirements",
            )
            altered = copy.deepcopy(requirements)
            altered["note"] = "different contract"
            write_json(fixture.resources_requirements, altered)
            with self.assertRaisesRegex(ContractError, "checked-out requirements"):
                fixture.validate()

    def test_checked_in_placeholders_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            with self.assertRaisesRegex(ContractError, "selected sources"):
                validate_release_contract(
                    repository=fixture.repository,
                    requirements_path=REQUIREMENTS_PATH,
                    coil_ref=COMMITS["coil"],
                    resources_ref=COMMITS["resources"],
                    core_report_path=fixture.core_report,
                    core_requirements_path=fixture.core_requirements,
                    resources_report_path=fixture.resources_report,
                    resources_requirements_path=fixture.resources_requirements,
                    plugin_report_path=fixture.plugin_report,
                )


if __name__ == "__main__":
    unittest.main()
