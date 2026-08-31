from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prepare_coil_shard import (
    COMPOSE_ARTIFACTS,
    ContractError,
    EXPECTED_PLATFORM_OWNERS,
    OWNERS,
    PLUGIN_FILES,
    PLUGIN_IMPLEMENTATION,
    PLUGIN_MARKER,
    ROOT_ARTIFACTS,
    expected_artifacts,
    load_json,
    module_requirements,
    validate_release_contract,
)


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REQUIREMENTS_PATH = SCRIPT_DIRECTORY.parent / "coil-maven-variant-requirements.json"
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
            self.assertEqual(
                variants["mingwX64"],
                ["mingwX64ApiElements-published", "mingwX64SourcesElements-published"],
            )
            expected_platforms = set(EXPECTED_PLATFORM_OWNERS)
            if artifact in COMPOSE_ARTIFACTS:
                expected_platforms -= {"linuxX64", "linuxArm64"}
            self.assertEqual(set(variants), expected_platforms)

    def test_validates_exact_upstream_reports_and_plugin_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
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
