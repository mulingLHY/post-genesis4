"""FFT spectrum plot widget for field analysis."""

from typing import Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
from scipy.constants import c
from PyQt5 import QtWidgets, QtGui

from post_genesis4.utils.log_utils import logger

import post_genesis4.gui as gui


class FFTSpectrumPlotUnit(QtWidgets.QWidget):
    """
    Widget for displaying FFT spectrum of radiation field.

    Provides controls for selecting harmonic number, field type (far/near),
    and wavelength range for FFT analysis.

    Attributes:
        ipypost4: Reference to main application instance.
        ax: Matplotlib axes for spectrum plotting.
        line: Plot line for spectrum data.
        data_tag: Current data identifier tag.
        intens: Intensity data array.
        phase: Phase data array.
        harm: Selected harmonic number.
        group: Selected field group name.
    """

    def __init__(self, ipypost4: "gui.IPyPostGenesis4", ax: plt.Axes):
        """
        Initialize FFT spectrum plot unit.

        Args:
            ipypost4: Main application instance.
            ax: Matplotlib axes for plotting.
        """
        super().__init__()
        self.ipypost4 = ipypost4
        self.ax = ax

        self.line: Optional[plt.Line2D] = None
        self.data_tag: Optional[str] = None
        self.__spectrum_min: Optional[float] = None
        self.__spectrum_max: Optional[float] = None

        self.intens: Optional[np.ndarray] = None
        self.phase: Optional[np.ndarray] = None
        self.harm: int = 1
        self.group: str = ""

        self.setLayout(QtWidgets.QHBoxLayout())

        # Harmonic selection buttons
        self._harmsgroup_widget = QtWidgets.QButtonGroup(self)
        self._harmsgroup_widget.setExclusive(True)

        for i in range(len(self.ipypost4.h5group_options)):
            if not self.ipypost4.h5group_options[i].startswith('Field'):
                continue
            btn = QtWidgets.QPushButton(self.ipypost4.h5group_options[i], self)
            btn.setFixedWidth(90)
            btn.setCheckable(True)
            if i == 2:
                btn.setChecked(True)
            self._harmsgroup_widget.addButton(btn, i)

        self._harmsgroup_widget.buttonToggled.connect(self.on_harm_change)

        layout = QtWidgets.QHBoxLayout()
        self.__show_fft_checkbox = QtWidgets.QCheckBox('FFT Spectrum:', self)
        self.__show_fft_checkbox.setChecked(False)
        self.__show_fft_checkbox.stateChanged.connect(
            lambda state: self.ipypost4.set_fft_spectrum_visible(
                self.__show_fft_checkbox.isChecked()
            )
        )
        layout.addWidget(self.__show_fft_checkbox)

        # Field type radio buttons (far/near)
        self._fieldtype_widget = QtWidgets.QButtonGroup(self)
        self._fieldtype_widget.setExclusive(True)

        btn = QtWidgets.QPushButton('far', self)
        btn.setFixedWidth(60)
        btn.setCheckable(True)
        btn.setChecked(True)
        self._fieldtype_widget.addButton(btn)

        btn = QtWidgets.QPushButton('near', self)
        btn.setFixedWidth(60)
        btn.setCheckable(True)
        self._fieldtype_widget.addButton(btn)

        self._fieldtype_widget.buttonToggled.connect(self.on_fieldtype_change)

        self._fieldtype_layout = QtWidgets.QHBoxLayout()
        for btn in self._fieldtype_widget.buttons():
            self._fieldtype_layout.addWidget(btn)
        layout.addLayout(self._fieldtype_layout)

        self._harmsgroup_layout = QtWidgets.QHBoxLayout()
        for btn in self._harmsgroup_widget.buttons():
            self._harmsgroup_layout.addWidget(btn)
        layout.addLayout(self._harmsgroup_layout)

        # Wavelength range inputs
        self.__min_lambda_input = QtWidgets.QLineEdit(self)
        self.__min_lambda_input.setFixedWidth(100)
        self.__min_lambda_input.setValidator(QtGui.QDoubleValidator())
        self.__min_lambda_input.setPlaceholderText('min (nm)')
        self.__min_lambda_input.textChanged.connect(self.on_lambda_range_change)
        self.__min_lambda_input.returnPressed.connect(self.on_lambda_range_change)
        layout.addWidget(self.__min_lambda_input)

        self.__max_lambda_input = QtWidgets.QLineEdit(self)
        self.__max_lambda_input.setFixedWidth(100)
        self.__max_lambda_input.setValidator(QtGui.QDoubleValidator())
        self.__max_lambda_input.setPlaceholderText('max (nm)')
        self.__max_lambda_input.textChanged.connect(self.on_lambda_range_change)
        self.__max_lambda_input.returnPressed.connect(self.on_lambda_range_change)
        layout.addWidget(self.__max_lambda_input)

        self.layout().addLayout(layout)

    def on_fieldtype_change(self, btn, checked: bool):
        """Handle field type (far/near) change."""
        self.ax.clear()
        self.plot_new()
        self.ax.figure.canvas.draw_idle()

    def on_harm_change(self, btn, checked: bool):
        """Handle harmonic number change."""
        self.ax.clear()
        self.plot_new()
        self.ax.figure.canvas.draw_idle()

    def validated_lambda_range(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get validated wavelength range from input fields.

        Returns:
            Tuple of (min_lambda, max_lambda), or (None, None) if not set.
        """
        if self.__spectrum_min is None or self.__spectrum_max is None:
            return None, None

        min_lambda = float(self.__min_lambda_input.text()) if self.__min_lambda_input.text() else self.__spectrum_min
        max_lambda = float(self.__max_lambda_input.text()) if self.__max_lambda_input.text() else self.__spectrum_max

        if min_lambda >= max_lambda or min_lambda >= self.__spectrum_max or max_lambda <= self.__spectrum_min:
            return self.__spectrum_min, self.__spectrum_max

        return min_lambda, max_lambda

    def on_lambda_range_change(self):
        """Handle wavelength range input change."""
        logger.debug(f"on_range_lambda_range_change, {self.__min_lambda_input.text()}, {self.__max_lambda_input.text()}")

        if self.__spectrum_min is None or self.__spectrum_max is None:
            return

        min_lambda, max_lambda = self.validated_lambda_range()
        self.ax.set_xlim(min_lambda, max_lambda)
        self.ax.figure.canvas.draw_idle()

    def fetch_data(self, loc: str = 'far'):
        """
        Fetch field data from HDF5 file.

        Args:
            loc: Location type, either 'far' or 'near'.
        """
        self.group = self._harmsgroup_widget.checkedButton().text()
        self.harm = self.group.split('Field')[1]
        self.harm = int(1 if self.harm == '' else self.harm)

        loc = self._fieldtype_widget.checkedButton().text()

        if loc in ('far', 'near'):
            data_tag = f'/{self.group}/{loc}'
            if self.data_tag == data_tag:
                return
            self.intens, self.phase = self.ipypost4.fetch_data(
                f'/{self.group}/intensity-{loc}field',
                f'/{self.group}/phase-{loc}field'
            )
            self.data_tag = data_tag
        else:
            raise ValueError('loc should be either "far" or "near"')

    def _rad_field(self) -> Tuple[np.ndarray, int]:
        """
        Get complex radiation field at current slice.

        Returns:
            Tuple of (complex field array, harmonic number).
        """
        if self.ipypost4.slice_control._slice_at_z_idx in np.arange(self.intens.shape[0]):
            intens = self.intens[self.ipypost4.slice_control._slice_at_z_idx, :]
            phase = self.phase[self.ipypost4.slice_control._slice_at_z_idx, :]
        else:
            intens = self.intens[-1, :]
            phase = self.phase[-1, :]

        # Note: not scaled properly
        field = np.sqrt(intens[:]) * np.exp(1j * phase[:])
        return field, self.harm

    def update_plot(self):
        """Update spectrum plot with current data."""
        field, harm = self._rad_field()
        spec = np.abs(np.fft.fft(field)) ** 2
        spec = np.fft.fftshift(spec)

        self.line.set_ydata(spec)
        self.ax.set_title(
            f'FFT Spectrum(a.u.),{self.ipypost4.zplot[self.ipypost4.slice_control._slice_at_z_idx]:.3f}m'
        )
        self.ax.relim()
        if not self.ipypost4.lockyscale_checkbox.isChecked():
            self.ax.autoscale(axis='y')

    def plot_new(self):
        logger.debug("FFTSpectrumPlotUnit.plot_new")
        self.fetch_data()

        s_values = self.ipypost4.s_values  # units: um
        field, harm = self._rad_field()

        s_values_m = s_values * 1e-6  # Convert from um to m
        time_values = s_values_m / c

        # Calculate FFT
        N = len(field)
        T = np.mean(np.diff(time_values))
        freq = np.fft.fftfreq(N, d=T) + c/self.ipypost4.h5_file['/Global/lambdaref'][0]*harm
        freq = np.fft.fftshift(freq)

        spec = np.abs(np.fft.fft(field)) ** 2
        spec = np.fft.fftshift(spec)

        freq /= 1e9  # Convert from Hz to GHz

        self.ax.clear()
        self.line, = self.ax.plot(c/freq, spec, linewidth=0.8, color='#1F77A4')
        self.ax.yaxis.tick_right()
        self.ax.set_title(
            f'FFT Spectrum(a.u.),{self.ipypost4.zplot[self.ipypost4.slice_control._slice_at_z_idx]:.3f}m'
        )
        self.ax.set_xlabel(r'$\lambda$ (nm)')
        self.ax.grid(axis='x', linestyle=':', alpha=0.8)

        self.__spectrum_min = np.min(c/freq)
        self.__spectrum_max = np.max(c/freq)

        self.ax.set_xlim(self.validated_lambda_range())

    def reinit(self):
        """Reinitialize widget when new data is loaded."""
        self.data_tag = None
        self.__spectrum_min = None
        self.__spectrum_max = None

        self._harmsgroup_widget.blockSignals(True)
        ptext = ''
        for btn in self._harmsgroup_widget.buttons():
            if btn.isChecked():
                ptext = btn.text()
            self._harmsgroup_widget.removeButton(btn)
            self._harmsgroup_layout.removeWidget(btn)
            del btn

        for i in range(len(self.ipypost4.h5group_options)):
            if not self.ipypost4.h5group_options[i].startswith('Field'):
                continue
            btn = QtWidgets.QPushButton(self.ipypost4.h5group_options[i], self)
            btn.setFixedWidth(90)
            btn.setCheckable(True)
            if i == 2:
                btn.setChecked(True)
            if ptext == self.ipypost4.h5group_options[i]:
                btn.setChecked(True)
            self._harmsgroup_widget.addButton(btn, i)
            self._harmsgroup_layout.addWidget(btn)

        self._harmsgroup_widget.blockSignals(False)

        self.ax.clear()
        if self.ax.get_visible():
            self.plot_new()
