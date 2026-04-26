"""Brief lattice plot widget for displaying undulator lattice."""

from typing import Optional

import numpy as np
import matplotlib.pyplot as plt

import post_genesis4.gui as gui


class BriefLatticePlotUnit:
    """
    Widget for displaying a brief overview of the undulator lattice.

    Shows aw (undulator parameter) and qf (quadrupole focusing) values
    along the z-axis with a vertical line indicating current slice position.

    Attributes:
        ipypost4: Reference to main application instance.
        ax: Matplotlib axes for aw plotting.
        ax_twin: Twin axes for qf plotting.
        z_line: Vertical line indicating current slice position.
        z: Z-axis coordinates.
        aw: Undulator parameter values.
        qf: Quadrupole focusing values.
    """

    def __init__(self, ipypost4: "gui.IPyPostGenesis4", ax: plt.Axes):
        """
        Initialize lattice plot unit.

        Args:
            ipypost4: Main application instance.
            ax: Matplotlib axes for primary plotting.
        """
        self.ipypost4 = ipypost4
        self.ax = ax
        self.ax_twin = self.ax.twinx()
        self.ax.axis('off')
        self.ax_twin.axis('off')
        self.ax.set_navigate(False)
        self.ax_twin.set_navigate(False)

        self.z_line: Optional[plt.Line2D] = None
        self.z: Optional[np.ndarray] = None
        self.aw: Optional[np.ndarray] = None
        self.qf: Optional[np.ndarray] = None

    def preprocess_data(self):
        """Load and preprocess lattice data from HDF5 file."""
        self.z = self.ipypost4.h5_file['/Lattice/z'][()]
        aw = self.ipypost4.h5_file['/Lattice/aw'][()]
        qf = self.ipypost4.h5_file['/Lattice/qf'][()]

        self.ax.set_ylim(-np.max(np.abs(aw))*1.3, np.max(np.abs(aw))*1.3)
        self.ax_twin.set_ylim(-np.max(np.abs(qf))*1.05, np.max(np.abs(qf))*1.05)

        if np.max(np.abs(qf)) == 0:
            self.ax_twin.set_ylim(-1, 1)

        # Replace zeros with None for proper plotting
        aw[aw == 0] = None
        qf[qf == 0] = None

        self.aw = aw
        self.qf = qf

    def plot_z_line(self):
        """Plot or update vertical line at current slice position."""
        if self.z_line:
            self.z_line.set_xdata([self.ipypost4.slice_control.slice_value] * 2)
        elif self.ipypost4.slice_control.plot_axis_x == 's':
            self.z_line = self.ax_twin.axvline(
                self.ipypost4.slice_control.slice_value,
                self.ax_twin.get_ylim()[0], self.ax_twin.get_ylim()[1],
                linewidth=1.0, linestyle='--', color='red'
            )

    def update_plot(self):
        """Update plot with current slice position."""
        self.plot_z_line()

    def plot_new(self):
        """Create new lattice plot."""
        self.ax.clear()
        self.ax_twin.clear()
        # Clear automatically removes the z_line
        self.z_line = None

        self.preprocess_data()

        # Plot multiple transparency levels for visual effect
        for f in np.linspace(0.01, 1.01, 20):
            self.ax.plot(self.z, self.aw*f, linewidth=0.6, color='orange', drawstyle='steps-post')
            self.ax_twin.plot(self.z, self.qf*f, linewidth=0.6, color='b', drawstyle='steps-post')

        self.ax.axis('off')
        self.ax_twin.axis('off')

        self.plot_z_line()
