# -*- encoding: utf-8 -*-
'''
@File    :   pyqt5post_genesis4.pyw
@Time    :   2026/04/23 12:04:00
@Author  :   lihaiyang from SINAP 
'''

tip = """
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

import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker
from dataclasses import dataclass
import logging
import sys
import os
from scipy.constants import speed_of_light
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
import platform

def _setup_logger(level=logging.INFO):
    _logger = logging.getLogger(__name__)
    _logger.setLevel(level)

    if level <= logging.DEBUG:
        handler = logging.FileHandler(filename='pypost_genesis4.log', mode='w')
    else:
        handler = logging.StreamHandler(sys.stdout)

    # handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s,%(msecs)d$ %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)

    if len(_logger.handlers) > 0:
        _logger.handlers[-1] = handler 
    else:
        _logger.addHandler(handler)
    return _logger

_logger = _setup_logger(level=logging.DEBUG)

def fwhm(x, data):
    peak_index = np.argmax(data)
    peak_value = data[peak_index]
    half_max = peak_value / 2.0

    left_idx = np.where(data[:peak_index] < half_max)[0]
    if len(left_idx) == 0:
        left_boundary = x[0]
    else:
        left_idx1 = left_idx[-1]
        left_idx2 = left_idx1 + 1
        left_boundary = x[left_idx1] + (half_max - data[left_idx1]) / (data[left_idx2] - data[left_idx1]) * (x[left_idx2] - x[left_idx1])

    # 右侧：找到小于half_max的索引，并进行线性插值
    right_idx = np.where(data[peak_index:] < half_max)[0]
    if len(right_idx) == 0:
        right_boundary = x[-1]
    else:
        right_idx1 = right_idx[0] + peak_index  # 第一个小于half_max的索引
        right_idx2 = right_idx1 - 1  # 最后一个大于half_max的索引
        # 线性插值计算右边界
        right_boundary = x[right_idx1] - (half_max - data[right_idx1]) / (data[right_idx2] - data[right_idx1]) * (x[right_idx1] - x[right_idx2])

    # 计算半高宽
    fwhm_value = right_boundary - left_boundary

    return x[peak_index], peak_value, fwhm_value

class WaitingDialog(QDialog):
    def __init__(self, parent=None, title="Waiting...", message="Waiting..."):
        super().__init__(parent=parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(600, 200)

        self.setLayout(QVBoxLayout(self))
        self.message = QLabel(message, self)
        self.layout().addWidget(self.message, alignment=Qt.AlignCenter)

        self.progress = QProgressBar(self)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setRange(0, 0)
        self.layout().addWidget(self.progress)

@dataclass
class MainPlotUnit(QtWidgets.QWidget):
    ipypost4: "IPyPostGenesis4" = None
    slice_control: "SliceControl" = None
    color: str = "grey"

    ax: plt.Axes = None
    line: plt.Line2D = None
    avg_line: plt.Line2D = None
    max_line: plt.Line2D = None

    label: str = None

    @property
    def h5group(self):
        return self.ipypost4.h5group_options[self._h5group_widget.checkedId()] if self._h5group_widget else None
    @h5group.setter
    def h5group(self, value):
        if value not in self.ipypost4.h5group_options:
            raise ValueError(f"Invalid h5group value: {value}")
        self._h5group_widget.buttons()[self.ipypost4.h5group_options.index(value)].setChecked(True)
    
    @property
    def h5dataset(self):
        return self._h5dataset_widget.currentText() if self._h5dataset_widget else None
    @h5dataset.setter
    def h5dataset(self, value):
        if value not in self.ipypost4.dataset_in_groups[self.h5group]:
            raise ValueError(f"Invalid h5dataset value: {value}")
        self._h5dataset_widget.setCurrentText(value)

    data:np.ndarray = None
    data_unit: str = 'a.u.'
    data_tag: str = None

    _h5group_widget: QtWidgets.QButtonGroup = None
    _h5dataset_widget: QtWidgets.QComboBox = None
    @property
    def avg_over_s(self):
        return self._avg_over_s_checkbox.isChecked()
    @avg_over_s.setter
    def avg_over_s(self, value):
        self._avg_over_s_checkbox.setChecked(value)
    @property
    def max_over_s(self):
        return self._max_over_s_checkbox.isChecked()
    @max_over_s.setter
    def max_over_s(self, value):
        self._max_over_s_checkbox.setChecked(value)
    @property
    def log_y_scale(self):
        return self._log_y_scale_checkbox.isChecked()
    @log_y_scale.setter
    def log_y_scale(self, value):
        self._log_y_scale_checkbox.setChecked(value)
    @property
    def find_peak(self):
        return self._find_peak_checkbox.isChecked()
    @find_peak.setter
    def find_peak(self, value):
        self._find_peak_checkbox.setChecked(value)

    _avg_over_s_checkbox: QtWidgets.QCheckBox = None
    _max_over_s_checkbox: QtWidgets.QCheckBox = None
    _log_y_scale_checkbox: QtWidgets.QCheckBox = None
    _find_peak_checkbox: QtWidgets.QCheckBox = None
    _y_zero_line_checkbox: QtWidgets.QCheckBox = None

    def init(self):
        super().__init__()

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

        self._avg_over_s_checkbox = QtWidgets.QCheckBox("Avg. over s")
        self._avg_over_s_checkbox.stateChanged.connect(lambda: self.ipypost4.plot_new_dataset())
        self._max_over_s_checkbox = QtWidgets.QCheckBox("Max. over s")
        self._max_over_s_checkbox.stateChanged.connect(lambda: self.ipypost4.plot_new_dataset())
        self._log_y_scale_checkbox = QtWidgets.QCheckBox("Log y-scale")
        self._log_y_scale_checkbox.stateChanged.connect(lambda: self.ipypost4.update_plot_slice())

        self.peak_text = None
        self._find_peak_checkbox = QtWidgets.QCheckBox("Find Peak")
        self._find_peak_checkbox.stateChanged.connect(lambda: self.ipypost4.update_plot_slice())

        self.yzero_line = None
        self._y_zero_line_checkbox = QtWidgets.QCheckBox("Line y=0")
        self._y_zero_line_checkbox.stateChanged.connect(lambda: (self.ipypost4.update_plot_slice(),self.ipypost4.fig.canvas.draw_idle()))
        
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._avg_over_s_checkbox)
        layout.addWidget(self._max_over_s_checkbox)
        layout.addWidget(self._log_y_scale_checkbox)
        layout.addWidget(self._find_peak_checkbox)
        layout.addWidget(self._y_zero_line_checkbox)
        self.layout().addLayout(layout)

    def reinit(self):
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
        if not self.ipypost4._initialized:
            return
        
        if self.data_tag == f'/{self.h5group}/{self.h5dataset}':
            return
        
        del self.data
        self.data = self.ipypost4.fetch_data(f'/{self.h5group}/{self.h5dataset}')
        self.data_tag = f'/{self.h5group}/{self.h5dataset}'

        if self.ipypost4.h5_file[self.data_tag].attrs.__contains__('unit'):
            self.data_unit = str(self.ipypost4.h5_file[self.data_tag].attrs['unit'], encoding="utf-8")
        else:
            self.data_unit = 'a.u.'

    def on_dataset_change(self, text):
        _logger.debug(f"on_dataset_change: self.h5group={self.h5group}, self.h5dataset={self.h5dataset}")
        self.fetch_data()
        
        self.ipypost4.plot_new_dataset()
    
    def on_group_change(self, button: QtWidgets.QPushButton, checked: bool): 
        if not checked: return  
        _logger.debug(f"on_group_change: button={button}")
        # the clear() will automatically trigger 'value' change with None
        self._h5dataset_widget.blockSignals(True)
        ptext = self._h5dataset_widget.currentText()
        self._h5dataset_widget.clear()
        self._h5dataset_widget.addItems(self.ipypost4.dataset_in_groups[self.h5group])
        self._h5dataset_widget.blockSignals(False)
        self._h5dataset_widget.setCurrentText(ptext if ptext in self.ipypost4.dataset_in_groups[self.h5group] else self.ipypost4.dataset_in_groups[self.h5group][0])
        self.on_dataset_change(self._h5dataset_widget.currentText())
        
    def update_text_visiable(self, event):
        if not self.peak_text:
            return
        _logger.debug(f"MainPlotUnit.update_text_visiable: peak_text={self.peak_text}")
        new_visible = self.ax.get_xlim()[0] <= self.peak_text._x <= self.ax.get_xlim()[1]
        # _logger.debug(f"update_text_visiable: self.ax.get_xlim()={self.ax.get_xlim()}, self.peak_text._x={self.peak_text._x}, new_visible={new_visible}")

        if new_visible == self.peak_text.get_visible():
            return
        else:
            self.peak_text.set_visible(new_visible)
            event.canvas.draw_idle()
        
    def _find_peak(self):
        if self.peak_text:
            self.peak_text.remove()
            self.peak_text = None
        if self._find_peak_checkbox.isChecked():    
            x = self.line.get_xdata()
            y = self.line.get_ydata()
            peak_x, peak_value, FWHM = fwhm(x, y)
            self.peak_text = self.ax.text(peak_x, peak_value, f'{peak_x:.3f}, {peak_value:.3e}\n FWHM: {FWHM:.3f}', 
                fontsize=10, verticalalignment='center', horizontalalignment='center', color=self.color)
        

    def _plot_yzero_line(self):
        if self.yzero_line:
            self.yzero_line.remove()
            self.yzero_line = None
        if self._y_zero_line_checkbox.isChecked():
            self.yzero_line = self.ax.axhline(0, np.min(self.line.get_xdata()), np.max(self.line.get_xdata()), linewidth=0.8, linestyle='--', color=self.color)

    def unit_nice_needed(self):
        return self.data_unit in ['m', 'W', 'A']

    def nice_unit_formatter(self, y, pos):
        if y == 0:
            return "0"
        val = y / self.unit_factor
        # 根据数值大小决定精度
        if abs(val) >= 100:
            return f"{val:.1f}"
        elif abs(val) >= 10:
            return f"{val:.2f}"
        else:
            return f"{val:.3f}"

    unit_formatter = matplotlib.ticker.ScalarFormatter()
    def init_nice_unit(self):
        if self.unit_nice_needed():
            _logger.debug(f"MainPlotUnit.init_nice_unit: self.data_unit={self.data_unit} with nice unit") 
            self.unit_formatter = matplotlib.ticker.FuncFormatter(self.nice_unit_formatter)
        else:
            _logger.debug(f"MainPlotUnit.init_nice_unit: self.data_unit={self.data_unit} without nice unit")
            self.unit_formmater = matplotlib.ticker.ScalarFormatter()
            self.unit_factor, self.unit_prefix = 1, ""
        self.ax.yaxis.set_major_formatter(self.unit_formatter)

    def update_nice_scale_prefix(self, data):
        if not self.unit_nice_needed():
            return
        scale = np.max(np.abs(data))
        if scale == 0:
            self.unit_factor, self.unit_prefix = 1, ""

        p10 = np.log10(abs(scale))

        if p10 < -18:  # Limits of SI prefixes
            f = 1e-18
        elif p10 > 15:
            f = 1e15
        elif p10 < -1.5 or p10 > 2:
            f = 10 ** (p10 // 3 * 3)
        else:
            f = 1

        SHORT_PREFIX_FACTOR = {"a": 1e-18, "f": 1e-15, "p": 1e-12, "n": 1e-9, "µ": 1e-6, "m": 1e-3, "": 1, "da": 1e1, "h": 1e2, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15}
        SHORT_PREFIX: dict[float, str] = dict((v, k) for k, v in SHORT_PREFIX_FACTOR.items())

        self.unit_factor, self.unit_prefix = f, SHORT_PREFIX[f]

    def get_unit(self):
        return (f'({self.unit_prefix}{self.data_unit})' if self.data_unit and self.data_unit != ' ' else '')

    def update_plot(self):
        if self.ipypost4.slice_control.plot_axis_x == 's':
            z_idx = np.argmin(np.abs(self.ipypost4.zplot - self.ipypost4.slice_control.slice_value))  # 找到与slice_value最接近的z索引
            self.line.set_ydata(self.data[z_idx, :])
            self.ipypost4.fig.suptitle(f'at z = {self.ipypost4.zplot[z_idx]:.3f} m')
        else:
            s_idx = np.argmin(np.abs(self.ipypost4.s_values - self.ipypost4.slice_control.slice_value))  # 找到与slice_value最接近的s索引
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
            # self.ax.set_ylim(bottom=max(np.finfo(np.float32).tiny, np.min(self.line.get_ydata())))
            self.ax.set_yscale('log')
        else:
            self.ax.set_yscale('linear')
        self.ax.yaxis.set_major_formatter(self.unit_formatter)

    def plot_new(self, **kwargs):
        self.fetch_data()
        self.init_nice_unit()

        for l in self.ax.lines: 
            l.remove()
            self.yzero_line = None
        
        if self.h5group == 'Lattice':
            kwargs['drawstyle']='steps-post'

        if self.ipypost4.slice_control.plot_axis_x == 's': 
            z_idx = np.argmin(np.abs(self.ipypost4.zplot - self.ipypost4.slice_control.slice_value))  # 找到与slice_value最接近的z索引
            plot_xdata = self.ipypost4.s_values
            plot_ydata = self.data[z_idx, :]
            plot_xlabel = 's[um] (Global/s)'
            plot_title = f'at z = {self.ipypost4.zplot[z_idx]:.3f} m'
        else:
            s_idx = np.argmin(np.abs(self.ipypost4.s_values - self.ipypost4.slice_control.slice_value))  # 找到与slice_value最接近的s索引
            plot_xdata = self.ipypost4.zplot
            plot_ydata = self.data[:, s_idx]
            plot_xlabel = 'z[m] (Lattice/zplot)'
            plot_title = f'at s = {self.ipypost4.s_values[s_idx]:.3f} um'

        self.update_nice_scale_prefix(plot_ydata)

        self.line = self.ax.plot(plot_xdata, plot_ydata, linewidth=0.8, color=self.color, label=f'{self.h5group}/{self.h5dataset}', **kwargs)[0]
        if self._avg_over_s_checkbox.isChecked() and self.ipypost4.slice_control.plot_axis_x == 'z':
            self.ax.plot(plot_xdata, np.mean(self.data, axis=1), linewidth=0.8, color=self.color, linestyle='--', label=f'Avg.{self.h5group}/{self.h5dataset}', **kwargs)
        if self._max_over_s_checkbox.isChecked() and self.ipypost4.slice_control.plot_axis_x == 'z':
            self.ax.plot(plot_xdata, np.max(self.data, axis=1), linewidth=0.8, color=self.color, linestyle=':', label=f'Max.{self.h5group}/{self.h5dataset}', **kwargs)
        
        self.ax.set_xlabel(plot_xlabel)
        self.ax.set_ylabel(f'{self.h5group} / {self.h5dataset} ' + self.get_unit())

        self.ipypost4.fig.suptitle(plot_title)

        self._find_peak()
        self._plot_yzero_line()

        self.ax.relim()
        self.ax.autoscale()
        self.ax.figure.canvas.toolbar.update()

        if self._log_y_scale_checkbox.isChecked():
            # self.ax.set_ylim(bottom=max(np.finfo(np.float32).tiny, np.min(self.line.get_ydata())))
            self.ax.set_yscale('log')
        else:
            self.ax.set_yscale('linear')
        self.ax.yaxis.set_major_formatter(self.unit_formatter)


        self.ax.yaxis.label.set_color(self.color)
        self.ax.tick_params(axis='y', colors=self.color)

class BriefLatticePlotUnit:
    ipypost4: "IPyPostGenesis4" = None
    ax: plt.Axes = None
    ax_twin: plt.Axes = None

    z_line: plt.Line2D = None

    def __init__(self, ipypost4: "IPyPostGenesis4", ax: plt.Axes):
        self.ipypost4 = ipypost4
        self.ax = ax
        self.ax_twin = self.ax.twinx()
        self.ax.axis('off')
        self.ax_twin.axis('off')
        self.ax.set_navigate(False)
        self.ax_twin.set_navigate(False)

    def preprocess_data(self): 
        self.z = self.ipypost4.h5_file['/Lattice/z'][()]
        aw = self.ipypost4.h5_file['/Lattice/aw'][()]
        qf = self.ipypost4.h5_file['/Lattice/qf'][()]

        self.ax.set_ylim(-np.max(np.abs(aw))*1.3, np.max(np.abs(aw))*1.3)
        self.ax_twin.set_ylim(-np.max(np.abs(qf))*1.05, np.max(np.abs(qf))*1.05)

        if np.max(np.abs(qf)) == 0:
            self.ax_twin.set_ylim(-1, 1)

        aw[aw==0] = None
        qf[qf==0] = None

        self.aw = aw
        self.qf = qf
    
    def plot_z_line(self):
        if self.z_line:
            self.z_line.set_xdata([self.ipypost4.slice_control.slice_value]*2)
        elif self.ipypost4.slice_control.plot_axis_x == 's':
            self.z_line = self.ax_twin.axvline(self.ipypost4.slice_control.slice_value, self.ax_twin.get_ylim()[0], self.ax_twin.get_ylim()[1]
                                               , linewidth=1.0, linestyle='--', color='red')
    
    def update_plot(self):
        self.plot_z_line()

    def plot_new(self):
        self.ax.clear()
        
        self.ax_twin.clear()
        # the clear() has automatically removes the z_line
        self.z_line = None
        
        self.preprocess_data()
        for f in np.linspace(0.01, 1.01, 18):
            self.ax.plot(self.z, self.aw*f, linewidth=0.6, color='orange', drawstyle='steps-post')
            self.ax_twin.plot(self.z, self.qf*f, linewidth=0.6, color='b', drawstyle='steps-post')

        self.ax.axis('off')
        self.ax_twin.axis('off')
        
        self.plot_z_line()

class FFTSpectrumPlotUnit(QtWidgets.QWidget):
    line: plt.Line2D = None
    data_tag: str = None

    __spectrum_min: float = None
    __spectrum_max: float = None
    def __init__(self, ipypost4: "IPyPostGenesis4", ax: plt.Axes):
        super().__init__()
        self.ipypost4 = ipypost4
        self.ax = ax

        self.setLayout(QtWidgets.QHBoxLayout())

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
        self.__show_fft_checkbox.stateChanged.connect(lambda state: self.ipypost4.set_fft_spectrum_visible(self.__show_fft_checkbox.isChecked()))
        layout.addWidget(self.__show_fft_checkbox)

        # setup fieldtype radio buttons
        self._fieldtype_widget = QtWidgets.QButtonGroup(self)
        self._fieldtype_widget.setExclusive(True)

        btn = QtWidgets.QPushButton('far', self)
        btn.setFixedWidth(60), btn.setCheckable(True), btn.setChecked(True)
        self._fieldtype_widget.addButton(btn)
        btn = QtWidgets.QPushButton('near', self)
        btn.setFixedWidth(60), btn.setCheckable(True)
        self._fieldtype_widget.addButton(btn)

        self._fieldtype_widget.buttonToggled.connect(self.on_fieldtype_change)

        self._fieldtype_layout = QtWidgets.QHBoxLayout()
        for btn in self._fieldtype_widget.buttons():
            self._fieldtype_layout.addWidget(btn)
        layout.addLayout(self._fieldtype_layout)

        # layout.addWidget(QtWidgets.QLabel('FFT Spectrum:'))
        self._harmsgroup_layout = QtWidgets.QHBoxLayout()
        for btn in self._harmsgroup_widget.buttons():
            self._harmsgroup_layout.addWidget(btn)
        layout.addLayout(self._harmsgroup_layout)

        self.__min_lambda_input = QtWidgets.QLineEdit(self)
        self.__min_lambda_input.setFixedWidth(100), self.__min_lambda_input.setValidator(QtGui.QDoubleValidator())
        self.__min_lambda_input.setPlaceholderText('min (nm)')
        self.__min_lambda_input.textChanged.connect(self.on_lambda_range_change)
        # when enter is pressed, the focus is lost and the signal is emitted
        self.__min_lambda_input.returnPressed.connect(self.on_lambda_range_change)
        layout.addWidget(self.__min_lambda_input)

        self.__max_lambda_input = QtWidgets.QLineEdit(self)
        self.__max_lambda_input.setFixedWidth(100), self.__max_lambda_input.setValidator(QtGui.QDoubleValidator())
        self.__max_lambda_input.setPlaceholderText('max (nm)')
        self.__max_lambda_input.textChanged.connect(self.on_lambda_range_change)
        # when enter is pressed, the focus is lost and the signal is emitted
        self.__max_lambda_input.returnPressed.connect(self.on_lambda_range_change)
        layout.addWidget(self.__max_lambda_input)

        self.layout().addLayout(layout)
    
    def on_fieldtype_change(self, btn, checked):
        self.ax.clear()
        self.plot_new()
        self.ax.figure.canvas.draw_idle()

    def on_harm_change(self, btn, checked):
        self.ax.clear()
        self.plot_new()
        self.ax.figure.canvas.draw_idle()

    def validated_lambda_range(self):
        if self.__spectrum_min is None or self.__spectrum_max is None:
            return None, None
        min_lambda = float(self.__min_lambda_input.text()) if self.__min_lambda_input.text() else self.__spectrum_min
        max_lambda = float(self.__max_lambda_input.text()) if self.__max_lambda_input.text() else self.__spectrum_max

        if min_lambda >= max_lambda or min_lambda >= self.__spectrum_max or max_lambda <= self.__spectrum_min:
            return self.__spectrum_min, self.__spectrum_max
        
        return min_lambda, max_lambda

    def on_lambda_range_change(self):
        _logger.debug(f"on_range_lambda_range_change, {self.__min_lambda_input.text()}, {self.__max_lambda_input.text()}")
        
        if self.__spectrum_min is None or self.__spectrum_max is None:
            return
        min_lambda, max_lambda = self.validated_lambda_range()
        
        self.ax.set_xlim(min_lambda, max_lambda)
        self.ax.figure.canvas.draw_idle()
    
    def fetch_data(self, loc='far'):
        self.group = self._harmsgroup_widget.checkedButton().text()
        self.harm = self.group.split('Field')[1]
        self.harm = int(1 if self.harm == '' else self.harm)

        loc = self._fieldtype_widget.checkedButton().text()

        if loc in ('far', 'near'):
            data_tag = f'/{self.group}/{loc}'
            if self.data_tag == data_tag:
                return
            self.intens, self.phase = self.ipypost4.fetch_data(f'/{self.group}/intensity-{loc}field', 
                                                               f'/{self.group}/phase-{loc}field')
            self.data_tag = data_tag
        else:
            raise ValueError('loc should be either "far" or "near"')


    def _rad_field(self):
        if self.ipypost4.slice_control._slice_at_z_idx in np.arange(self.intens.shape[0]):
            intens = self.intens[self.ipypost4.slice_control._slice_at_z_idx, :]
            phase = self.phase[self.ipypost4.slice_control._slice_at_z_idx, :]
        # not scaled properly!!!!
        field = np.sqrt(intens[:]) * np.exp(1j * phase[:])
        return field, self.harm
    
    def update_plot(self):
        field, harm = self._rad_field()
        spec = np.abs(np.fft.fft(field)) ** 2
        spec = np.fft.fftshift(spec)

        self.line.set_ydata(spec)
        self.ax.set_title(f'FFT Spectrum(a.u.),{self.ipypost4.zplot[self.ipypost4.slice_control._slice_at_z_idx]:.3f}m')
        self.ax.relim()
        if not self.ipypost4.lockyscale_checkbox.isChecked():
            self.ax.autoscale(axis='y')
    
    def plot_new(self):
        _logger.debug("FFTSpectrumPlotUnit.plot_new")
        self.fetch_data()

        s_values = self.ipypost4.s_values # units: um
        field, harm = self._rad_field()

        from scipy.constants import c

        s_values_m = s_values * 1e-6  # convert units from um to m

        time_values = s_values_m / c

        # calc FFT
        N = len(field)
        T = np.mean(np.diff(time_values))  
        freq = np.fft.fftfreq(N, d=T) + c/self.ipypost4.h5_file['/Global/lambdaref'][0]*harm  # 频率轴
        freq = np.fft.fftshift(freq)  # move the center frequency to the center of the spectrum


        spec = np.abs(np.fft.fft(field)) ** 2
        spec = np.fft.fftshift(spec)

        freq /= 1e9  # convert units from Hz to GHz

        self.ax.clear()
        # if self.line:
        #     self.line.remove()
        self.line, = self.ax.plot(c/freq, spec, linewidth=0.8, color='#1F77A4')
        self.ax.yaxis.tick_right()
        self.ax.set_title(f'FFT Spectrum(a.u.),{self.ipypost4.zplot[self.ipypost4.slice_control._slice_at_z_idx]:.3f}m')
        self.ax.set_xlabel(r'$\lambda$ (nm)')
        # self.ax.set_ylabel('Magnitude')
        # self.ax.legend()
        self.ax.grid(axis='x', linestyle=':', alpha=0.8)

        self.__spectrum_min = np.min(c/freq)
        self.__spectrum_max = np.max(c/freq)

        self.ax.set_xlim(self.validated_lambda_range())
    
    def reinit(self):
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

@dataclass
class SliceControl(QtWidgets.QWidget):
    ipypost4: "IPyPostGenesis4" = None

    @property
    def plot_axis_x(self):
        return self._plot_axis_x_widget.checkedButton().text() if self._plot_axis_x_widget else None
    @plot_axis_x.setter
    def plot_axis_x(self, value):
        if value not in ['s', 'z']:
            raise ValueError(f"Invalid plot_axis_x value: {value}")
        for btn in self._plot_axis_x_widget.buttons():
            if btn.text() == value:
                btn.setChecked(True)

    @property
    def current_x_data(self):    
        if self.plot_axis_x == 's':
            return self.ipypost4.s_values
        else:
            return self.ipypost4.zplot
    @property
    def slice_options(self):
        if self.plot_axis_x == 's':
            return self.ipypost4.zplot
        else:
            return self.ipypost4.s_values

    @property
    def slice_value(self):
        if self.plot_axis_x == 's':
            return self.ipypost4.zplot[self._slice_at_z_idx]
        else:
            return self.ipypost4.s_values[self._slice_at_s_idx]
        
    @slice_value.setter
    def slice_value(self, value):
        _logger.debug("SliceControl.slice_value setter: value={}".format(value))
        if self.plot_axis_x == 's':
            z_idx = np.argmin(np.abs(self.ipypost4.zplot - value))
            self._slice_at_z_idx = z_idx
            self._slice_value_slider.setValue(z_idx)
        else:
            s_idx = np.argmin(np.abs(self.ipypost4.s_values - value)) 
            self._slice_at_s_idx = s_idx
            self._slice_value_slider.setValue(s_idx)

    _slice_at_z_idx = 0
    _slice_at_s_idx = 0

    def init(self):
        super().__init__()
        self.setLayout(QtWidgets.QHBoxLayout())

        self._plot_axis_x_widget = QtWidgets.QButtonGroup()
        self.__s_btn = QtWidgets.QPushButton('s')
        self.__s_btn.setCheckable(True)
        self.__s_btn.setChecked(True)
        self.__z_btn = QtWidgets.QPushButton('z')
        self.__z_btn.setCheckable(True)
        self._plot_axis_x_widget.addButton(self.__s_btn, id=0)
        self._plot_axis_x_widget.addButton(self.__z_btn, id=1)
        self._plot_axis_x_widget.buttonToggled.connect(self.on_plot_axis_x_change)
        
        self._slice_value_slider = QtWidgets.QSlider(orientation=QtCore.Qt.Horizontal)
        self._slice_value_slider.setMinimum(0)
        self._slice_value_slider.setMaximum(len(self.ipypost4.zplot)-1)
        self._slice_value_slider.setSingleStep(1)
        self._slice_value_slider.setPageStep(4)
        self._slice_value_slider.setValue(0)
        self._slice_value_slider.valueChanged.connect(self.on_slice_value_change)

        self._slice_value_label = QtWidgets.QLabel("0.00")
        self._slice_value_label.setMinimumWidth(80)
        self._slice_value_label.setAlignment(QtCore.Qt.AlignCenter)

        plus_widget = QtWidgets.QPushButton('+')
        plus_widget.clicked.connect(lambda: self._slice_value_slider.setValue(min(self._slice_value_slider.value() + 1, self._slice_value_slider.maximum()-1)))
        minus_widget = QtWidgets.QPushButton('-')
        minus_widget.clicked.connect(lambda: self._slice_value_slider.setValue(max(self._slice_value_slider.value() - 1, 0)))

        self.layout().addWidget(self.__s_btn)
        self.layout().addWidget(self.__z_btn)
        self.layout().addWidget(self._slice_value_slider)
        self.layout().addWidget(self._slice_value_label)
        self.layout().addWidget(minus_widget)
        self.layout().addWidget(plus_widget)

       
    def reinit(self):
        self._slice_value_slider.blockSignals(True)
        self._slice_value_slider.setMaximum(self.ipypost4.zplot.shape[0]-1 if self.plot_axis_x == 's' else self.ipypost4.s_values.shape[0]-1)
        self._slice_value_slider.blockSignals(False)
        self._slice_at_s_idx = min(self._slice_at_s_idx, len(self.ipypost4.s_values)-1)
        self._slice_at_z_idx = min(self._slice_at_z_idx, len(self.ipypost4.zplot)-1)

    def on_plot_axis_x_change(self, change: QtWidgets.QPushButton, checked: bool):
        if not checked: return
        _logger.debug("SliceControl.on_plot_axis_x_change: new value={}".format(change))
        self._slice_value_slider.blockSignals(True)
        if change.text() == 's':
            self._slice_value_slider.setMaximum(len(self.ipypost4.zplot)-1)
            self._slice_value_slider.setValue(self._slice_at_z_idx)
            # self._slice_value_slider.description = 'At z(m)  :'
        else:
            self._slice_value_slider.setMaximum(len(self.ipypost4.s_values)-1)
            self._slice_value_slider.setValue(self._slice_at_s_idx)
            # self._slice_value_slider.description = 'At s(um) :'

        self.ipypost4.plot_new_dataset()
        self._slice_value_slider.blockSignals(False)

        # upate _slice_value_label becaue after unobserve, the value of _slice_at_z_idx or _slice_at_s_idx was changed
        if self.plot_axis_x == 's':
            self._slice_value_label.setText(f"{self.ipypost4.zplot[self._slice_at_z_idx]:.3f}")
        else:
            self._slice_value_label.setText(f"{self.ipypost4.s_values[self._slice_at_s_idx]:.3f}")
        _logger.debug("SliceControl.on_plot_axis_x_change end")
        
    def on_slice_value_change(self, idx):
        if self.plot_axis_x == 's':
            _logger.debug("SliceControl.on_slice_value_change: new value={}".format(self.ipypost4.zplot[idx]))
            self._slice_at_z_idx = idx
            self._slice_value_label.setText(f"{self.ipypost4.zplot[idx]:.3f}")
        else:
            _logger.debug("SliceControl.on_slice_value_change: new value={}".format(self.ipypost4.s_values[idx]))
            self._slice_at_s_idx = idx
            self._slice_value_label.setText(f"{self.ipypost4.s_values[idx]:.3f}")

        self.ipypost4.update_plot_slice()
        _logger.debug("SliceControl.on_slice_value_change end")


class GifExporter(QtWidgets.QWidget):
    ipypost4: "IPyPostGenesis4" = None

    def __init__(self, ipypost4: "IPyPostGenesis4"):
        self.ipypost4 = ipypost4

    def init(self):
        super().__init__()

        self.setLayout(QtWidgets.QHBoxLayout())

        self.export_dialog = WaitingDialog(self, "Exporting GIF", "Writing GIF to file...")

        self.export_btn = QtWidgets.QPushButton('export gif')
        self.export_btn.released.connect(self.export_gif)
        self.layout().addWidget(self.export_btn)

        self.text_from = QtWidgets.QLineEdit('0')
        self.text_from.setValidator(QtGui.QDoubleValidator()); self.text_from.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('From:')); self.layout().addWidget(self.text_from)

        self.text_to = QtWidgets.QLineEdit('30')
        self.text_to.setValidator(QtGui.QDoubleValidator()); self.text_to.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('To:')); self.layout().addWidget(self.text_to)

        self.text_step = QtWidgets.QLineEdit('4')
        self.text_step.setValidator(QtGui.QIntValidator()); self.text_step.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('Step(index):')); self.layout().addWidget(self.text_step)

        self.text_interval = QtWidgets.QLineEdit('50')
        self.text_interval.setValidator(QtGui.QIntValidator()); self.text_interval.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('Interval(ms):')); self.layout().addWidget(self.text_interval)

        self.text_pausetime = QtWidgets.QLineEdit('500')
        self.text_pausetime.setValidator(QtGui.QIntValidator()); self.text_pausetime.setFixedWidth(60)
        self.layout().addWidget(QtWidgets.QLabel('Pause(ms):')); self.layout().addWidget(self.text_pausetime)

        self.text_path = QtWidgets.QLineEdit('ipygenesis4.gif')
        self.text_path.setMinimumWidth(400)
        self.layout().addWidget(QtWidgets.QLabel('Path:')); self.layout().addWidget(self.text_path)

    def update_plot_slice(self, value):
        self.ipypost4.slice_control.slice_value = value
        QtWidgets.QApplication.processEvents()
        return
    
    def export_gif(self):
        import matplotlib.animation as animation
        slice_options = self.ipypost4.slice_control.slice_options
        start_idx = np.argmin(np.abs(slice_options - float(self.text_from.text())))
        end_idx = np.argmin(np.abs(slice_options - float(self.text_to.text())))
        frames = slice_options[start_idx:(end_idx+1):int(self.text_step.text())]
        frames = np.append(frames, [slice_options[end_idx]]*int(abs(int(self.text_pausetime.text())/int(self.text_interval.text())) + 1))
        
        ani = animation.FuncAnimation(self.ipypost4.fig, self.update_plot_slice, repeat=False, 
                                      frames=frames, interval=float(self.text_interval.text()))
        
        self.export_dialog.show()

        ani.save(self.text_path.text(), writer='pillow', 
                 progress_callback=lambda i, n: i+1==n or QtWidgets.QApplication.processEvents())
        del ani

        self.export_dialog.accept()

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
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanva
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

class WinCopyableNavigationToolbar(NavigationToolbar):
    toolitems = NavigationToolbar.toolitems + [
        ('Copy\nImg', 'Copy the figure to clipboard', 'copy', 'copy_figure'),
    ]

    def copy_figure(self):
        import io
        import win32clipboard
        from PIL import Image
        buf = io.BytesIO()
        self.canvas.figure.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)

        # 使用 PIL 加载图像
        image = Image.open(buf)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # 去掉 BMP 文件头
        output.close()
        buf.close()

        # 打开剪贴板并写入图像数据
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        finally:
            win32clipboard.CloseClipboard()

class Genesis4MetaDataWindow(QtWidgets.QWidget):
    meta_data: dict = {}
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Genesis4 MetaData')
        self.resize(1000, 1000)

        self.__meta_category_widget = QtWidgets.QButtonGroup(self)
        self.__meta_category_widget.setExclusive(True)
        self.__meta_category_widget.buttonToggled.connect(lambda btn, checked: self.__meta_text.setText(self.meta_data[btn.text()]))

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
    def set_meta_data(self, meta_data:dict, path:str):
        _logger.debug(f'Genesis4MetaDataWindow.set_meta_data: meta_data={meta_data}')
        for btn in self.__meta_category_widget.buttons():
            self.__meta_category_widget.removeButton(btn)
            self.__meta_category_layout.removeWidget(btn)
            del btn
        
        self.meta_data = meta_data
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
        
    def parse_meta_data(h5_file:h5py.File):
        meta_data = {}
        if '/Meta' not in h5_file.keys():
            return meta_data
        meta_data['Overview'] = Genesis4MetaDataWindow.__parse_meta_dataset(h5_file['/Meta/'])

        if 'InputFile' in h5_file['/Meta'].keys():
            meta_data['InputFile'] = str(h5_file['/Meta/InputFile'][0], encoding='utf-8')
        
        if 'LatticeFile' in h5_file['/Meta'].keys():
            meta_data['LatticeFile'] = str(h5_file['/Meta/LatticeFile'][0], encoding='utf-8')

        return meta_data
    
    def __parse_meta_dataset(obj, result=''):
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


# pre-load data for faster response
class IPyPostGenesis4Builder:
    def __init__(self, h5_file:h5py.File=None):
        self.h5_file = h5_file
        self.zplot = np.round(h5_file['/Lattice/zplot'][:], 3)
        self.s_values = np.round(h5_file['/Global/s'][:]*1e6, 3)
        self.h5group_options = ['Beam','Lattice']
        for group_name in h5_file.keys():
            if group_name.startswith('Field'):
                self.h5group_options.append(group_name)
                # break
        self.dataset_in_groups = {group: [name for name in h5_file[f'/{group}'].keys() if not name.startswith('Global') ] 
                                 for group in self.h5group_options}
        # print(self.dataset_in_groups)

class IPyPostGenesis4(QtWidgets.QWidget):
    _instances = {} 

    def __new__(cls, builder, igui_id:int=0, **kwargs):
        if igui_id not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[igui_id] = instance
            instance._initialized = False
        return cls._instances[igui_id]
    
    @property
    def second_curve(self):
        return self.second_curve_checkbox.isChecked() if self.second_curve_checkbox else None
    @second_curve.setter
    def second_curve(self, value):
        self.second_curve_checkbox.setChecked(value)
        
    def __init__(self, builder:IPyPostGenesis4Builder, plot_config:dict=default_plot_config, force_config:bool=False, igui_id:int=0):
        self.h5_file = builder.h5_file
        self.zplot = builder.zplot
        self.s_values = builder.s_values
        self.h5group_options = builder.h5group_options
        for group_name in self.h5group_options:
            if group_name.startswith('Field'):
                default_plot_config['plot_unit2']['h5group'] = group_name
        self.dataset_in_groups = builder.dataset_in_groups

        # 初始化绘图
        if not self._initialized:
            super().__init__()
            self.setLayout(QtWidgets.QVBoxLayout())
            self.wait_data_dialog = WaitingDialog(self.window(), title="Waiting...", message="Waiting for data...")

            self.fig = plt.figure(figsize=(20, 40), dpi=120)
            self.fig.subplots_adjust(top=0.88, bottom=0.12, left=0.08, right=0.95, hspace=0.1, wspace=0.2)
            self.gs = self.fig.add_gridspec(1, 3, width_ratios=[12, 1, 4], wspace=0.04)
            self.gs.set_width_ratios([12, 0.1, 0.1])

            self.main_ax = self.fig.add_subplot(self.gs[0])
            self.feature_ax = self.fig.add_subplot(self.gs[2])

            self.feature_ax.set_visible(False)
            self.fig.canvas.draw_idle()

            # self.fig_width_px = self.fig.get_size_inches()[0] * self.fig.dpi
            self.lattice_ax = self.fig.add_axes(self.parse_lattice_ax_posision())
            self.lattice_plot_unit = BriefLatticePlotUnit(ipypost4=self, ax=self.lattice_ax)

            self.slice_control = SliceControl(ipypost4=self)
            self.slice_control.init()

            self.plot_unit1 = MainPlotUnit(ipypost4=self, ax=self.main_ax, slice_control=self.slice_control, color='#00739c', label='1')
            self.plot_unit2 = MainPlotUnit(ipypost4=self, ax=self.main_ax.twinx(), slice_control=self.slice_control, color='#e24200', label='2')
            self.plot_unit2.ax.set_visible(False)

            self.plot_unit1.init()
            self.plot_unit2.init()

            self.fft_spectrum_plot_unit = FFTSpectrumPlotUnit(ipypost4=self, ax=self.feature_ax)

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
            self.lockyscale_checkbox.stateChanged.connect(lambda change:self.update_plot_slice() if not change else None)
            aux_group.addWidget(self.second_curve_checkbox)
            aux_group.addWidget(self.lockyscale_checkbox)
            aux_group.addWidget(self.lattice_plot_checkbox)
            aux_group.addStretch(1)
            aux_group.addWidget(self.fft_spectrum_plot_unit)

            self._fig_widget = FigureCanva(self.fig)
            self.opitions_group = QtWidgets.QGroupBox('Options')
            self.opitions_group.setLayout(QtWidgets.QHBoxLayout())
            self.opitions_group.layout().addWidget(self.plot_unit1)
            space_between = QtWidgets.QLabel(); space_between.setMaximumWidth(100)
            self.opitions_group.layout().addWidget(space_between)
            self.opitions_group.layout().addWidget(self.plot_unit2)

            self.layout().addWidget(self.opitions_group)
            self.layout().addWidget(self.slice_control)
            self.layout().addLayout(aux_group)


            self.layout().addWidget(self._fig_widget)
            if platform.system() == 'Windows':
                self.layout().addWidget(WinCopyableNavigationToolbar(self._fig_widget, self))
            else:
                self.layout().addWidget(NavigationToolbar(self._fig_widget, self))

            self.gifexporter = GifExporter(ipypost4=self)
            self.gifexporter.init()

            self.layout().addWidget(self.gifexporter)
            self.layout().setContentsMargins(5, 10, 5, 0)
        else:
            self.plot_unit1.reinit()
            self.plot_unit2.reinit()

            self.slice_control.reinit()
            self.fft_spectrum_plot_unit.reinit()
        
        if not self._initialized or force_config:
            self.__apply_plot_config(plot_config)

        self._initialized = True  

        self.plot_new_dataset()

    def __apply_plot_config(obj, plot_config:dict):
        if plot_config is None:
            return    
        for key, value in plot_config.items():
            if isinstance(value, dict):
                IPyPostGenesis4.__apply_plot_config(getattr(obj, key), value)
            else:
                setattr(obj, key, value)

    def parse_lattice_ax_posision(self):
        pos = self.main_ax.get_position()
        new_height = pos.height/15
        return [pos.x0, pos.y0 + pos.height + new_height/4, pos.width, new_height]
    
    def fetch_data(self, *data_path:str):
        if not self._initialized:
            return
        self.wait_data_dialog.show()

        res = []
        for path in data_path:
            data = self.h5_file[path][()]
            if len(data.shape) == 1:
                data = np.append(data, [data[-1]]*(len(self.zplot) - data.shape[0]))
                data = data[:, np.newaxis].repeat(self.s_values.shape[0], axis=1)

            if data.shape[0] == 1:
                data = data.repeat(self.zplot.shape[0], axis=0)
            res.append(data)

        self.wait_data_dialog.accept()
        if len(res) == 1:
            return res[0]
        else:
            return res

    def set_fft_spectrum_visible(self, visible:bool):
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

    def on_second_curve_checkbox_change(self, change):
        _logger.debug("IPyPostGenesis4.on_second_curve_checkbox_change: new value={}".format(change))
        if change:
            self.plot_unit2.ax.set_visible(True)
            self.plot_new_dataset()
        else:
            self.plot_unit2.ax.set_visible(False)
            self.fig.canvas.draw_idle()
        
    
    def on_lattice_plot_checkbox_change(self, change):
        _logger.debug("IPyPostGenesis4.on_lattice_plot_checkbox_change: new value={}".format(change))
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
        if not self._initialized:
            return
        self.fig.canvas.toolbar._nav_stack.back()
        
        # update plot and autoscale
        self.plot_unit1.update_plot()
        if self.plot_unit2.ax.get_visible():
            self.plot_unit2.update_plot()
        
        if self.slice_control.plot_axis_x == 's' and self.fft_spectrum_plot_unit.ax.get_visible():
            # fft_spectrum only update when z changed
            self.fft_spectrum_plot_unit.update_plot()
        if self.lattice_plot_unit.ax.get_visible():
            self.lattice_plot_unit.update_plot()

        # store locked lim and scale
        self.fig.canvas.toolbar.push_current()
        locked_scale = self.fig.canvas.toolbar._nav_stack()
        self.fig.canvas.toolbar._nav_stack.back()
        
        # push all-view scale to toolbar home scale
        self.plot_unit1.ax.relim(), self.plot_unit2.ax.relim()
        self.plot_unit1.ax.autoscale(), self.plot_unit2.ax.autoscale()
        if self.slice_control.plot_axis_x == 's' and self.fft_spectrum_plot_unit.ax.get_visible():
            self.fft_spectrum_plot_unit.ax.relim()
            self.fft_spectrum_plot_unit.ax.autoscale()

        self.fig.canvas.toolbar.push_current()
        self.fig.canvas.toolbar._nav_stack._elements[0] = self.fig.canvas.toolbar._nav_stack()
        self.fig.canvas.toolbar._nav_stack.back()

        #restore locked scale
        self.fig.canvas.toolbar._nav_stack.push(locked_scale)
        
        self.fig.canvas.toolbar._update_view() # fig.canvas.draw_idle() called inside
        # self.fig.canvas.draw_idle()
            
    def plot_new_dataset(self):
        if not self._initialized:
            return

        _logger.debug('enter plot_new_dataset')
        self.plot_unit1.plot_new(antialiased=True)
        self.plot_unit1.ax.grid(axis='x', linestyle=':', alpha=0.8)
        # self.plot_unit1.ax.legend(loc="upper left")

        if self.second_curve_checkbox.isChecked():
            self.plot_unit2.plot_new(antialiased=True)
            # self.plot_unit2.ax.legend(loc="upper right")
            # self.plot_unit2.ax.spines['left'].set_position(('outward', 0))
        if self.fft_spectrum_plot_unit.ax.get_visible():
            self.fft_spectrum_plot_unit.plot_new()
        if self.lattice_plot_checkbox.isChecked():
            self.lattice_plot_unit.plot_new()
        self.fig.canvas.draw_idle()
        _logger.debug('leave plot_new_dataset')



class G4LikeGenesisOutput:
    '''
    Genesis output *.out files storage object
    '''

    def __init__(self):
        self.z = []
        self.s = []
        self.I = []
        self.n = []
        self.E = []
        self.aw = []
        self.qfld = []

        self.sliceKeys = []
        self.sliceValues = {}

        self.parameters = {}
        self.filePath = ''

        self.InputFile = ''
        self.SliceData = ''

    def fileName(self):
        return os.path.basename(self.filePath)

    def __call__(self, name):

        if name not in self.parameters.keys():
            return None
        else:
            p, = self.parameters[name]
            return float(p.replace('D', 'E'))

        
import time
def _read_genesis2_out(filePath):
    '''
    reads Genesis output from *.out file.
    copy from ocelot and modify for convert to Genesis4
    '''
    ind_str = '  '
    import re
    out = G4LikeGenesisOutput()
    out.filePath = filePath

    _logger.info('reading genesis2 {} file'.format(os.path.basename(filePath)))
    _logger.debug(ind_str + 'reading from ' + filePath)
    
    
    chunk = ''
    output_unsorted = []
    nSlice = 0

    if os.path.getsize(out.filePath) == 0:
        _logger.error(ind_str + 'file "' + out.filePath + '" has zero size')
        raise IOError('File ' + out.filePath + ' has zero size')
    
    start_time = time.time()

    with open(out.filePath, 'r') as f:
        null = f.readline()
        for line in f:
            QtWidgets.QApplication.processEvents()
            tokens = line.strip().split()

            if len(tokens) < 1:
                continue

            if tokens[0] == '**********':
                chunk = 'slices'
                nSlice = int(tokens[3])
                _logger.log(5, ind_str + 'reading slice # ' + str(nSlice))

            if tokens[0] == 'power':
                out.SliceData = ",".join(line.strip().split())
                chunk = 'slice'
                if len(out.sliceKeys) == 0:  # to record the first instance
                    out.sliceKeys = list(tokens)
                    _logger.debug(ind_str + 'reading slice values ')
                
                output_unsorted.append(np.loadtxt(f, max_rows=int(out('entries_per_record'))))
                continue

            if tokens[0] == '$newrun':
                out.InputFile += line
                chunk = 'input1'
                _logger.debug(ind_str + 'reading input parameters')
                continue

            if tokens[0] == '$end':
                out.InputFile += line
                chunk = 'input2'
                continue

            if tokens == ['z[m]', 'aw', 'qfld']:
                chunk = 'magnetic optics'
                _logger.debug(ind_str + 'reading magnetic optics ')
                continue

            if chunk == 'magnetic optics':
                z, aw, qfld = list(map(float, tokens))
                out.z.append(z)
                out.aw.append(aw)
                out.qfld.append(qfld)

            if chunk == 'input1':
                out.InputFile += line
                tokens = line.replace('=', '').strip().split()
                out.parameters[tokens[0]] = tokens[1:]
                #out.parameters[tokens[0]] = tokens[0:]
            if chunk == 'input2':
                tokens = line.replace('=', '').strip().split()
                out.parameters['_'.join(tokens[1:])] = [tokens[0]]
                #out.parameters[tokens[0]] = tokens[0:]

            if chunk == 'slice':
                try:
                    vals = list(map(float, tokens))
                except ValueError:
                    _logger.log(5, ind_str + 'wrong E value, fixing')
                    _logger.log(5, ind_str + str(tokens))
                    tokens_fixed = re.sub(r'([0-9])\-([0-9])', r'\g<1>E-\g<2>', ' '.join(tokens))
                    tokens_fixed = re.sub(r'([0-9])\+([0-9])', r'\g<1>E+\g<2>', tokens_fixed)
                    tokens_fixed = tokens_fixed.split()
                    _logger.log(5, ind_str + str(tokens_fixed))
                    vals = list(map(float, tokens_fixed))

                output_unsorted.append(vals)

            if chunk == 'slices':
                if len(tokens) == 2 and tokens[1] == 'current':
                    out.I.append(float(tokens[0]))
                    out.n.append(nSlice)
                elif len(tokens) == 3 and tokens[1] == 'scan':
                    out.I.append(float(tokens[0]))
                    out.n.append(nSlice)

    #check for consistency
    if chunk == '':
        _logger.error(ind_str + 'File "' + out.filePath + '" has no genesis output information or is corrupted')
        raise ValueError('File "' + out.filePath + '" has no genesis output information or is corrupted')
    
    for parm in ['z', 'aw', 'qfld', 'I', 'n']:
        setattr(out, parm, np.array(getattr(out, parm)))

    if out('dgrid') == 0:
        rbeam = np.sqrt(out('rxbeam')**2 + out('rybeam')**2)
        ray = np.sqrt(out('zrayl') * out('xlamds') / np.pi * (1 + (out('zwaist') / out('zrayl'))**2))
        out.leng = out('rmax0') * (rbeam + ray)
    else:
        out.leng = 2 * out('dgrid')
    out.ncar = int(out('ncar'))  # number of mesh points
    
    #universal solution?
    out.leng=out('meshsize')*(out.ncar-1)
    

    out.nSlices = len(out.n)
    if out('entries_per_record') is None:
        _logger.error(ind_str + 'In file "' + out.filePath + '" file header is missing')
        raise ValueError('In file "' + out.filePath + '" file header is missing')
    
    out.nZ = int(out('entries_per_record'))  # number of records along the undulator
    _logger.debug(ind_str + 'nSlices ' + str(out.nSlices))
    _logger.debug(ind_str + 'nZ ' + str(out.nZ))

    if nSlice == 0:
        _logger.error(ind_str + 'In file "' + out.filePath + '" number of recorded slices is zero')
        raise ValueError('In file "' + out.filePath + '" number of recorded slices is zero')

    n_missing = (out.n[-1] - out.n[0]) - (len(out.n) - 1) * out('ishsty')
    if n_missing != 0:
        _logger.error(ind_str + 'File "' + out.filePath + '" is missing at least ' + str(n_missing) + ' slices')
        raise ValueError('File "' + out.filePath + '" is missing at least ' + str(n_missing) + ' slices')
    

    output_unsorted = np.array(output_unsorted)
    _logger.debug('output_unsorted.shape = ' + str(output_unsorted.shape))
    _logger.debug(ind_str + 'out.sliceKeys' + str(out.sliceKeys))
    for i in range(len(out.sliceKeys)):
        key = out.sliceKeys[int(i)]
        _logger.debug(ind_str + 'key = ' + str(key))
        if key[0].isdigit():
            hn = key[0]
            if 'bunch' in key:
                key = 'bunching'
            elif 'phase' in key:
                key = 'phi_mid'
            elif 'p-mid' in key:
                key = 'p_mid'
            elif 'power' in key:
                key = 'power'
            else:
                pass
            key='h{:}_'.format(hn)+key
            _logger.debug(2*ind_str + 'key_new = ' + str(key))
            
        setattr(out, key.replace('-', '_').replace('<', '').replace('>', ''), output_unsorted[:,:,i])
        # setattr(out, key.replace('-', '_').replace('<', '').replace('>', ''), output_unsorted[:,i].reshape((int(out.nSlices), int(out.nZ))))
    if hasattr(out, 'energy'):
        out.energy += out('gamma0')
    out.power_z = np.max(out.power, 0)
    out.sliceKeys_used = out.sliceKeys

    if out('itdp') == True:
        out.s = out('zsep') * out('xlamds') * (out.n - out.n[0])  # np.arange(0,out.nSlices)
        out.t = out.s / speed_of_light * 1.e+15
        out.dt = (out.t[1] - out.t[0]) * 1.e-15
        # out.dt=out('zsep') * out('xlamds') / speed_of_light
        out.beam_charge = np.sum(out.I * out.dt)
        out.sn_Imax = np.argmax(out.I)  # slice number with maximum current
        
        out.pulse_energy = np.sum(out.power * out.dt, axis=0)
            
    else:
        out.s = [0]
    
    if out('iscan') != 0:
        out.scv = out.I  # scan value
        out.I = np.linspace(1, 1, len(out.scv))  # because used as a weight
    
    _logger.debug(ind_str + 'done in %.2f seconds' % (time.time() - start_time))
    return out

def convert_genesis2_output_to_genesis4_hdf5(filePath, outfilePath=None):
    g2 = _read_genesis2_out(filePath)
    outfilePath = outfilePath or filePath + '_ipypostgenesis4.out.h5'

    with h5py.File(outfilePath, 'w') as g4:
        meta_group = g4.create_group('Meta')
        meta_group.create_dataset('AAA', data=["Converted from Genesis1.3-Version2 output by pyqt5post_genesis4.pyw"], dtype="|S128")
        meta_group.create_dataset('SliceData', data=[g2.SliceData], dtype="|S" + str(len(g2.SliceData)))
        meta_group.create_dataset('InputFile', data=[g2.InputFile], dtype="|S" + str(len(g2.InputFile)))

        lattice_group = g4.create_group('Lattice')
        lattice_group.create_dataset('zplot', data=g2.z)
        lattice_group.create_dataset('z', data=g2.z)
        lattice_group.create_dataset('aw', data=g2.aw)
        lattice_group.create_dataset('qf', data=g2.qfld)

        global_group = g4.create_group('Global')
        global_group.create_dataset('s', data=g2.s)
        global_group.create_dataset('lambdaref', data=[g2('xlamds')], dtype='<f8')
        global_group.create_dataset('gamma0', data=[g2('gamma0')], dtype='<f8')
        global_group.create_dataset('one4one', data=[0], dtype='<f8')
        global_group.create_dataset('sample', data=[g2('zsep')], dtype='<f8')
        # TODO: add support for scan, slen, time, frequency in global_group

        beam_group = g4.create_group('Beam')
        field_group = g4.create_group('Field')
        # from out with replace('-', '_').replace('<', '').replace('>', '')
        beam_map = {
            'energy': ('energy', 'mc^2'),
            'e_spread': ('energyspread', 'mc^2'),
            'bunching': ('bunching', ''),
            'xrms': ('xsize', 'm'),
            'yrms': ('ysize', 'm'),
            'x': ('xposition', 'm'),
            'y': ('yposition', 'm')
        }
        for key in (set(beam_map) & set(vars(g2).keys())):
            dset = beam_group.create_dataset(beam_map[key][0], data=getattr(g2, key).T)
            dset.attrs['unit'] = np.bytes_(beam_map[key][1])
            QtWidgets.QApplication.processEvents()
        dset = beam_group.create_dataset('current', data=g2.I[None, :])
        dset.attrs['unit'] = np.bytes_('A')

        field_map = {
            'power': ('power', 'W'),
            'far_field': ('intensity-farfield', 'W/rad^2'),
            'p_mid': ('intensity-nearfield', ''),
            'phi_mid': ('phase-nearfield', 'rad'),
            'r_size': ('r_size', 'm'),
            'angle': ('angle', 'rad')
        }
        for key in (set(field_map) & set(vars(g2).keys())):
            dset = field_group.create_dataset(field_map[key][0], data=getattr(g2, key).T)
            dset.attrs['unit'] = np.bytes_(field_map[key][1])
            QtWidgets.QApplication.processEvents()
        # TODO: add support for harmonics out.

        del g2
        return g4.filename

class SyncQtApplicationFileReader:
    "Read file with `QtWidgets.QApplication.processEvents()` to avoid GUI blocking"

    largeread_update_gui_bytes = 32 * 1024
    smallread_threshold_bytes = 1024

    def __init__(self, path:str):
        self.__file = open(path, 'rb')
        self.total_read = 0
    
    def read(self, n:int) -> bytes:
        _logger.debug('SyncQtApplicationFileReader read {} bytes'.format(n))
        if n <= self.smallread_threshold_bytes:
            return self.__file.read(n)

        data = bytearray()
        remaining = n
        while remaining > 0:
            # if self.total_read >= self.largeread_update_gui_bytes:
            #     _logger.debug('SyncQtApplicationFileReader update GUI after {} bytes'.format(self.largeread_update_gui_bytes))
            #     QtWidgets.QApplication.processEvents()
            #     self.total_read %= self.largeread_update_gui_bytes

            read_size = min(remaining, self.largeread_update_gui_bytes)
            chunk = self.__file.read(read_size)
            if not chunk: 
                break
            data += chunk

            remaining -= len(chunk)
            self.total_read += len(chunk)
            QtWidgets.QApplication.processEvents()

        return bytes(data)
    
    def seek(self, offset:int, whence:int=0) -> int:
        # _logger.debug('SyncQtApplicationFileReader seek {} {}'.format(offset, whence))
        return self.__file.seek(offset, whence)
    
    def close(self) -> None:
        # _logger.debug('SyncQtApplicationFileReader close')
        self.__file.close()
    def tell(self) -> int:
        # _logger.debug('SyncQtApplicationFileReader tell')
        return self.__file.tell()

class PostGenesis4MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(PostGenesis4MainWindow, self).__init__(parent)
        self.setWindowTitle('PyPostGenesis4')
        self.resize(1650, 1150)

        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)

        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)

        # input file selection
        self.wait_file_dialog = WaitingDialog(self, 'Waiting for file loading...', 'Loading Genesis4 output file...')
        self.wait_file_thread = QtCore.QThread()
        self.wait_file_thread.run = self.select_history_file
        self.wait_file_thread.started.connect(self.wait_file_dialog.show)
        self.wait_file_thread.finished.connect(self.wait_file_dialog.accept)

        self.file_input = QtWidgets.QLineEdit()
        self.file_input.setMinimumWidth(300)
        self.file_input.setPlaceholderText('Enter file path')
        self.file_history_widget = QtWidgets.QComboBox()
        self.file_history_widget.setMinimumWidth(800)
        self.file_history_widget.currentTextChanged.connect(self.wait_file_thread.start)

        self.file_button = QtWidgets.QPushButton('Open')
        self.file_reopen_button = QtWidgets.QPushButton('Reopen')
        self.file_clear_other_button = QtWidgets.QPushButton('Clear')
        self.file_button.clicked.connect(self.open_input_file)
        self.file_reopen_button.clicked.connect(self.wait_file_thread.start)
        self.file_clear_other_button.clicked.connect(self.file_history_widget.clear)

        self.btn_meta_data = QtWidgets.QPushButton('Meta')
        self.meta_data_window = Genesis4MetaDataWindow()
        self.btn_meta_data.clicked.connect(self.show_meta_data)

        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_layout.addWidget(QtWidgets.QLabel('Input file:'))
        self.file_layout.addWidget(self.file_input)
        self.file_layout.addWidget(self.file_history_widget)
        self.file_layout.addWidget(self.file_button)
        self.file_layout.addWidget(self.file_reopen_button)

        self.file_layout = QtWidgets.QHBoxLayout()
        self.file_layout.addWidget(QtWidgets.QLabel('Input file:'))
        self.file_layout.addWidget(self.file_input)
        self.file_layout.addWidget(self.file_history_widget)
        self.file_layout.addWidget(self.file_button)
        self.file_layout.addWidget(self.file_reopen_button)
        self.file_layout.addWidget(self.btn_meta_data)
        self.file_layout.addWidget(self.file_clear_other_button)
        self.main_layout.addLayout(self.file_layout)

        self.post_layout = QtWidgets.QHBoxLayout()
        self.tip_label = QtWidgets.QLabel(tip)
        self.tip_label.setStyleSheet("QLabel { font-size: 26px; font-family: Times New Roman; }")
        self.tip_label.setContentsMargins(60, 30, 60, 10)
        self.tip_label.setWordWrap(True)
        self.post_layout.addWidget(self.tip_label)
        self.main_layout.addLayout(self.post_layout)

    def show_meta_data(self):
        if self.h5_file:
            self.meta_data_window.show()
            self.meta_data_window.activateWindow()

    _post_widget:IPyPostGenesis4 = None
    def open_input_file(self):
        if self.file_input.text():
            fileName = self.file_input.text()
            fileName = fileName.strip("\"").strip()

            if not os.path.isfile(fileName):
                QtWidgets.QMessageBox.warning(self, 'Warning', 'File not found: {}'.format(fileName))
                return
            if not fileName.endswith('.out') and not fileName.endswith('.out.h5'):
                QtWidgets.QMessageBox.warning(self, 'Warning', 'File type not supported: {}'.format(fileName))
                return
            self.add_file_history([fileName])
            self.file_input.clear()

        else:
            options = QtWidgets.QFileDialog.Options()

            fileName, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "选择文件", "", "Genesis2/4 (*.out *.out.h5)", options=options)
            _logger.debug(fileName); _logger.debug(_)
            
            if fileName: self.add_file_history(fileName)
    
    def add_file_history(self, strlist:list[str]):
        # newlist = [s for s in strlist if self.file_history_widget.findText(s) < 0]
        [self.file_history_widget.removeItem(self.file_history_widget.findText(s)) for s in strlist if self.file_history_widget.findText(s) >= 0]
        self.file_history_widget.addItems(strlist)

        self.file_history_widget.setCurrentText(strlist[0])

    h5_file:h5py.File = None
    f_gui:SyncQtApplicationFileReader = None
    def select_history_file(self):
        path = self.file_history_widget.currentText()
        if not path: return
        _logger.debug('select_history_file: {}'.format(path))

        if self.f_gui:
            self.f_gui.close()
        if self.h5_file:
            self.h5_file.close()
        # DEPRECATED: remove the '.out' check
        if path.endswith('.out'):
            if not os.path.isfile(path + '.ipypostgenesis4.out.h5') or os.path.getmtime(path) > os.path.getmtime(path + '.ipypostgenesis4.out.h5'):
                QtCore.QMetaObject.invokeMethod(self.wait_file_dialog.message, "setText", QtCore.Q_ARG(str, "Converting Genesis2 output to Genesis4 format..."))
                os.utime(path, (time.time(), time.time())) # update the timestamp to avoid re-converting

                text_new = convert_genesis2_output_to_genesis4_hdf5(path, path + '.ipypostgenesis4.out.h5')
                QtWidgets.QApplication.processEvents()
            
            path = path + '.ipypostgenesis4.out.h5'
        
        QtCore.QMetaObject.invokeMethod(self.wait_file_dialog.message, "setText", QtCore.Q_ARG(str, "Reading Genesis4 output file..."))
        
        self.f_gui = SyncQtApplicationFileReader(path)
        try:
            self.h5_file = h5py.File(self.f_gui, 'r', locking=False)
        except TypeError as e:
            _logger.error(e)
            self.h5_file = h5py.File(self.f_gui, 'r')

        self.post_builder = IPyPostGenesis4Builder(self.h5_file)

        QtCore.QMetaObject.invokeMethod(self.meta_data_window, "set_meta_data", 
                                        QtCore.Q_ARG("PyQt_PyObject", Genesis4MetaDataWindow.parse_meta_data(self.h5_file)), 
                                        QtCore.Q_ARG(str, path))

        QtCore.QMetaObject.invokeMethod(self, "update_ipypostgenesis4_layout")
    
    @QtCore.pyqtSlot()
    def update_ipypostgenesis4_layout(self):
        if not self._post_widget:
            self._post_widget = IPyPostGenesis4(self.post_builder)
            self.tip_label.hide()
            self.post_layout.addWidget(self._post_widget)
        else:
            self._post_widget = IPyPostGenesis4(self.post_builder)


if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)

    app.setStyle('Fusion')
    app.setStyleSheet("""
        QLabel { color: black; font-size: 20px; } 
        QLineEdit { font-size: 20px; }
        QPushButton { font-size: 20px; }
        QComboBox { font-size: 20px;}
        QCheckBox { font-size: 20px; }
    """)
    win = PostGenesis4MainWindow()
    win.show()

    sys.exit(app.exec())