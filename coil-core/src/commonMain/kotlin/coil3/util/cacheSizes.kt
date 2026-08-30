package coil3.util

internal fun percentageOfBytes(bytes: Long, percent: Double): Long {
    require(bytes >= 0) { "bytes must be >= 0." }
    require(percent in 0.0..1.0) { "percent must be in the range [0.0, 1.0]." }
    return (bytes.toDouble() * percent).toLong()
}

internal fun diskCacheSize(
    remainingFreeSpaceBytes: Long,
    percent: Double,
    minimumBytes: Long,
    maximumBytes: Long,
): Long {
    require(minimumBytes >= 0) { "minimumBytes must be >= 0." }
    require(maximumBytes >= minimumBytes) { "maximumBytes must be >= minimumBytes." }
    return percentageOfBytes(remainingFreeSpaceBytes.coerceAtLeast(0), percent)
        .coerceIn(minimumBytes, maximumBytes)
}
