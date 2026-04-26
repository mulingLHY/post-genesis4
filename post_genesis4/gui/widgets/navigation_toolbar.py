"""Custom navigation toolbar with copy functionality."""

from PyQt5 import QtWidgets, QtGui
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

class CopyableNavigationToolbar(NavigationToolbar):
    """
    Navigation toolbar with image copy functionality.

    Adds a button to copy the current figure to the clipboard.
    """

    toolitems = NavigationToolbar.toolitems + [
        ('Copy\nImg', 'Copy the figure to clipboard', 'copy', 'copy_figure'),
    ]

    def copy_figure(self):
        """Copy the current figure to the clipboard."""
        import io
        buf = io.BytesIO()
        self.canvas.figure.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)

        img = QtGui.QImage.fromData(buf.read())
        img = img.convertToFormat(QtGui.QImage.Format_RGB32)
        QtWidgets.QApplication.clipboard().setImage(img)
