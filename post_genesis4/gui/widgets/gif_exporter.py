"""GIF export widget for creating animations."""

import numpy as np
from PyQt5 import QtWidgets, QtGui

import post_genesis4.gui as gui


class GifExporter(QtWidgets.QWidget):
    """
    Widget for exporting plot animations as GIF files.

    Provides controls for selecting frame range, step size, timing,
    and output path for GIF generation.

    Attributes:
        ipypost4: Reference to main application instance.
        export_dialog: Waiting dialog shown during export.
    """

    def __init__(self, ipypost4: "gui.IPyPostGenesis4"):
        """
        Initialize GIF exporter widget.

        Args:
            ipypost4: Main application instance.
        """
        self.ipypost4 = ipypost4

        self.export_dialog = None
        self.export_btn: QtWidgets.QPushButton = None
        self.text_from: QtWidgets.QLineEdit = None
        self.text_to: QtWidgets.QLineEdit = None
        self.text_step: QtWidgets.QLineEdit = None
        self.text_interval: QtWidgets.QLineEdit = None
        self.text_pausetime: QtWidgets.QLineEdit = None
        self.text_path: QtWidgets.QLineEdit = None

        super().__init__()
        self.setLayout(QtWidgets.QHBoxLayout())

        self.export_dialog = WaitingDialog(self, "Exporting GIF", "Writing GIF to file...")

        self.export_btn = QtWidgets.QPushButton('export gif')
        self.export_btn.released.connect(self.export_gif)
        self.layout().addWidget(self.export_btn)

        self.text_from = QtWidgets.QLineEdit('0')
        self.text_from.setValidator(QtGui.QDoubleValidator())
        self.text_from.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('From:'))
        self.layout().addWidget(self.text_from)

        self.text_to = QtWidgets.QLineEdit('30')
        self.text_to.setValidator(QtGui.QDoubleValidator())
        self.text_to.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('To:'))
        self.layout().addWidget(self.text_to)

        self.text_step = QtWidgets.QLineEdit('4')
        self.text_step.setValidator(QtGui.QIntValidator())
        self.text_step.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('Step(index):'))
        self.layout().addWidget(self.text_step)

        self.text_interval = QtWidgets.QLineEdit('50')
        self.text_interval.setValidator(QtGui.QIntValidator())
        self.text_interval.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('Interval(ms):'))
        self.layout().addWidget(self.text_interval)

        self.text_pausetime = QtWidgets.QLineEdit('500')
        self.text_pausetime.setValidator(QtGui.QIntValidator())
        self.text_pausetime.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('Pause(ms):'))
        self.layout().addWidget(self.text_pausetime)

        self.text_path = QtWidgets.QLineEdit('ipygenesis4.gif')
        self.text_path.setMinimumWidth(400)
        self.layout().addWidget(QtWidgets.QLabel('Path:'))
        self.layout().addWidget(self.text_path)

    def update_plot_slice(self, value: float):
        """
        Update plot to specified slice value (used as animation frame callback).

        Args:
            value: Slice value to display.
        """
        self.ipypost4.slice_control.slice_value = value
        QtWidgets.QApplication.processEvents()
        return

    def export_gif(self):
        """Export current plot as animated GIF."""
        import matplotlib.animation as animation

        slice_options = self.ipypost4.slice_control.slice_options
        start_idx = np.argmin(np.abs(slice_options - float(self.text_from.text())))
        end_idx = np.argmin(np.abs(slice_options - float(self.text_to.text())))
        frames = slice_options[start_idx:(end_idx+1):int(self.text_step.text())]
        frames = np.append(
            frames,
            [slice_options[end_idx]] * int(abs(int(self.text_pausetime.text())/int(self.text_interval.text())) + 1)
        )

        ani = animation.FuncAnimation(
            self.ipypost4.fig, self.update_plot_slice, repeat=False,
            frames=frames, interval=float(self.text_interval.text())
        )

        self.export_dialog.show()

        ani.save(
            self.text_path.text(), writer='pillow',
            progress_callback=lambda i, n: i+1 == n or QtWidgets.QApplication.processEvents()
        )
        del ani

        self.export_dialog.accept()


# Import here to avoid circular dependency
from post_genesis4.gui.widgets.waiting_dialog import WaitingDialog
