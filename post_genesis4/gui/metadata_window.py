"""Meta data window for displaying Genesis4 file metadata."""

from typing import Dict

import h5py
from PyQt5 import QtWidgets, QtCore


class Genesis4MetaDataWindow(QtWidgets.QWidget):
    """
    Window for displaying metadata from Genesis4 HDF5 files.

    Shows parsed metadata organized by category (Overview, InputFile, etc.)
    in a readable text browser.

    Attributes:
        meta_data: Dictionary of metadata organized by category.
    """

    meta_data: Dict[str, str] = {}

    def __init__(self):
        """Initialize metadata window."""
        super().__init__()
        self.setWindowTitle('Genesis4 MetaData')
        self.resize(1000, 1000)

        self.__meta_category_widget = QtWidgets.QButtonGroup(self)
        self.__meta_category_widget.setExclusive(True)
        self.__meta_category_widget.buttonToggled.connect(
            lambda btn, checked: self.__meta_text.setText(self.meta_data[btn.text()])
        )

        self.__meta_category_layout = QtWidgets.QHBoxLayout()

        self.__meta_text = QtWidgets.QTextBrowser()
        self.__meta_text.setFontPointSize(15)
        self.__meta_text.setFontFamily('Consolas')
        self.__meta_text.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

        self.__path_text = QtWidgets.QLineEdit()
        self.__path_text.setReadOnly(True)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.__path_text)
        self.layout().addLayout(self.__meta_category_layout)
        self.layout().addWidget(self.__meta_text)

    @QtCore.pyqtSlot(dict, str)
    def set_meta_data(self, meta_data: Dict[str, str], path: str):
        """
        Set and display metadata.

        Args:
            meta_data: Dictionary mapping category names to metadata strings.
            path: Path to the HDF5 file.
        """
        from post_genesis4.utils.log_utils import logger
        logger.debug(f'Genesis4MetaDataWindow.set_meta_data: meta_data={meta_data}')

        # Clear existing category buttons
        for btn in self.__meta_category_widget.buttons():
            self.__meta_category_widget.removeButton(btn)
            self.__meta_category_layout.removeWidget(btn)
            del btn

        self.meta_data = meta_data

        # Create buttons for each category
        for category in meta_data.keys():
            btn = QtWidgets.QPushButton(category)
            btn.setCheckable(True)
            self.__meta_category_widget.addButton(btn)
            self.__meta_category_layout.addWidget(btn)

            if category == 'Overview':
                btn.setChecked(True)

        if len(meta_data) == 0:
            self.__meta_text.setText('No MetaData in this file')

        self.__path_text.setText(path)

    @staticmethod
    def parse_meta_data(h5_file: h5py.File) -> Dict[str, str]:
        """
        Parse metadata from an HDF5 file.

        Args:
            h5_file: Opened h5py File object.

        Returns:
            Dictionary mapping category names to formatted metadata strings.
        """
        meta_data = {}
        if '/Meta' not in h5_file.keys():
            return meta_data

        meta_data['Overview'] = Genesis4MetaDataWindow.__parse_meta_dataset(h5_file['/Meta/'])

        if 'InputFile' in h5_file['/Meta'].keys():
            meta_data['InputFile'] = str(h5_file['/Meta/InputFile'][0], encoding='utf-8')

        if 'LatticeFile' in h5_file['/Meta'].keys():
            meta_data['LatticeFile'] = str(h5_file['/Meta/LatticeFile'][0], encoding='utf-8')

        return meta_data

    @staticmethod
    def __parse_meta_dataset(obj, result: str = '') -> str:
        """
        Recursively parse metadata from HDF5 groups and datasets.

        Args:
            obj: HDF5 group, file, or dataset object.
            result: Accumulated result string.

        Returns:
            Formatted metadata string.
        """
        if isinstance(obj, (h5py.Group, h5py.File)):
            for v in obj.values():
                result += Genesis4MetaDataWindow.__parse_meta_dataset(v)
        elif isinstance(obj, h5py.Dataset):
            if "InputFile" in obj.name or "LatticeFile" in obj.name:
                result += obj.name.replace('/Meta/', '') + ": ..." + "\n"
            else:
                result += obj.name.replace('/Meta/', '') + ": "
                result += str(obj[0], encoding='utf-8') if obj.dtype.kind == 'S' else str(obj[0])
                result += "\n"
        return result
