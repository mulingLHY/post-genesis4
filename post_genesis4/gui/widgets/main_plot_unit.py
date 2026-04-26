"""Main plot unit widget for displaying Genesis data."""

from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker
from PyQt5 import QtWidgets

from post_genesis4.utils.log_utils import logger
from post_genesis4.utils.math_utils import fwhm
from post_genesis4.gui.widgets.slice_control import SliceControl

import post_genesis4.gui as gui


class MainPlotUnit(QtWidgets.QWidget):
    """
    Widget for plotting a single dataset from Genesis output.

    Handles data fetching, plotting, and UI controls for one curve.
    Supports features like averaging, max display, log scale, and peak finding.

    Attributes:
        ipypost4: Reference to main application instance.
        slice_control: Reference to slice control widget.
        color: Plot line color.
        ax: Matplotlib axes for plotting.
        line: Main plot line.
        avg_line: Average line (optional).
        max_line: Maximum line (optional).
        label: Plot label identifier.
        data: Current data array.
        data_unit: Unit string for the data.
        data_tag: HDF5 path tag for current data.
    """
    ipypost4: "gui.IPyPostGenesis4" = None
    slice_control: SliceControl = None
    color: str = "grey"
    label: str = None

    ax: plt.Axes = None
    line: plt.Line2D = None
    avg_line: plt.Line2D = None
    max_line: plt.Line2D = None

    data: Optional[np.ndarray] = None
    data_unit: str = 'a.u.'
    data_tag: Optional[str] = None

    _h5group_widget: QtWidgets.QButtonGroup = None
    _h5dataset_widget: QtWidgets.QComboBox = None
    _h5group_layout: QtWidgets.QHBoxLayout = None

    _avg_over_s_checkbox: QtWidgets.QCheckBox = None
    _max_over_s_checkbox: QtWidgets.QCheckBox = None
    _log_y_scale_checkbox: QtWidgets.QCheckBox = None
    _find_peak_checkbox: QtWidgets.QCheckBox = None
    _y_zero_line_checkbox: QtWidgets.QCheckBox = None

    peak_text: Optional[plt.Text] = None
    yzero_line: Optional[plt.Line2D] = None

    unit_formatter: matplotlib.ticker.Formatter = None
    unit_factor: float = 1
    unit_prefix: str = ""

    @property
    def h5group(self) -> str:
        """Get selected HDF5 group."""
        return self.ipypost4.h5group_options[self._h5group_widget.checkedId()] if self._h5group_widget else None

    @h5group.setter
    def h5group(self, value: str):
        """Set HDF5 group by name."""
        if value not in self.ipypost4.h5group_options:
            raise ValueError(f"Invalid h5group value: {value}")
        self._h5group_widget.buttons()[self.ipypost4.h5group_options.index(value)].setChecked(True)

    @property
    def h5dataset(self) -> str:
        """Get selected HDF5 dataset."""
        return self._h5dataset_widget.currentText() if self._h5dataset_widget else None

    @h5dataset.setter
    def h5dataset(self, value: str):
        """Set HDF5 dataset by name."""
        if value not in self.ipypost4.dataset_in_groups[self.h5group]:
            raise ValueError(f"Invalid h5dataset value: {value}")
        self._h5dataset_widget.setCurrentText(value)

    @property
    def avg_over_s(self) -> bool:
        """Get average over s checkbox state."""
        return self._avg_over_s_checkbox.isChecked()

    @avg_over_s.setter
    def avg_over_s(self, value: bool):
        """Set average over s checkbox state."""
        self._avg_over_s_checkbox.setChecked(value)

    @property
    def max_over_s(self) -> bool:
        """Get max over s checkbox state."""
        return self._max_over_s_checkbox.isChecked()

    @max_over_s.setter
    def max_over_s(self, value: bool):
        """Set max over s checkbox state."""
        self._max_over_s_checkbox.setChecked(value)

    @property
    def log_y_scale(self) -> bool:
        """Get log y-scale checkbox state."""
        return self._log_y_scale_checkbox.isChecked()

    @log_y_scale.setter
    def log_y_scale(self, value: bool):
        """Set log y-scale checkbox state."""
        self._log_y_scale_checkbox.setChecked(value)

    @property
    def find_peak(self) -> bool:
        """Get find peak checkbox state."""
        return self._find_peak_checkbox.isChecked()

    @find_peak.setter
    def find_peak(self, value: bool):
        """Set find peak checkbox state."""
        self._find_peak_checkbox.setChecked(value)

    def __init__(self, ipypost4: "gui.IPyPostGenesis4", ax: plt.Axes, slice_control: SliceControl, color: str, label: str):
        """Initialize widget UI components."""
        super().__init__()

        self.ipypost4 = ipypost4
        self.ax = ax
        self.slice_control = slice_control
        self.color = color
        self.label = label

        self.ax.figure.canvas.mpl_connect('draw_event', lambda event: self.update_text_visiable(event))

        self.setLayout(QtWidgets.QVBoxLayout())
        self._h5group_widget = QtWidgets.QButtonGroup(self)
        self._h5group_widget.setExclusive(True)

        for i in range(len(self.ipypost4.h5group_options)):
            btn = QtWidgets.QPushButton(self.ipypost4.h5group_options[i], self)
            btn.setFixedWidth(90)
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)
            self._h5group_widget.addButton(btn, i)

        self._h5group_widget.buttonToggled.connect(self.on_group_change)

        self._h5dataset_widget = QtWidgets.QComboBox()
        self._h5dataset_widget.addItems(self.ipypost4.dataset_in_groups[self.h5group])
        self._h5dataset_widget.setCurrentText(self.ipypost4.dataset_in_groups["Beam"][0])
        self._h5dataset_widget.currentTextChanged.connect(self.on_dataset_change)

        layout = QtWidgets.QHBoxLayout()
        self._h5group_layout = QtWidgets.QHBoxLayout()
        for btn in self._h5group_widget.buttons():
            self._h5group_layout.addWidget(btn)
        layout.addLayout(self._h5group_layout)
        layout.addWidget(self._h5dataset_widget)
        self.layout().addLayout(layout)

        # Control checkboxes
        self._avg_over_s_checkbox = QtWidgets.QCheckBox("Avg. over s")
        self._avg_over_s_checkbox.stateChanged.connect(lambda: self.ipypost4.plot_new_dataset())
        self._max_over_s_checkbox = QtWidgets.QCheckBox("Max. over s")
        self._max_over_s_checkbox.stateChanged.connect(lambda: self.ipypost4.plot_new_dataset())
        self._log_y_scale_checkbox = QtWidgets.QCheckBox("Log y-scale")
        self._log_y_scale_checkbox.stateChanged.connect(lambda: self.ipypost4.update_plot_slice())

        self._find_peak_checkbox = QtWidgets.QCheckBox("Find Peak")
        self._find_peak_checkbox.stateChanged.connect(lambda: self.ipypost4.update_plot_slice())

        self._y_zero_line_checkbox = QtWidgets.QCheckBox("Line y=0")
        self._y_zero_line_checkbox.stateChanged.connect(
            lambda: (self.ipypost4.update_plot_slice(), self.ipypost4.fig.canvas.draw_idle())
        )

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._avg_over_s_checkbox)
        layout.addWidget(self._max_over_s_checkbox)
        layout.addWidget(self._log_y_scale_checkbox)
        layout.addWidget(self._find_peak_checkbox)
        layout.addWidget(self._y_zero_line_checkbox)
        self.layout().addLayout(layout)

    def reinit(self):
        """Reinitialize widget when new data is loaded."""
        self.data_tag = None

        self._h5group_widget.blockSignals(True)
        ptext = ''
        for btn in self._h5group_widget.buttons():
            if btn.isChecked():
                ptext = btn.text()
            self._h5group_widget.removeButton(btn)
            self._h5group_layout.removeWidget(btn)
            del btn

        for i in range(len(self.ipypost4.h5group_options)):
            btn = QtWidgets.QPushButton(self.ipypost4.h5group_options[i], self)
            btn.setFixedWidth(90)
            btn.setCheckable(True)
            if i == 0:
                btn.setChecked(True)
            if ptext == self.ipypost4.h5group_options[i]:
                btn.setChecked(True)
            self._h5group_widget.addButton(btn, i)
            self._h5group_layout.addWidget(btn)

        self._h5group_widget.blockSignals(False)

        self._h5dataset_widget.blockSignals(True)
        ptext = self._h5dataset_widget.currentText()
        self._h5dataset_widget.clear()
        self._h5dataset_widget.addItems(self.ipypost4.dataset_in_groups[self.h5group])
        if ptext in self.ipypost4.dataset_in_groups[self.h5group]:
            self._h5dataset_widget.setCurrentText(ptext)

        self._h5dataset_widget.blockSignals(False)

    def fetch_data(self):
        """Fetch data from HDF5 file if not already cached."""
        if self.data_tag == f'/{self.h5group}/{self.h5dataset}':
            return

        # Clear old data safely
        if self.data is not None: del self.data
        self.data = self.ipypost4.fetch_data(f'/{self.h5group}/{self.h5dataset}')
        self.data_tag = f'/{self.h5group}/{self.h5dataset}'

        if self.ipypost4.h5_file[self.data_tag].attrs.__contains__('unit'):
            self.data_unit = str(self.ipypost4.h5_file[self.data_tag].attrs['unit'], encoding="utf-8")
        else:
            self.data_unit = 'a.u.'

    def on_dataset_change(self, text: str):
        """Handle dataset selection change."""
        logger.debug(f"on_dataset_change: self.h5group={self.h5group}, self.h5dataset={self.h5dataset}")
        self.ipypost4.plot_new_dataset()

    def on_group_change(self, button: QtWidgets.QPushButton, checked: bool):
        """Handle HDF5 group selection change."""
        if not checked:
            return
        logger.debug(f"on_group_change: button={button}")

        self._h5dataset_widget.blockSignals(True)
        ptext = self._h5dataset_widget.currentText()
        self._h5dataset_widget.clear()
        self._h5dataset_widget.addItems(self.ipypost4.dataset_in_groups[self.h5group])
        self._h5dataset_widget.blockSignals(False)
        self._h5dataset_widget.setCurrentText(
            ptext if ptext in self.ipypost4.dataset_in_groups[self.h5group]
            else self.ipypost4.dataset_in_groups[self.h5group][0]
        )
        self.on_dataset_change(self._h5dataset_widget.currentText())

    def update_text_visiable(self, event):
        """Update visibility of peak text annotation based on axis limits."""
        if not self.peak_text:
            return
        logger.debug(f"MainPlotUnit.update_text_visiable: peak_text={self.peak_text}")
        new_visible = self.ax.get_xlim()[0] <= self.peak_text._x <= self.ax.get_xlim()[1]

        if new_visible == self.peak_text.get_visible():
            return
        else:
            self.peak_text.set_visible(new_visible)
            event.canvas.draw_idle()

    def _find_peak(self):
        """Find and annotate peak with FWHM."""
        if self.peak_text:
            self.peak_text.remove()
            self.peak_text = None

        if self._find_peak_checkbox.isChecked():
            x = self.line.get_xdata()
            y = self.line.get_ydata()
            peak_x, peak_value, FWHM = fwhm(x, y)
            self.peak_text = self.ax.text(
                peak_x, peak_value,
                f'{peak_x:.3f}, {peak_value:.3e}\n FWHM: {FWHM:.3f}',
                fontsize=10, verticalalignment='center',
                horizontalalignment='center', color=self.color
            )

    def _plot_yzero_line(self):
        """Plot horizontal line at y=0 if enabled."""
        if self.yzero_line:
            self.yzero_line.remove()
            self.yzero_line = None

        if self._y_zero_line_checkbox.isChecked():
            self.yzero_line = self.ax.axhline(
                0, np.min(self.line.get_xdata()), np.max(self.line.get_xdata()),
                linewidth=0.8, linestyle='--', color=self.color
            )

    def unit_nice_needed(self) -> bool:
        """Check if unit formatting is needed."""
        return self.data_unit in ['m', 'W', 'A']

    def nice_unit_formatter(self, y: float, pos) -> str:
        """Format tick values with SI prefixes."""
        if y == 0:
            return "0"
        val = y / self.unit_factor
        if abs(val) >= 100:
            return f"{val:.1f}"
        elif abs(val) >= 10:
            return f"{val:.2f}"
        else:
            return f"{val:.3f}"

    def init_nice_unit(self):
        """Initialize unit formatter based on data unit."""
        if self.unit_nice_needed():
            logger.debug(f"MainPlotUnit.init_nice_unit: self.data_unit={self.data_unit} with nice unit")
            self.unit_formatter = matplotlib.ticker.FuncFormatter(self.nice_unit_formatter)
        else:
            logger.debug(f"MainPlotUnit.init_nice_unit: self.data_unit={self.data_unit} without nice unit")
            self.unit_formatter = matplotlib.ticker.ScalarFormatter()
            self.unit_factor, self.unit_prefix = 1, ""
        self.ax.yaxis.set_major_formatter(self.unit_formatter)

    def update_nice_scale_prefix(self, data: np.ndarray):
        """Update SI prefix based on data magnitude."""
        if not self.unit_nice_needed():
            return

        scale = np.max(np.abs(data))
        if scale == 0:
            self.unit_factor, self.unit_prefix = 1, ""
            return

        p10 = np.log10(abs(scale))

        if p10 < -18:
            f = 1e-18
        elif p10 > 15:
            f = 1e15
        elif p10 < -1.5 or p10 > 2:
            f = 10 ** (p10 // 3 * 3)
        else:
            f = 1

        SHORT_PREFIX_FACTOR = {
            "a": 1e-18, "f": 1e-15, "p": 1e-12, "n": 1e-9,
            "µ": 1e-6, "m": 1e-3, "": 1, "da": 1e1,
            "h": 1e2, "k": 1e3, "M": 1e6, "G": 1e9,
            "T": 1e12, "P": 1e15
        }
        SHORT_PREFIX: dict = dict((v, k) for k, v in SHORT_PREFIX_FACTOR.items())

        self.unit_factor, self.unit_prefix = f, SHORT_PREFIX[f]

    def get_unit(self) -> str:
        """Get formatted unit string."""
        return (f'({self.unit_prefix}{self.data_unit})' if self.data_unit and self.data_unit != ' ' else '')

    def update_plot(self):
        """Update plot with current slice data."""
        if self.ipypost4.slice_control.plot_axis_x == 's':
            z_idx = np.argmin(np.abs(self.ipypost4.zplot - self.ipypost4.slice_control.slice_value))
            self.line.set_ydata(self.data[z_idx, :])
            self.ipypost4.fig.suptitle(f'at z = {self.ipypost4.zplot[z_idx]:.3f} m')
        else:
            s_idx = np.argmin(np.abs(self.ipypost4.s_values - self.ipypost4.slice_control.slice_value))
            self.line.set_ydata(self.data[:, s_idx])
            self.ipypost4.fig.suptitle(f'at s = {self.ipypost4.s_values[s_idx]:.3f} um')

        self._find_peak()
        self._plot_yzero_line()

        self.ax.relim()
        if not self.ipypost4.lockyscale_checkbox.isChecked():
            self.update_nice_scale_prefix(self.line.get_ydata())
            self.ax.set_ylabel(f'{self.h5group} / {self.h5dataset} ' + self.get_unit())
            self.ax.autoscale(axis='y')

        if self._log_y_scale_checkbox.isChecked():
            self.ax.set_yscale('log')
        else:
            self.ax.set_yscale('linear')
        self.ax.yaxis.set_major_formatter(self.unit_formatter)

    def plot_new(self, **kwargs):
        """Create new plot with current data."""
        self.fetch_data()
        self.init_nice_unit()

        # Clear existing lines
        for l in self.ax.lines:
            l.remove()
        self.yzero_line = None

        if self.h5group == 'Lattice':
            kwargs['drawstyle'] = 'steps-post'

        if self.ipypost4.slice_control.plot_axis_x == 's':
            z_idx = np.argmin(np.abs(self.ipypost4.zplot - self.ipypost4.slice_control.slice_value))
            plot_xdata = self.ipypost4.s_values
            plot_ydata = self.data[z_idx, :]
            plot_xlabel = 's[um] (Global/s)'
            plot_title = f'at z = {self.ipypost4.zplot[z_idx]:.3f} m'
        else:
            s_idx = np.argmin(np.abs(self.ipypost4.s_values - self.ipypost4.slice_control.slice_value))
            plot_xdata = self.ipypost4.zplot
            plot_ydata = self.data[:, s_idx]
            plot_xlabel = 'z[m] (Lattice/zplot)'
            plot_title = f'at s = {self.ipypost4.s_values[s_idx]:.3f} um'

        self.update_nice_scale_prefix(plot_ydata)

        self.line = self.ax.plot(
            plot_xdata, plot_ydata, linewidth=0.8, color=self.color,
            label=f'{self.h5group}/{self.h5dataset}', **kwargs
        )[0]

        if self._avg_over_s_checkbox.isChecked() and self.ipypost4.slice_control.plot_axis_x == 'z':
            self.ax.plot(
                plot_xdata, np.mean(self.data, axis=1),
                linewidth=0.8, color=self.color, linestyle='--',
                label=f'Avg.{self.h5group}/{self.h5dataset}', **kwargs
            )
        if self._max_over_s_checkbox.isChecked() and self.ipypost4.slice_control.plot_axis_x == 'z':
            self.ax.plot(
                plot_xdata, np.max(self.data, axis=1),
                linewidth=0.8, color=self.color, linestyle=':',
                label=f'Max.{self.h5group}/{self.h5dataset}', **kwargs
            )

        self.ax.set_xlabel(plot_xlabel)
        self.ax.set_ylabel(f'{self.h5group} / {self.h5dataset} ' + self.get_unit())
        self.ipypost4.fig.suptitle(plot_title)

        self._find_peak()
        self._plot_yzero_line()

        self.ax.relim()
        self.ax.autoscale()
        self.ax.figure.canvas.toolbar.update()

        if self._log_y_scale_checkbox.isChecked():
            self.ax.set_yscale('log')
        else:
            self.ax.set_yscale('linear')
        self.ax.yaxis.set_major_formatter(self.unit_formatter)

        self.ax.yaxis.label.set_color(self.color)
        self.ax.tick_params(axis='y', colors=self.color)
