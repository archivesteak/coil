#!/bin/bash
set -euo pipefail

if [[ "${COIL_REMOTE_PUBLICATION_ENABLED:-}" != "true" ]]; then
    echo "Remote publication is frozen. Set COIL_REMOTE_PUBLICATION_ENABLED=true only after release approval." >&2
    exit 1
fi
if [[ -z "${MAVEN_REPO_LOCAL:-}" ]]; then
    echo "Set MAVEN_REPO_LOCAL to the isolated repository directory." >&2
    exit 2
fi

gradle_args=("-Dmaven.repo.local=$MAVEN_REPO_LOCAL")

# Regenerate the baseline profile.
./gradlew "${gradle_args[@]}" generateBaselineProfile

# Build and upload the artifacts to 'mavenCentral'.
./gradlew "${gradle_args[@]}" publishToMavenCentral -Pcoil.remotePublication.enabled=true
