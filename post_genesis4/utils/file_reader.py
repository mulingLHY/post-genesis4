"""File reader with Qt event processing to avoid GUI blocking."""

from PyQt5 import QtWidgets

from post_genesis4.utils.log_utils import logger


class SyncQtApplicationFileReader:
    """
    File reader that processes Qt events during large reads.

    This class wraps a file object and calls QApplication.processEvents()
    periodically during large read operations to keep the GUI responsive.
    """

    largeread_update_gui_bytes = 32 * 1024   # Process events every 32KB
    smallread_threshold_bytes = 1024         # Reads below this are considered small

    def __init__(self, path: str):
        self.__file = open(path, 'rb')
        self.total_read = 0

    def read(self, n: int) -> bytes:
        """
        Read n bytes from file, processing Qt events for large reads.

        Args:
            n: Number of bytes to read.

        Returns:
            Bytes read from file.
        """
        logger.debug(f'SyncQtApplicationFileReader read {n} bytes')

        if n <= self.smallread_threshold_bytes:
            return self.__file.read(n)

        data = bytearray()
        remaining = n

        while remaining > 0:
            read_size = min(remaining, self.largeread_update_gui_bytes)
            chunk = self.__file.read(read_size)
            if not chunk:
                break

            data += chunk
            remaining -= len(chunk)
            self.total_read += len(chunk)

            # Process Qt events to keep GUI responsive
            QtWidgets.QApplication.processEvents()

        return bytes(data)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.__file.seek(offset, whence)

    def close(self) -> None:
        self.__file.close()

    def tell(self) -> int:
        return self.__file.tell()
