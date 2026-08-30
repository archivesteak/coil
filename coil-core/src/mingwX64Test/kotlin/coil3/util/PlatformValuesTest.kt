@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package coil3.util

import coil3.PlatformContext
import kotlin.math.absoluteValue
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.cinterop.alloc
import kotlinx.cinterop.convert
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.sizeOf
import okio.FileSystem
import platform.windows.GetDiskFreeSpaceExW
import platform.windows.GlobalMemoryStatusEx
import platform.windows.MEMORYSTATUSEX
import platform.windows.ULARGE_INTEGER

class PlatformValuesTest {

    @Test
    fun totalMemoryMatchesWindowsPhysicalMemory() = memScoped {
        val status = alloc<MEMORYSTATUSEX>()
        status.dwLength = sizeOf<MEMORYSTATUSEX>().convert()
        assertTrue(GlobalMemoryStatusEx(status.ptr) != 0)
        val expected = status.ullTotalPhys.coerceAtMost(Long.MAX_VALUE.toULong()).toLong()

        assertTrue(expected > 0)
        assertEquals(expected, PlatformContext.INSTANCE.totalAvailableMemoryBytes())
    }

    @Test
    fun freeSpaceTracksTheTemporaryDirectoryVolume() = memScoped {
        val directory = FileSystem.SYSTEM_TEMPORARY_DIRECTORY
        val actual = FileSystem.SYSTEM.remainingFreeSpaceBytes(directory)
        val availableToCaller = alloc<ULARGE_INTEGER>()
        assertTrue(
            GetDiskFreeSpaceExW(
                directory.toString(),
                availableToCaller.ptr,
                null,
                null,
            ) != 0,
        )
        val expected = availableToCaller.QuadPart.coerceAtMost(Long.MAX_VALUE.toULong()).toLong()

        assertTrue(actual > 0)
        assertTrue((actual - expected).absoluteValue <= 128L * 1024L * 1024L)
    }
}
