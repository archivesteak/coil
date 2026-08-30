package coil3.util

import kotlin.test.Test
import kotlin.test.assertEquals

class CacheSizesTest {

    @Test
    fun percentageOfBytesHandlesArithmeticBoundaries() {
        assertEquals(0, percentageOfBytes(0, 1.0))
        assertEquals(0, percentageOfBytes(Long.MAX_VALUE, 0.0))
        assertEquals(Long.MAX_VALUE, percentageOfBytes(Long.MAX_VALUE, 1.0))
        assertEquals(644_245_094, percentageOfBytes(4L * 1024L * 1024L * 1024L, 0.15))
    }

    @Test
    fun diskCacheSizeAppliesMinimumAndMaximumCaps() {
        val minimum = 10L * 1024L * 1024L
        val maximum = 250L * 1024L * 1024L
        assertEquals(minimum, diskCacheSize(0, 0.02, minimum, maximum))
        assertEquals(85_899_345, diskCacheSize(4L * 1024L * 1024L * 1024L, 0.02, minimum, maximum))
        assertEquals(maximum, diskCacheSize(Long.MAX_VALUE, 0.02, minimum, maximum))
    }
}
