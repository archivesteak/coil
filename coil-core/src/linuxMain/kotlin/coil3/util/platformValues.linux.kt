package coil3.util

import coil3.PlatformContext
import okio.FileSystem
import okio.Path

internal actual fun PlatformContext.totalAvailableMemoryBytes(): Long {
    return 512L * 1024L * 1024L // Preserve Coil's upstream non-JVM fallback.
}

internal actual fun FileSystem.remainingFreeSpaceBytes(directory: Path): Long {
    return 4L * 1024L * 1024L * 1024L // Preserve Coil's upstream non-JVM fallback.
}
