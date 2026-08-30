#!/bin/bash
set -euo pipefail

# Build and install only the dependency-closed MinGW producer set to an explicitly isolated local
# Maven repository. settings.gradle.kts validates that this path is absolute, exists, and is not
# inside the ambient ~/.m2 directory.
if [[ -z "${MAVEN_REPO_LOCAL:-}" ]]; then
    echo "Set MAVEN_REPO_LOCAL to the isolated repository directory." >&2
    exit 2
fi

./gradlew "-Dmaven.repo.local=$MAVEN_REPO_LOCAL" publishMingwClosureToMavenLocal
