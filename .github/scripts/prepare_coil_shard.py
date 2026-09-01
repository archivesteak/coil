#!/usr/bin/env python3
"""Validate the upstream artifact contract and collect one exact Coil host shard."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ElementTree
import zipfile
from pathlib import Path
from typing import Any, Iterable


OWNERS = ("windows", "apple", "web")
GROUP = "io.github.archivesteak.coil3"
VERSION = "3.6.0-mingw"
ROOT_ARTIFACTS = (
    "coil",
    "coil-compose",
    "coil-compose-core",
    "coil-core",
    "coil-network-core",
    "coil-network-ktor3",
)
COMPOSE_ARTIFACTS = {"coil-compose", "coil-compose-core"}
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
PLACEHOLDER_COMMIT = "0" * 40
EXPECTED_PLATFORM_OWNERS = {
    "common": "windows",
    "jvm": "windows",
    "mingwX64": "windows",
    "macosArm64": "apple",
    "iosArm64": "apple",
    "iosSimulatorArm64": "apple",
    "js": "web",
    "wasmJs": "web",
    "android": "web",
    "linuxX64": "web",
    "linuxArm64": "web",
}
PLUGIN_IMPLEMENTATION = (
    "io.github.archivesteak.compose:compose-gradle-plugin:"
    "1.12.0-beta02-mingw"
)
PLUGIN_MARKER = (
    "io.github.archivesteak.compose:"
    "io.github.archivesteak.compose.gradle.plugin:1.12.0-beta02-mingw"
)
PLUGIN_FILES = {
    "io/github/archivesteak/compose/compose-gradle-plugin/"
    "1.12.0-beta02-mingw/compose-gradle-plugin-1.12.0-beta02-mingw.jar",
    "io/github/archivesteak/compose/compose-gradle-plugin/"
    "1.12.0-beta02-mingw/compose-gradle-plugin-1.12.0-beta02-mingw-sources.jar",
    "io/github/archivesteak/compose/compose-gradle-plugin/"
    "1.12.0-beta02-mingw/compose-gradle-plugin-1.12.0-beta02-mingw-javadoc.jar",
    "io/github/archivesteak/compose/compose-gradle-plugin/"
    "1.12.0-beta02-mingw/compose-gradle-plugin-1.12.0-beta02-mingw.module",
    "io/github/archivesteak/compose/compose-gradle-plugin/"
    "1.12.0-beta02-mingw/compose-gradle-plugin-1.12.0-beta02-mingw.pom",
    "io/github/archivesteak/compose/"
    "io.github.archivesteak.compose.gradle.plugin/1.12.0-beta02-mingw/"
    "io.github.archivesteak.compose.gradle.plugin-1.12.0-beta02-mingw.pom",
}


class ContractError(ValueError):
    """The selected source, report, or publication does not match the release contract."""


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json(path: Path, description: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"{description} must be a regular file: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read {description} {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"{description} must contain a JSON object: {path}")
    return value


def validate_commit(value: object, description: str) -> str:
    if not isinstance(value, str) or COMMIT_PATTERN.fullmatch(value) is None:
        raise ContractError(
            f"{description} must be a full lowercase 40-character commit SHA"
        )
    if value == PLACEHOLDER_COMMIT:
        raise ContractError(f"{description} is still the all-zero release placeholder")
    return value


def sha256_file(path: Path, description: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"{description} must be a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def module_requirements(requirements: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if requirements.get("schemaVersion") != 2:
        raise ContractError("Coil requirements must use schemaVersion 2")
    if requirements.get("groupPrefix") != GROUP:
        raise ContractError(f"Coil requirements must use groupPrefix {GROUP}")
    if requirements.get("platformOwners") != EXPECTED_PLATFORM_OWNERS:
        raise ContractError("Coil platform ownership differs from the exact host contract")
    if requirements.get("pomOnlyModules") != []:
        raise ContractError("Coil requirements must not contain POM-only modules")

    raw_modules = requirements.get("modules")
    if not isinstance(raw_modules, list):
        raise ContractError("Coil requirements must contain a modules array")
    modules: dict[str, dict[str, Any]] = {}
    for module in raw_modules:
        if not isinstance(module, dict):
            raise ContractError("every Coil module requirement must be an object")
        coordinate = module.get("coordinate")
        if not isinstance(coordinate, str):
            raise ContractError("every Coil module coordinate must be a string")
        parts = coordinate.split(":")
        if len(parts) != 3 or parts[0] != GROUP or parts[2] != VERSION:
            raise ContractError(f"unexpected Coil coordinate: {coordinate!r}")
        artifact = parts[1]
        if artifact in modules:
            raise ContractError(f"duplicate Coil root artifact: {artifact}")
        required_variants = module.get("requiredVariants")
        target_modules = module.get("targetModules")
        if not isinstance(required_variants, dict) or not isinstance(
            target_modules, dict
        ):
            raise ContractError(f"{artifact} lacks variants or target modules")
        expected_platforms = set(EXPECTED_PLATFORM_OWNERS)
        if artifact in COMPOSE_ARTIFACTS:
            expected_platforms -= {"linuxX64", "linuxArm64"}
        if set(required_variants) != expected_platforms:
            raise ContractError(
                f"{artifact} required platforms differ: "
                f"expected {sorted(expected_platforms)}, "
                f"found {sorted(required_variants)}"
            )
        if set(target_modules) != expected_platforms - {"common"}:
            raise ContractError(f"{artifact} target module platforms are incomplete")
        for platform, target in target_modules.items():
            if not isinstance(target, str) or not target.startswith(f"{artifact}-"):
                raise ContractError(
                    f"{artifact} has invalid targetModules[{platform!r}]={target!r}"
                )
        modules[artifact] = module
    if set(modules) != set(ROOT_ARTIFACTS):
        raise ContractError(
            f"Coil roots must be exactly {list(ROOT_ARTIFACTS)}, "
            f"found {sorted(modules)}"
        )
    return modules


def expected_artifacts(requirements: dict[str, Any], owner: str) -> set[str]:
    if owner not in OWNERS:
        raise ContractError(f"invalid Coil owner {owner!r}")
    modules = module_requirements(requirements)
    # Every host must publish the root metadata. The merger selects common variants from
    # Windows and platform variants from their owners, then proves duplicate root payloads equal.
    artifacts = set(ROOT_ARTIFACTS)
    for module in modules.values():
        for platform in module["requiredVariants"]:
            if platform == "common" or EXPECTED_PLATFORM_OWNERS[platform] != owner:
                continue
            artifacts.add(module["targetModules"][platform])
    return artifacts


def report_sources(
    report_path: Path,
    requirements_path: Path,
    description: str,
) -> dict[str, str]:
    report = load_json(report_path, f"{description} merge report")
    requirements = load_json(requirements_path, f"{description} requirements")
    expected_hash = sha256_file(requirements_path, f"{description} requirements")
    if report.get("requirementsSha256") != expected_hash:
        raise ContractError(
            f"{description} merge report does not match the checked-out requirements"
        )
    expected_provenance = requirements.get("sourceProvenance")
    actual_provenance = report.get("sourceProvenance")
    if not isinstance(expected_provenance, dict) or set(expected_provenance) != set(
        OWNERS
    ):
        raise ContractError(f"{description} requirements lack exact owner provenance")
    if not isinstance(actual_provenance, dict) or set(actual_provenance) != set(OWNERS):
        raise ContractError(f"{description} report lacks exact owner provenance")

    combined: dict[str, str] = {}
    for owner in OWNERS:
        record = actual_provenance[owner]
        if not isinstance(record, dict) or set(record) != {"marker", "sha256", "sources"}:
            raise ContractError(f"{description} {owner} provenance record is malformed")
        marker = record["marker"]
        marker_hash = record["sha256"]
        sources = record["sources"]
        if marker != f"provenance/{owner}.json":
            raise ContractError(f"{description} {owner} provenance marker path differs")
        if not isinstance(marker_hash, str) or SHA256_PATTERN.fullmatch(marker_hash) is None:
            raise ContractError(f"{description} {owner} provenance hash is invalid")
        if not isinstance(sources, dict) or sources != expected_provenance[owner]:
            raise ContractError(
                f"{description} {owner} report sources differ from requirements"
            )
        for name, raw_commit in sources.items():
            if not isinstance(name, str) or not name:
                raise ContractError(f"{description} contains an invalid source name")
            commit = validate_commit(raw_commit, f"{description} {owner}/{name}")
            previous = combined.setdefault(name, commit)
            if previous != commit:
                raise ContractError(
                    f"{description} gives source {name!r} inconsistent commits"
                )
    return combined


def validate_plugin_report(
    repository: Path,
    report_path: Path,
    resources_ref: str,
) -> None:
    report = load_json(report_path, "plugin provenance report")
    expected_keys = {
        "schemaVersion",
        "sourceRef",
        "pluginId",
        "legacyPluginId",
        "implementationClass",
        "implementationCoordinate",
        "markerCoordinate",
        "files",
    }
    if set(report) != expected_keys or report.get("schemaVersion") != 1:
        raise ContractError("plugin provenance report has the wrong schema")
    expected_identity = {
        "sourceRef": resources_ref,
        "pluginId": "io.github.archivesteak.compose",
        "legacyPluginId": "org.jetbrains.compose",
        "implementationClass": "org.jetbrains.compose.ComposePlugin",
        "implementationCoordinate": PLUGIN_IMPLEMENTATION,
        "markerCoordinate": PLUGIN_MARKER,
    }
    for key, expected in expected_identity.items():
        if report.get(key) != expected:
            raise ContractError(f"plugin provenance {key} differs from {expected!r}")
    raw_files = report.get("files")
    if not isinstance(raw_files, dict) or set(raw_files) != PLUGIN_FILES:
        raise ContractError("plugin provenance does not contain the exact six files")

    repository = repository.resolve()
    for relative, record in raw_files.items():
        if not isinstance(record, dict) or set(record) != {"size", "sha256"}:
            raise ContractError(f"plugin provenance file record is malformed: {relative}")
        relative_path = Path(relative)
        if relative_path.is_absolute() or any(
            part in {"", ".", ".."} for part in relative_path.parts
        ):
            raise ContractError(f"plugin provenance contains an unsafe path: {relative}")
        path = repository / relative_path
        try:
            path.resolve(strict=True).relative_to(repository)
        except (OSError, ValueError) as error:
            raise ContractError(f"plugin file escapes the repository: {relative}") from error
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"plugin file is missing or unsafe: {relative}")
        size = record.get("size")
        digest = record.get("sha256")
        if type(size) is not int or size <= 0 or path.stat().st_size != size:
            raise ContractError(f"plugin file size differs: {relative}")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            raise ContractError(f"plugin file hash is invalid: {relative}")
        if sha256_file(path, f"plugin file {relative}") != digest:
            raise ContractError(f"plugin file hash differs: {relative}")


def validate_release_contract(
    *,
    repository: Path,
    requirements_path: Path,
    coil_ref: str,
    resources_ref: str,
    core_report_path: Path,
    core_requirements_path: Path,
    resources_report_path: Path,
    resources_requirements_path: Path,
    plugin_report_path: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    coil_ref = validate_commit(coil_ref, "coil_ref")
    resources_ref = validate_commit(resources_ref, "resources_ref")
    requirements = load_json(requirements_path, "Coil requirements")
    module_requirements(requirements)

    core_sources = report_sources(
        core_report_path,
        core_requirements_path,
        "core",
    )
    expected_core_names = {"compose", "skia", "skiko"}
    if set(core_sources) != expected_core_names:
        raise ContractError(
            f"core report sources differ: expected {sorted(expected_core_names)}, "
            f"found {sorted(core_sources)}"
        )
    resources_sources = report_sources(
        resources_report_path,
        resources_requirements_path,
        "resources",
    )
    expected_resources_sources = {
        "compose-core": core_sources["compose"],
        "resources": resources_ref,
        "skia": core_sources["skia"],
        "skiko": core_sources["skiko"],
    }
    if resources_sources != expected_resources_sources:
        raise ContractError("resources report does not exactly extend core provenance")
    validate_plugin_report(repository, plugin_report_path, resources_ref)

    actual_sources = {"coil": coil_ref, **expected_resources_sources}
    provenance = requirements.get("sourceProvenance")
    if not isinstance(provenance, dict) or set(provenance) != set(OWNERS):
        raise ContractError("Coil requirements lack exact owner provenance")
    for owner in OWNERS:
        if provenance[owner] != actual_sources:
            raise ContractError(
                f"Coil {owner} provenance does not match the selected sources"
            )
    return requirements, actual_sources


def ensure_tree_has_no_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise ContractError(f"publication path must not be a symlink: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ContractError(f"publication contains a symlink: {path}")


def primary_extension(artifact: str) -> str:
    if artifact in ROOT_ARTIFACTS or artifact.endswith("-jvm"):
        return "jar"
    if artifact.endswith("-android"):
        return "aar"
    return "klib"


def xml_text(root: ElementTree.Element, name: str) -> str:
    element = root.find(f"{{*}}{name}")
    return element.text.strip() if element is not None and element.text else ""


def verify_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries:
                raise ContractError(f"published archive is empty: {path}")
            for entry in entries:
                parts = Path(entry.filename.replace("\\", "/")).parts
                if entry.filename.startswith(("/", "\\")) or any(
                    part in {"", ".", ".."} for part in parts
                ):
                    raise ContractError(f"published archive has an unsafe entry: {path}")
            names = {entry.filename for entry in entries}
    except zipfile.BadZipFile as error:
        raise ContractError(f"published archive is corrupt: {path}") from error
    if path.suffix == ".klib" and "default/manifest" not in names:
        raise ContractError(f"published KLIB lacks default/manifest: {path}")
    if path.suffix == ".aar" and "AndroidManifest.xml" not in names:
        raise ContractError(f"published AAR lacks AndroidManifest.xml: {path}")


def validate_publication(version_directory: Path, artifact: str) -> None:
    base = f"{artifact}-{VERSION}"
    primary = f"{base}.{primary_extension(artifact)}"
    expected = {
        f"{base}.pom",
        f"{base}.module",
        primary,
        f"{base}-sources.jar",
        f"{base}-javadoc.jar",
    }
    existing = {path.name for path in version_directory.iterdir() if path.is_file()}
    if existing != expected:
        raise ContractError(
            f"{artifact} publication files differ: expected {sorted(expected)}, "
            f"found {sorted(existing)}"
        )

    pom_path = version_directory / f"{base}.pom"
    try:
        pom = ElementTree.parse(pom_path).getroot()
    except ElementTree.ParseError as error:
        raise ContractError(f"{artifact} POM is malformed") from error
    if (
        xml_text(pom, "groupId"),
        xml_text(pom, "artifactId"),
        xml_text(pom, "version"),
    ) != (GROUP, artifact, VERSION):
        raise ContractError(f"{artifact} POM has the wrong coordinate")
    if not xml_text(pom, "name") or not xml_text(pom, "description"):
        raise ContractError(f"{artifact} POM has incomplete name or description metadata")
    if xml_text(pom, "url") != "https://github.com/archivesteak/coil":
        raise ContractError(f"{artifact} POM has the wrong project URL")

    licenses = pom.find("{*}licenses")
    if licenses is None or not any(
        xml_text(license, "name") and xml_text(license, "url")
        for license in licenses.findall("{*}license")
    ):
        raise ContractError(f"{artifact} POM has incomplete license metadata")

    developers = pom.find("{*}developers")
    if developers is None or not any(
        (
            xml_text(developer, "id"),
            xml_text(developer, "name"),
            xml_text(developer, "url").rstrip("/"),
        )
        == (
            "archivesteak",
            "Jack Harrington",
            "https://github.com/archivesteak",
        )
        for developer in developers.findall("{*}developer")
    ):
        raise ContractError(f"{artifact} POM has the wrong fork developer metadata")

    scm = pom.find("{*}scm")
    if scm is None or (
        xml_text(scm, "url"),
        xml_text(scm, "connection"),
        xml_text(scm, "developerConnection"),
    ) != (
        "https://github.com/archivesteak/coil",
        "scm:git:https://github.com/archivesteak/coil.git",
        "scm:git:ssh://git@github.com/archivesteak/coil.git",
    ):
        raise ContractError(f"{artifact} POM has the wrong SCM URL")

    module_path = version_directory / f"{base}.module"
    module = load_json(module_path, f"{artifact} Gradle metadata")
    component = module.get("component")
    if not isinstance(component, dict) or (
        component.get("group"),
        component.get("module"),
        component.get("version"),
    ) != (GROUP, artifact, VERSION):
        raise ContractError(f"{artifact} Gradle metadata has the wrong component")
    variants = module.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ContractError(f"{artifact} Gradle metadata has no variants")

    pom_text = pom_path.read_text(encoding="utf-8")
    module_text = module_path.read_text(encoding="utf-8")
    for forbidden in (
        "io.coil-kt.coil3",
        "org.jetbrains.compose",
        "org.jetbrains.skiko",
    ):
        if forbidden in pom_text or forbidden in module_text:
            raise ContractError(
                f"{artifact} publication contains forbidden upstream coordinate {forbidden}"
            )
    for filename in (primary, f"{base}-sources.jar", f"{base}-javadoc.jar"):
        verify_archive(version_directory / filename)


def prepare_shard(
    *,
    owner: str,
    source_repository: Path,
    destination: Path,
    requirements_path: Path,
    coil_ref: str,
    resources_ref: str,
    core_report_path: Path,
    core_requirements_path: Path,
    resources_report_path: Path,
    resources_requirements_path: Path,
    plugin_report_path: Path,
) -> Path:
    source_repository = source_repository.resolve()
    if source_repository.is_symlink() or not source_repository.is_dir():
        raise ContractError(f"source Maven repository is invalid: {source_repository}")
    destination = destination.resolve()
    if destination.exists() or destination.is_symlink():
        raise ContractError(f"destination must be fresh and absent: {destination}")
    requirements, sources = validate_release_contract(
        repository=source_repository,
        requirements_path=requirements_path,
        coil_ref=coil_ref,
        resources_ref=resources_ref,
        core_report_path=core_report_path,
        core_requirements_path=core_requirements_path,
        resources_report_path=resources_report_path,
        resources_requirements_path=resources_requirements_path,
        plugin_report_path=plugin_report_path,
    )

    source_group = source_repository.joinpath(*GROUP.split("."))
    if source_group.is_symlink() or not source_group.is_dir():
        raise ContractError(f"source repository has no Coil group: {source_group}")
    artifacts = expected_artifacts(requirements, owner)
    existing_artifacts = {path.name for path in source_group.iterdir() if path.is_dir()}
    if existing_artifacts != artifacts:
        raise ContractError(
            f"{owner} Coil artifacts differ: expected {sorted(artifacts)}, "
            f"found {sorted(existing_artifacts)}"
        )

    destination_group = destination.joinpath(*GROUP.split("."))
    for artifact in sorted(artifacts):
        source_version = source_group / artifact / VERSION
        if not source_version.is_dir():
            raise ContractError(f"missing Coil publication: {artifact}:{VERSION}")
        ensure_tree_has_no_symlinks(source_version)
        validate_publication(source_version, artifact)
        shutil.copytree(source_version, destination_group / artifact / VERSION)

    marker = destination / "provenance" / f"{owner}.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps(
            {"schemaVersion": 1, "owner": owner, "sources": sources},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if {path.name for path in destination.iterdir()} != {"io", "provenance"}:
        raise ContractError("prepared Coil shard has unexpected root entries")
    return marker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=OWNERS)
    parser.add_argument("--source-repository", required=True, type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--coil-ref", required=True)
    parser.add_argument("--resources-ref", required=True)
    parser.add_argument("--core-report", required=True, type=Path)
    parser.add_argument("--core-requirements", required=True, type=Path)
    parser.add_argument("--resources-report", required=True, type=Path)
    parser.add_argument("--resources-requirements", required=True, type=Path)
    parser.add_argument("--plugin-report", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.validate_only:
            validate_release_contract(
                repository=args.source_repository,
                requirements_path=args.requirements,
                coil_ref=args.coil_ref,
                resources_ref=args.resources_ref,
                core_report_path=args.core_report,
                core_requirements_path=args.core_requirements,
                resources_report_path=args.resources_report,
                resources_requirements_path=args.resources_requirements,
                plugin_report_path=args.plugin_report,
            )
            print("validated exact Coil, resources, plugin, and core source contract")
            return 0
        if args.owner is None or args.destination is None:
            raise ContractError(
                "--owner and --destination are required unless --validate-only is used"
            )
        marker = prepare_shard(
            owner=args.owner,
            source_repository=args.source_repository,
            destination=args.destination,
            requirements_path=args.requirements,
            coil_ref=args.coil_ref,
            resources_ref=args.resources_ref,
            core_report_path=args.core_report,
            core_requirements_path=args.core_requirements,
            resources_report_path=args.resources_report,
            resources_requirements_path=args.resources_requirements,
            plugin_report_path=args.plugin_report,
        )
    except (ContractError, OSError, UnicodeError) as error:
        print(f"ERROR: {error}")
        return 1
    print(f"prepared exact Coil shard: {marker.parent.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
