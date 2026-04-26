"""
File I/O and conversion utilities for Genesis4 files.

This package handles reading Genesis2 .out files, converting them to
Genesis4 HDF5 format, and non-blocking file operations.
"""

from post_genesis4.utils.file_reader import SyncQtApplicationFileReader
from post_genesis4.utils.genesis2_utils import (
    _read_genesis2_out,
    convert_genesis2_output_to_genesis4_hdf5,
)

__all__ = [
    "SyncQtApplicationFileReader",
    "_read_genesis2_out",
    "convert_genesis2_output_to_genesis4_hdf5",
]
