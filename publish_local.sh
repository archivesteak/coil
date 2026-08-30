#!/bin/bash
set -euo pipefail

# Build and install only the dependency-closed MinGW producer set to mavenLocal.
./gradlew publishMingwClosureToMavenLocal
