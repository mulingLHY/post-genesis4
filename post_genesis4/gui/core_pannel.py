"""
Core pannel for Genesis4 output visualization.

This module contains the main IPyPostGenesis4 class that coordinates all plotting widgets and manages the visualization state.
"""

from typing import Dict, Optional

import numpy as np
import matplotlib.pyplot as plt
import h5py
from PyQt5 import QtWidgets, QtCore

from post_genesis4.utils.log_utils import logger
from post_genesis4.gui.widgets import (
    WaitingDialog, SliceControl, MainPlotUnit, BriefLatticePlotUnit,
    FFTSpectrumPlotUnit, GifExporter, CopyableNavigationToolbar
)


class IPyPostGenesis4Builder:
    """
    Builder class for preparing Genesis4 data for visualization.

    This class pre-loads metadata and dataset structure from an HDF5 file
    to enable faster GUI response times.

    Attributes:
        h5_file: The opened HDF5 file object.
        zplot: Z-axis plot coordinates.
        s_values: S-axis values in micrometers.
        h5group_options: Available HDF5 groups for plotting.
        dataset_in_groups: Mapping of groups to their datasets.
    """

    def __init__(self, h5_file: h5py.File):
        """
        Initialize builder with an HDF5 file.

        Args:
            h5_file: Opened h5py File object in read mode.
        """
        self.h5_file = h5_file
        self.zplot = np.round(h5_file['/Lattice/zplot'][:], 3)
        self.s_values = np.round(h5_file['/Global/s'][:]*1e6, 3)

        # Build list of available groups
        self.h5group_options = ['Beam', 'Lattice']
        for group_name in h5_file.keys():
            if group_name.startswith('Field'):
                self.h5group_options.append(group_name)

        # Map groups to their datasets (excluding Global datasets)
        self.dataset_in_groups = {
            group: [name for name in h5_file[f'/{group}'].keys() if not name.startswith('Global')]
            for group in self.h5group_options
        }


# Default plot configuration
default_plot_config = {
    "plot_unit1": {
        "h5group": "Beam",
        "h5dataset": "current",
        "log_y_scale": False,
        "avg_over_s": False,
        "max_over_s": False,
        "find_peak": False
    },
    "plot_unit2": {
        "h5group": "Field",
        "h5dataset": "power",
        "log_y_scale": False,
        "avg_over_s": False,
        "max_over_s": False,
        "find_peak": True
    },
    "slice_control": {
        "plot_axis_x": "s",
        "slice_value": 20
    },
    "second_curve": True,
}


