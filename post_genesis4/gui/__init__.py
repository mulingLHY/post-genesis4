"""
GUI controllers for Genesis4 visualization.

This package contains the main application window and the core
visualization controller that coordinates all plotting widgets.
"""

from post_genesis4.gui.core_pannel import IPyPostGenesis4, default_plot_config
from post_genesis4.gui.main_window import PostGenesis4MainWindow
from post_genesis4.gui.metadata_window import Genesis4MetaDataWindow

__all__ = [
    "IPyPostGenesis4",
    "default_plot_config",
    "PostGenesis4MainWindow",
    'Genesis4MetaDataWindow',
]
