"""Waiting dialog widget for showing progress during blocking operations."""

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt


class WaitingDialog(QtWidgets.QDialog):
    """
    A modal dialog showing an indeterminate progress indicator.

    Used during file loading and data processing to prevent user interaction
    and provide visual feedback.

    Attributes:
        message: QLabel displaying the status message.
        progress: QProgressBar showing indeterminate progress.
    """

    def __init__(self, parent=None, title="Waiting...", message="Waiting..."):
        """
        Initialize the waiting dialog.

        Args:
            parent: Parent widget.
            title: Window title.
            message: Message to display.
        """
        super().__init__(parent=parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(600, 200)

        self.setLayout(QtWidgets.QVBoxLayout(self))
        self.message = QtWidgets.QLabel(message, self)
        self.layout().addWidget(self.message, alignment=Qt.AlignCenter)

        self.progress = QtWidgets.QProgressBar(self)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setRange(0, 0)  # Indeterminate mode
        self.layout().addWidget(self.progress)
