"""Slice control widget for selecting plot slice position."""

import numpy as np
from PyQt5 import QtWidgets, QtCore

from post_genesis4.utils.log_utils import logger

import post_genesis4.gui as gui


class SliceControl(QtWidgets.QWidget):
    """
    Widget for controlling which slice of data to display.

    Allows users to select between s-axis and z-axis plotting,
    and choose the specific slice value via a slider.

    Attributes:
        ipypost4: Reference to the main IPyPostGenesis4 instance.
        plot_axis_x: Current plot axis ('s' or 'z').
        slice_value: Current slice value.
        _slice_at_z_idx: Current index in zplot array.
        _slice_at_s_idx: Current index in s_values array.
    """
    ipypost4: "gui.IPyPostGenesis4" = None

    _slice_at_z_idx: int = 0
    _slice_at_s_idx: int = 0

    _plot_axis_x_widget: QtWidgets.QButtonGroup = None
    __s_btn: QtWidgets.QPushButton = None
    __z_btn: QtWidgets.QPushButton = None
    _slice_value_slider: QtWidgets.QSlider = None
    _slice_value_label: QtWidgets.QLabel = None

    @property
    def plot_axis_x(self) -> str:
        """Get current plot axis ('s' or 'z')."""
        return self._plot_axis_x_widget.checkedButton().text() if self._plot_axis_x_widget else None

    @plot_axis_x.setter
    def plot_axis_x(self, value: str):
        """Set current plot axis."""
        if value not in ['s', 'z']:
            raise ValueError(f"Invalid plot_axis_x value: {value}")
        for btn in self._plot_axis_x_widget.buttons():
            if btn.text() == value:
                btn.setChecked(True)

    @property
    def current_x_data(self) -> np.ndarray:
        """Get current X-axis data array."""
        if self.plot_axis_x == 's':
            return self.ipypost4.s_values
        else:
            return self.ipypost4.zplot

    @property
    def slice_options(self) -> np.ndarray:
        """Get available slice values."""
        if self.plot_axis_x == 's':
            return self.ipypost4.zplot
        else:
            return self.ipypost4.s_values

    @property
    def slice_value(self) -> float:
        """Get current slice value."""
        if self.plot_axis_x == 's':
            return self.ipypost4.zplot[self._slice_at_z_idx]
        else:
            return self.ipypost4.s_values[self._slice_at_s_idx]

    @slice_value.setter
    def slice_value(self, value: float):
        """Set slice value by finding nearest index."""
        logger.debug(f"SliceControl.slice_value setter: value={value}")
        if self.plot_axis_x == 's':
            z_idx = np.argmin(np.abs(self.ipypost4.zplot - value))
            self._slice_at_z_idx = z_idx
            self._slice_value_slider.setValue(z_idx)
        else:
            s_idx = np.argmin(np.abs(self.ipypost4.s_values - value))
            self._slice_at_s_idx = s_idx
            self._slice_value_slider.setValue(s_idx)

    def __init__(self, ipypost4: "gui.IPyPostGenesis4"):
        """Initialize the widget UI components."""
        super().__init__()

        self.ipypost4 = ipypost4
        self.setLayout(QtWidgets.QHBoxLayout())

        # Plot axis selection buttons
        self._plot_axis_x_widget = QtWidgets.QButtonGroup()
        self.__s_btn = QtWidgets.QPushButton('s')
        self.__s_btn.setCheckable(True)
        self.__s_btn.setChecked(True)
        self.__z_btn = QtWidgets.QPushButton('z')
        self.__z_btn.setCheckable(True)
        self._plot_axis_x_widget.addButton(self.__s_btn, id=0)
        self._plot_axis_x_widget.addButton(self.__z_btn, id=1)
        self._plot_axis_x_widget.buttonToggled.connect(self.on_plot_axis_x_change)

        # Slider for slice selection
        self._slice_value_slider = QtWidgets.QSlider(orientation=QtCore.Qt.Horizontal)
        self._slice_value_slider.setMinimum(0)
        self._slice_value_slider.setMaximum(len(self.ipypost4.zplot)-1)
        self._slice_value_slider.setSingleStep(1)
        self._slice_value_slider.setPageStep(4)
        self._slice_value_slider.setValue(0)
        self._slice_value_slider.valueChanged.connect(self.on_slice_value_change)

        # Label showing current value
        self._slice_value_label = QtWidgets.QLabel("0.00")
        self._slice_value_label.setMinimumWidth(80)
        self._slice_value_label.setAlignment(QtCore.Qt.AlignCenter)

        # Plus/minus buttons for fine adjustment
        plus_widget = QtWidgets.QPushButton('+')
        plus_widget.clicked.connect(
            lambda: self._slice_value_slider.setValue(
                min(self._slice_value_slider.value() + 1, self._slice_value_slider.maximum()-1)
            )
        )
        minus_widget = QtWidgets.QPushButton('-')
        minus_widget.clicked.connect(
            lambda: self._slice_value_slider.setValue(
                max(self._slice_value_slider.value() - 1, 0)
            )
        )

        self.layout().addWidget(self.__s_btn)
        self.layout().addWidget(self.__z_btn)
        self.layout().addWidget(self._slice_value_slider)
        self.layout().addWidget(self._slice_value_label)
        self.layout().addWidget(minus_widget)
        self.layout().addWidget(plus_widget)

    def reinit(self):
        """Reinitialize widget when new data is loaded."""
        self._slice_value_slider.blockSignals(True)
        self._slice_value_slider.setMaximum(
            self.ipypost4.zplot.shape[0]-1 if self.plot_axis_x == 's'
            else self.ipypost4.s_values.shape[0]-1
        )
        self._slice_value_slider.blockSignals(False)
        self._slice_at_s_idx = min(self._slice_at_s_idx, len(self.ipypost4.s_values)-1)
        self._slice_at_z_idx = min(self._slice_at_z_idx, len(self.ipypost4.zplot)-1)

    def on_plot_axis_x_change(self, change: QtWidgets.QPushButton, checked: bool):
        """Handle plot axis change."""
        if not checked:
            return
        logger.debug(f"SliceControl.on_plot_axis_x_change: new value={change}")

        self._slice_value_slider.blockSignals(True)
        if change.text() == 's':
            self._slice_value_slider.setMaximum(len(self.ipypost4.zplot)-1)
            self._slice_value_slider.setValue(self._slice_at_z_idx)
        else:
            self._slice_value_slider.setMaximum(len(self.ipypost4.s_values)-1)
            self._slice_value_slider.setValue(self._slice_at_s_idx)

        self.ipypost4.plot_new_dataset()
        self._slice_value_slider.blockSignals(False)

        # Update label because after unobserve, the index may have changed
        if self.plot_axis_x == 's':
            self._slice_value_label.setText(f"{self.ipypost4.zplot[self._slice_at_z_idx]:.3f}")
        else:
            self._slice_value_label.setText(f"{self.ipypost4.s_values[self._slice_at_s_idx]:.3f}")

        logger.debug("SliceControl.on_plot_axis_x_change end")

    def on_slice_value_change(self, idx: int):
        """Handle slider value change."""
        if self.plot_axis_x == 's':
            logger.debug(f"SliceControl.on_slice_value_change: new value={self.ipypost4.zplot[idx]}")
            self._slice_at_z_idx = idx
            self._slice_value_label.setText(f"{self.ipypost4.zplot[idx]:.3f}")
        else:
            logger.debug(f"SliceControl.on_slice_value_change: new value={self.ipypost4.s_values[idx]}")
            self._slice_at_s_idx = idx
            self._slice_value_label.setText(f"{self.ipypost4.s_values[idx]:.3f}")

        self.ipypost4.update_plot_slice()
        logger.debug("SliceControl.on_slice_value_change end")
