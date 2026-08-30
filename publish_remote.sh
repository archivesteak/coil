#!/bin/bash
set -euo pipefail

if [[ "${COIL_REMOTE_PUBLICATION_ENABLED:-}" != "true" ]]; then
    echo "Remote publication is frozen. Set COIL_REMOTE_PUBLICATION_ENABLED=true only after release approval." >&2
    exit 1
fi

# Regenerate the baseline profile.
./gradlew generateBaselineProfile

# Build and upload the artifacts to 'mavenCentral'.
./gradlew publishToMavenCentral -Pcoil.remotePublication.enabled=true
