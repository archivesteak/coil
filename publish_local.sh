#!/bin/bash
set -euo pipefail

# Build and install one exact dependency-closed host shard to an explicitly isolated local Maven
# repository. settings.gradle.kts validates that this path is absolute, exists, and is not inside
# the ambient ~/.m2 directory.
if [[ -z "${MAVEN_REPO_LOCAL:-}" ]]; then
    echo "Set MAVEN_REPO_LOCAL to the isolated repository directory." >&2
    exit 2
fi
case "${MAVEN_PUBLICATION_OWNER:-}" in
    windows) aggregate=publishWindowsClosureToMavenLocal ;;
    apple) aggregate=publishAppleClosureToMavenLocal ;;
    web) aggregate=publishWebClosureToMavenLocal ;;
    *)
        echo "Set MAVEN_PUBLICATION_OWNER to windows, apple, or web." >&2
        exit 2
        ;;
esac

./gradlew "-Dmaven.repo.local=$MAVEN_REPO_LOCAL" \
    "-Pcoil.localPublication.owner=$MAVEN_PUBLICATION_OWNER" \
    "$aggregate"
