@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package coil3.util

import coil3.PlatformContext
import kotlinx.cinterop.alloc
import kotlinx.cinterop.convert
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.sizeOf
import okio.FileSystem
import okio.IOException
import okio.Path
import platform.windows.GetDiskFreeSpaceExW
import platform.windows.GetLastError
import platform.windows.GlobalMemoryStatusEx
import platform.windows.MEMORYSTATUSEX
import platform.windows.ULARGE_INTEGER

internal actual fun PlatformContext.totalAvailableMemoryBytes(): Long = memScoped {
    val status = alloc<MEMORYSTATUSEX>()
    status.dwLength = sizeOf<MEMORYSTATUSEX>().convert()
    if (GlobalMemoryStatusEx(status.ptr) == 0) {
        throw IllegalStateException("GlobalMemoryStatusEx failed with Win32 error ${GetLastError()}.")
    }
    status.ullTotalPhys.toSafeByteCount()
}

internal actual fun FileSystem.remainingFreeSpaceBytes(directory: Path): Long {
    createDirectories(directory)
    return memScoped {
        val availableToCaller = alloc<ULARGE_INTEGER>()
        val succeeded = GetDiskFreeSpaceExW(
            directory.toString(),
            availableToCaller.ptr,
            null,
            null,
        )
        if (succeeded == 0) {
            throw IOException(
                "GetDiskFreeSpaceExW failed for '$directory' with Win32 error ${GetLastError()}.",
            )
        }
        availableToCaller.QuadPart.toSafeByteCount()
    }
}

private fun ULong.toSafeByteCount(): Long {
    return coerceAtMost(Long.MAX_VALUE.toULong()).toLong()
}