class IPyPostGenesis4(QtWidgets.QWidget):
    """
    Main visualization widget for Genesis4 output data.

    Coordinates multiple plot units, slice control, and optional features
    like lattice display and FFT spectrum analysis.

    This class uses a singleton-like pattern to manage multiple instances
    identified by igui_id.

    Attributes:
        h5_file: HDF5 file object.
        zplot: Z-axis coordinates.
        s_values: S-axis values in micrometers.
        h5group_options: Available HDF5 groups.
        dataset_in_groups: Mapping of groups to datasets.
        fig: Matplotlib figure.
        slice_control: Slice selection widget.
        plot_unit1: Primary plot unit.
        plot_unit2: Secondary plot unit (optional).
        fft_spectrum_plot_unit: FFT spectrum plot (optional).
        lattice_plot_unit: Lattice overview plot (optional).
        gifexporter: GIF export widget.
    """

    def __init__(self, builder: IPyPostGenesis4Builder, plot_config: Dict = default_plot_config,
                 force_config: bool = False):
        """
        Initialize visualization widget.

        Args:
            builder: Data builder with pre-loaded metadata.
            plot_config: Configuration dictionary for plot settings.
            force_config: If True, reapply config even if already initialized.
            igui_id: Instance identifier.
        """
        self.h5_file = builder.h5_file
        self.zplot = builder.zplot
        self.s_values = builder.s_values
        self.h5group_options = builder.h5group_options

        # Update default Field group if available
        for group_name in self.h5group_options:
            if group_name.startswith('Field'):
                default_plot_config['plot_unit2']['h5group'] = group_name

        self.dataset_in_groups = builder.dataset_in_groups

        super().__init__()
        self.setLayout(QtWidgets.QVBoxLayout())
        self.wait_data_dialog = WaitingDialog(
            self.window(), title="Waiting...", message="Waiting for data..."
        )

        # Create matplotlib figure
        self.fig = plt.figure(figsize=(20, 40), dpi=120)
        self.fig.subplots_adjust(top=0.88, bottom=0.12, left=0.08, right=0.95, hspace=0.1, wspace=0.2)
        self.gs = self.fig.add_gridspec(1, 3, width_ratios=[12, 1, 4], wspace=0.04)
        self.gs.set_width_ratios([12, 0.1, 0.1])

        self.main_ax = self.fig.add_subplot(self.gs[0])
        self.feature_ax = self.fig.add_subplot(self.gs[2])
        self.feature_ax.set_visible(False)
        self.fig.canvas.draw_idle()

        # Lattice plot
        self.lattice_ax = self.fig.add_axes(self.parse_lattice_ax_posision())
        self.lattice_plot_unit = BriefLatticePlotUnit(ipypost4=self, ax=self.lattice_ax)

        # Slice control
        self.slice_control = SliceControl(ipypost4=self)

        # Plot units
        self.plot_unit1 = MainPlotUnit(
            ipypost4=self, ax=self.main_ax,
            slice_control=self.slice_control, color='#00739c', label='1'
        )
        self.plot_unit2 = MainPlotUnit(
            ipypost4=self, ax=self.main_ax.twinx(),
            slice_control=self.slice_control, color='#e24200', label='2'
        )
        self.plot_unit2.ax.set_visible(False)

        # FFT spectrum plot
        self.fft_spectrum_plot_unit = FFTSpectrumPlotUnit(ipypost4=self, ax=self.feature_ax)

        # Control checkboxes
        aux_group = QtWidgets.QHBoxLayout()
        aux_group.setContentsMargins(10, 0, 0, 0)
        aux_group.setAlignment(QtCore.Qt.AlignLeft)

        self.second_curve_checkbox = QtWidgets.QCheckBox('Second curve')
        self.second_curve_checkbox.setMaximumWidth(160)
        self.second_curve_checkbox.stateChanged.connect(self.on_second_curve_checkbox_change)

        self.lattice_plot_checkbox = QtWidgets.QCheckBox('Brief Lattice')
        self.lattice_plot_checkbox.setMaximumWidth(160)
        self.lattice_plot_checkbox.stateChanged.connect(self.on_lattice_plot_checkbox_change)
        self.lattice_plot_unit.ax.set_visible(False)

        self.lockyscale_checkbox = QtWidgets.QCheckBox('Lock y-scale')
        self.lockyscale_checkbox.setMaximumWidth(160)
        self.lockyscale_checkbox.stateChanged.connect(
            lambda change: self.update_plot_slice() if not change else None
        )

        aux_group.addWidget(self.second_curve_checkbox)
        aux_group.addWidget(self.lockyscale_checkbox)
        aux_group.addWidget(self.lattice_plot_checkbox)
        aux_group.addStretch(1)
        aux_group.addWidget(self.fft_spectrum_plot_unit)

        # Canvas and toolbar
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        self._fig_widget = FigureCanvas(self.fig)

        # Options group box
        self.opitions_group = QtWidgets.QGroupBox('Options')
        self.opitions_group.setLayout(QtWidgets.QHBoxLayout())
        self.opitions_group.layout().addWidget(self.plot_unit1)
        space_between = QtWidgets.QLabel()
        space_between.setMaximumWidth(100)
        self.opitions_group.layout().addWidget(space_between)
        self.opitions_group.layout().addWidget(self.plot_unit2)

        # Assemble layout
        self.layout().addWidget(self.opitions_group)
        self.layout().addWidget(self.slice_control)
        self.layout().addLayout(aux_group)
        self.layout().addWidget(self._fig_widget)
        self.layout().addWidget(CopyableNavigationToolbar(self._fig_widget, self))

        # GIF exporter
        self.gifexporter = GifExporter(ipypost4=self)
        self.layout().addWidget(self.gifexporter)

        self.layout().setContentsMargins(5, 10, 5, 0)

        # Apply configuration
        self.__apply_plot_config(plot_config)

        self.plot_new_dataset()

    def reinit(self, builder: IPyPostGenesis4Builder):
        self.h5_file = builder.h5_file
        self.zplot = builder.zplot
        self.s_values = builder.s_values
        self.h5group_options = builder.h5group_options

        # Update default Field group if available
        for group_name in self.h5group_options:
            if group_name.startswith('Field'):
                default_plot_config['plot_unit2']['h5group'] = group_name

        self.dataset_in_groups = builder.dataset_in_groups
    
        # Reinitialize widgets for new data
        self.plot_unit1.reinit()
        self.plot_unit2.reinit()
        self.slice_control.reinit()
        self.fft_spectrum_plot_unit.reinit()

        self.plot_new_dataset()


    @property
    def second_curve(self) -> bool:
        """Get second curve visibility state."""
        return self.second_curve_checkbox.isChecked() if self.second_curve_checkbox else None

    @second_curve.setter
    def second_curve(self, value: bool):
        """Set second curve visibility state."""
        self.second_curve_checkbox.setChecked(value)

    def __apply_plot_config(self, plot_config: Dict):
        """
        Recursively apply plot configuration to object attributes.

        Args:
            plot_config: Configuration dictionary.
        """
        if plot_config is None:
            return
        for key, value in plot_config.items():
            if isinstance(value, dict):
                IPyPostGenesis4.__apply_plot_config(getattr(self, key), value)
            else:
                setattr(self, key, value)

    def parse_lattice_ax_posision(self) -> list:
        """
        Calculate lattice axes position relative to main axes.

        Returns:
            List [x0, y0, width, height] for lattice axes.
        """
        pos = self.main_ax.get_position()
        new_height = pos.height / 15
        return [pos.x0, pos.y0 + pos.height + new_height/4, pos.width, new_height]

    def fetch_data(self, *data_path: str):
        """
        Fetch data from HDF5 file with proper reshaping.

        Args:
            *data_path: HDF5 dataset paths to fetch.

        Returns:
            Single array if one path, list of arrays if multiple paths.
        """
        self.wait_data_dialog.show()

        res = []
        for path in data_path:
            data = self.h5_file[path][()]

            # Reshape 1D data to 2D
            if len(data.shape) == 1:
                data = np.append(data, [data[-1]] * (len(self.zplot) - data.shape[0]))
                data = data[:, np.newaxis].repeat(self.s_values.shape[0], axis=1)

            # Expand single-row data
            if data.shape[0] == 1:
                data = data.repeat(self.zplot.shape[0], axis=0)

            res.append(data)

        self.wait_data_dialog.accept()

        if len(res) == 1:
            return res[0]
        else:
            return res

    def set_fft_spectrum_visible(self, visible: bool):
        """
        Show or hide FFT spectrum plot.

        Args:
            visible: Whether to show the spectrum plot.
        """
        if visible:
            self.fft_spectrum_plot_unit.ax.set_visible(True)
            self.gs.set_width_ratios([12, 1, 4])
            self.gs.update()
            self.lattice_ax.set_position(self.parse_lattice_ax_posision())
            self.fig.canvas.draw_idle()
            self.plot_new_dataset()
        else:
            self.fft_spectrum_plot_unit.ax.set_visible(False)
            self.gs.set_width_ratios([12, 0.1, 0.1])
            self.gs.update()
            self.lattice_ax.set_position(self.parse_lattice_ax_posision())
            self.fig.canvas.draw_idle()

    def on_second_curve_checkbox_change(self, change: int):
        """Handle second curve checkbox toggle."""
        logger.debug(f"IPyPostGenesis4.on_second_curve_checkbox_change: new value={change}")
        if change:
            self.plot_unit2.ax.set_visible(True)
            self.plot_new_dataset()
        else:
            self.plot_unit2.ax.set_visible(False)
            self.fig.canvas.draw_idle()

    def on_lattice_plot_checkbox_change(self, change: int):
        """Handle lattice plot checkbox toggle."""
        logger.debug(f"IPyPostGenesis4.on_lattice_plot_checkbox_change: new value={change}")
        if change:
            self.lattice_plot_unit.ax.set_visible(True)
            self.lattice_plot_unit.ax_twin.set_visible(True)
        else:
            self.lattice_plot_unit.ax.set_visible(False)
            self.lattice_plot_unit.ax_twin.set_visible(False)

        if self.lattice_plot_checkbox.isChecked():
            self.lattice_plot_unit.plot_new()
        self.fig.canvas.draw_idle()

    def update_plot_slice(self):
        """Update all plots with current slice position."""
        self.fig.canvas.toolbar._nav_stack.back()

        # Update plots and autoscale
        self.plot_unit1.update_plot()
        if self.plot_unit2.ax.get_visible():
            self.plot_unit2.update_plot()

        if self.slice_control.plot_axis_x == 's' and self.fft_spectrum_plot_unit.ax.get_visible():
            self.fft_spectrum_plot_unit.update_plot()

        if self.lattice_plot_unit.ax.get_visible():
            self.lattice_plot_unit.update_plot()

        # Store locked limits and scale
        self.fig.canvas.toolbar.push_current()
        locked_scale = self.fig.canvas.toolbar._nav_stack()
        self.fig.canvas.toolbar._nav_stack.back()

        # Push all-view scale to toolbar home scale
        self.plot_unit1.ax.relim()
        self.plot_unit2.ax.relim()
        self.plot_unit1.ax.autoscale()
        self.plot_unit2.ax.autoscale()

        if self.slice_control.plot_axis_x == 's' and self.fft_spectrum_plot_unit.ax.get_visible():
            self.fft_spectrum_plot_unit.ax.relim()
            self.fft_spectrum_plot_unit.ax.autoscale()

        self.fig.canvas.toolbar.push_current()
        self.fig.canvas.toolbar._nav_stack._elements[0] = self.fig.canvas.toolbar._nav_stack()
        self.fig.canvas.toolbar._nav_stack.back()

        # Restore locked scale
        self.fig.canvas.toolbar._nav_stack.push(locked_scale)
        self.fig.canvas.toolbar._update_view()

    def plot_new_dataset(self):
        """Create new plots with current dataset selections."""
        logger.debug('enter plot_new_dataset')

        self.plot_unit1.plot_new(antialiased=True)
        self.plot_unit1.ax.grid(axis='x', linestyle=':', alpha=0.8)

        if self.second_curve_checkbox.isChecked():
            self.plot_unit2.plot_new(antialiased=True)

        if self.fft_spectrum_plot_unit.ax.get_visible():
            self.fft_spectrum_plot_unit.plot_new()

        if self.lattice_plot_checkbox.isChecked():
            self.lattice_plot_unit.plot_new()

        self.fig.canvas.draw_idle()
        logger.debug('leave plot_new_dataset')
