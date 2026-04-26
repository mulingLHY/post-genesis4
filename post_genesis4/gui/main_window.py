"""
Main application window for post-genesis4.

This module contains the PostGenesis4MainWindow class which provides
the main user interface for loading and visualizing Genesis output files.
"""

import os
import time
from typing import List, Optional

import h5py
from PyQt5 import QtWidgets, QtCore

from post_genesis4.utils.log_utils import logger
from post_genesis4.utils.file_reader import SyncQtApplicationFileReader
from post_genesis4.utils.genesis2_utils import convert_genesis2_output_to_genesis4_hdf5
from post_genesis4.gui.core_pannel import IPyPostGenesis4, IPyPostGenesis4Builder
from post_genesis4.gui.metadata_window import Genesis4MetaDataWindow
from post_genesis4.gui.widgets import WaitingDialog



# Help text displayed when no file is loaded
TIP_TEXT = """
This is a PyQt5 GUI application for visualizing the output of Genesis1.3-Version4 and Genesis1.3-Version2 (experimentally supports).

With file input box empty, `Open` button will open a file dialog to select one or more Genesis output file.
You can also input a Genesis output file path in the file input box, and then click `Open` button to load the data.



If the output files are located on a server, you can use SSH with X11 forwarding to run the application on the server and display it on your local machine.  To do this, you can

- using terminal like `MobaXterm`
- install x11-server like `Xming` on the local machine

But it is recommended to mount the server directory to your local machine with `SFTP` using softwares like `RaiDrive` or `WinFsp`.

- RaiDrive: Add -> NAS -> SFTP



To use this application, you need to have the following dependencies installed:

- PyQt5
- h5py
- numpy
- matplotlib
- scipy
"""


