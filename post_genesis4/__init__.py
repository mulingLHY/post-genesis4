"""
Post-Genesis4: A PyQt5 GUI application for visualizing Genesis4 output files.

This package provides tools for visualizing and analyzing output from
Genesis1.3-Version4 and Genesis1.3-Version2 (experimentally supported).
"""

from importlib.metadata import version, metadata

__version__ = version("post-genesis4")
__author__ = metadata("post-genesis4")["Author"]

from post_genesis4.cli import show

__all__ = ["show"]