class PostGenesis4MainWindow(QtWidgets.QMainWindow):
    """
    Main application window for Genesis4 visualization.

    Provides file selection, history management, and hosts the main
    visualization widget.

    Attributes:
        h5_file: Currently opened HDF5 file.
        f_gui: File reader wrapper.
        _post_widget: Main visualization widget.
        post_builder: Data builder for current file.
        meta_data_window: Metadata display window.
    """

    def __init__(self, parent=None):
        """Initialize main window."""
        super(PostGenesis4MainWindow, self).__init__(parent)
        self.setWindowTitle('PyPostGenesis4')
        self.resize(1650, 1150)

        # State variables
        self.h5_file: Optional[h5py.File] = None
        self.f_gui: Optional[SyncQtApplicationFileReader] = None
        self._post_widget: Optional[IPyPostGenesis4] = None
        self.post_builder: Optional[IPyPostGenesis4Builder] = None

        # Main widget and layout
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)

        # Waiting dialog for file operations
        self.wait_file_dialog = WaitingDialog(
            self, 'Waiting for file loading...', 'Loading Genesis4 output file...'
        )
        self.wait_file_thread = QtCore.QThread()
        self.wait_file_thread.run = self.select_history_file
        self.wait_file_thread.started.connect(self.wait_file_dialog.show)
        self.wait_file_thread.finished.connect(self.wait_file_dialog.accept)

        # File input controls
        self.file_input = QtWidgets.QLineEdit()
        self.file_input.setMinimumWidth(300)
        self.file_input.setPlaceholderText('Enter file path')

        self.file_history_widget = QtWidgets.QComboBox()
        self.file_history_widget.setMinimumWidth(800)
        self.file_history_widget.currentTextChanged.connect(self.wait_file_thread.start)

        # Buttons
        self.file_button = QtWidgets.QPushButton('Open')
        self.file_reopen_button = QtWidgets.QPushButton('Reopen')
        self.file_clear_other_button = QtWidgets.QPushButton('Clear')
        self.file_button.clicked.connect(self.open_input_file)
        self.file_reopen_button.clicked.connect(self.wait_file_thread.start)
        self.file_clear_other_button.clicked.connect(self.file_history_widget.clear)

        # Meta data button and window
        self.btn_meta_data = QtWidgets.QPushButton('Meta')
        self.meta_data_window = Genesis4MetaDataWindow()
        self.btn_meta_data.clicked.connect(self.show_meta_data)

        # File selection layout
        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_layout.addWidget(QtWidgets.QLabel('Input file:'))
        self.file_layout.addWidget(self.file_input)
        self.file_layout.addWidget(self.file_history_widget)
        self.file_layout.addWidget(self.file_button)
        self.file_layout.addWidget(self.file_reopen_button)
        self.file_layout.addWidget(self.btn_meta_data)
        self.file_layout.addWidget(self.file_clear_other_button)
        self.main_layout.addLayout(self.file_layout)

        # Tip label (shown when no file is loaded)
        self.post_layout = QtWidgets.QHBoxLayout()
        self.tip_label = QtWidgets.QLabel(TIP_TEXT)
        self.tip_label.setStyleSheet("QLabel { font-size: 26px; font-family: Times New Roman; }")
        self.tip_label.setContentsMargins(60, 30, 60, 10)
        self.tip_label.setWordWrap(True)
        self.post_layout.addWidget(self.tip_label)
        self.main_layout.addLayout(self.post_layout)

    def show_meta_data(self):
        """Show metadata window if a file is loaded."""
        if self.h5_file:
            self.meta_data_window.show()
            self.meta_data_window.activateWindow()

    def open_input_file(self):
        """Handle file open button click."""
        if self.file_input.text():
            # Use text from input field
            fileName = self.file_input.text()
            fileName = fileName.strip("\"").strip()

            if not os.path.isfile(fileName):
                QtWidgets.QMessageBox.warning(self, 'Warning', f'File not found: {fileName}')
                return

            if not fileName.endswith('.out') and not fileName.endswith('.out.h5'):
                QtWidgets.QMessageBox.warning(self, 'Warning', f'File type not supported: {fileName}')
                return

            self.add_file_history([fileName])
            self.file_input.clear()
        else:
            # Open file dialog
            options = QtWidgets.QFileDialog.Options()
            fileName, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, "Select file", "", "Genesis2/4 (*.out *.out.h5)", options=options
            )
            logger.debug(f"Selected files: {fileName}")

            if fileName:
                self.add_file_history(fileName)

    def add_file_history(self, strlist: List[str]):
        """
        Add files to history dropdown.

        Args:
            strlist: List of file paths to add.
        """
        # Remove duplicates
        [self.file_history_widget.removeItem(self.file_history_widget.findText(s))
         for s in strlist if self.file_history_widget.findText(s) >= 0]
        self.file_history_widget.addItems(strlist)
        self.file_history_widget.setCurrentText(strlist[0])

    def select_history_file(self):
        """Load the selected file from history (runs in worker thread)."""
        path = self.file_history_widget.currentText()
        if not path:
            return

        logger.debug(f'select_history_file: {path}')

        # Close previous file
        if self.h5_file:
            self.h5_file.close()        
        if self.f_gui:
            self.f_gui.close()

        # Handle Genesis2 .out files (convert to HDF5 if needed)
        if path.endswith('.out'):
            hdf5_path = path + '.ipypostgenesis4.out.h5'
            if not os.path.isfile(hdf5_path) or os.path.getmtime(path) > os.path.getmtime(hdf5_path):
                QtCore.QMetaObject.invokeMethod(
                    self.wait_file_dialog.message, "setText",
                    QtCore.Q_ARG(str, "Converting Genesis2 output to Genesis4 format...")
                )
                os.utime(path, (time.time(), time.time()))  # Update timestamp
                convert_genesis2_output_to_genesis4_hdf5(path, hdf5_path)
                QtWidgets.QApplication.processEvents()

            path = hdf5_path

        QtCore.QMetaObject.invokeMethod(
            self.wait_file_dialog.message, "setText",
            QtCore.Q_ARG(str, "Reading Genesis4 output file...")
        )

        # Open HDF5 file with non-blocking reader
        self.f_gui = SyncQtApplicationFileReader(path)
        try:
            self.h5_file = h5py.File(self.f_gui, 'r', locking=False)
        except TypeError as e:
            logger.error(e)
            self.h5_file = h5py.File(self.f_gui, 'r')

        self.post_builder = IPyPostGenesis4Builder(self.h5_file)

        # Update metadata window
        QtCore.QMetaObject.invokeMethod(
            self.meta_data_window, "set_meta_data",
            QtCore.Q_ARG("PyQt_PyObject", Genesis4MetaDataWindow.parse_meta_data(self.h5_file)),
            QtCore.Q_ARG(str, path)
        )

        # Update main visualization
        QtCore.QMetaObject.invokeMethod(self, "update_ipypostgenesis4_layout")

    @QtCore.pyqtSlot()
    def update_ipypostgenesis4_layout(self):
        """Update or create the main visualization widget."""
        if not self._post_widget:
            self._post_widget = IPyPostGenesis4(self.post_builder)
            self.tip_label.hide()
            self.post_layout.addWidget(self._post_widget)
        else:
            self._post_widget.reinit(self.post_builder)
