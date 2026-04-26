"""
Converters for Genesis2 output files to Genesis4 HDF5 format.

This module provides functionality to read legacy Genesis2 .out files
and convert them to the HDF5 format used by Genesis4.
"""

import os
import re
import time
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import h5py
from scipy.constants import speed_of_light
from PyQt5 import QtWidgets

from post_genesis4.utils.log_utils import logger


class G4LikeGenesisOutput:
    """
    Storage object for Genesis output *.out files.

    This class holds all data parsed from a Genesis2/4 output file,
    including beam parameters, field data, and lattice information.
    """

    def __init__(self):
        # Lattice data
        self.z: List[float] = []
        self.aw: List[float] = []
        self.qfld: List[float] = []

        # Slice data
        self.s: List[float] = []
        self.I: List[float] = []  # Current
        self.n: List[int] = []    # Slice numbers

        # Field and beam data (dynamically added during parsing)
        self.E: Any = None
        self.sliceKeys: List[str] = []
        self.sliceValues: Dict[str, Any] = {}

        # Metadata
        self.parameters: Dict[str, List[str]] = {}
        self.filePath: str = ''
        self.InputFile: str = ''
        self.SliceData: str = ''

        # Derived properties (set during post-processing)
        self.leng: float = 0.0
        self.ncar: int = 0
        self.nSlices: int = 0
        self.nZ: int = 0
        self.power_z: Optional[np.ndarray] = None
        self.sliceKeys_used: List[str] = []
        self.sn_Imax: int = 0
        self.beam_charge: float = 0.0
        self.pulse_energy: Optional[np.ndarray] = None
        self.scv: Optional[np.ndarray] = None
        self.dt: float = 0.0
        self.t: Optional[np.ndarray] = None

    def fileName(self) -> str:
        """Get the base filename without path."""
        return os.path.basename(self.filePath)

    def __call__(self, name: str) -> Optional[float]:
        """
        Retrieve a parameter value by name.

        Args:
            name: Parameter name to look up.

        Returns:
            Parameter value as float, or None if not found.
        """
        if name not in self.parameters.keys():
            return None
        else:
            p, = self.parameters[name]
            return float(p.replace('D', 'E'))


def _read_genesis2_out(filePath: str) -> G4LikeGenesisOutput:
    """
    Read Genesis output from *.out file.

    Based on ocelot library, modified for conversion to Genesis4 format.

    Args:
        filePath: Path to the Genesis2 .out file.

    Returns:
        G4LikeGenesisOutput object containing all parsed data.

    Raises:
        IOError: If file has zero size.
        ValueError: If file is corrupted or missing required data.
    """
    ind_str = '  '
    out = G4LikeGenesisOutput()
    out.filePath = filePath

    logger.info(f'reading genesis2 {os.path.basename(filePath)} file')
    logger.debug(ind_str + 'reading from ' + filePath)

    chunk = ''
    output_unsorted = []
    nSlice = 0

    if os.path.getsize(out.filePath) == 0:
        logger.error(ind_str + 'file "' + out.filePath + '" has zero size')
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
                logger.log(5, ind_str + 'reading slice # ' + str(nSlice))

            if tokens[0] == 'power':
                out.SliceData = ",".join(line.strip().split())
                chunk = 'slice'
                if len(out.sliceKeys) == 0:  # Record the first instance
                    out.sliceKeys = list(tokens)
                    logger.debug(ind_str + 'reading slice values ')

                output_unsorted.append(np.loadtxt(f, max_rows=int(out('entries_per_record'))))
                continue

            if tokens[0] == '$newrun':
                out.InputFile += line
                chunk = 'input1'
                logger.debug(ind_str + 'reading input parameters')
                continue

            if tokens[0] == '$end':
                out.InputFile += line
                chunk = 'input2'
                continue

            if tokens == ['z[m]', 'aw', 'qfld']:
                chunk = 'magnetic optics'
                logger.debug(ind_str + 'reading magnetic optics ')
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

            if chunk == 'input2':
                tokens = line.replace('=', '').strip().split()
                out.parameters['_'.join(tokens[1:])] = [tokens[0]]

            if chunk == 'slice':
                try:
                    vals = list(map(float, tokens))
                except ValueError:
                    logger.log(5, ind_str + 'wrong E value, fixing')
                    logger.log(5, ind_str + str(tokens))
                    tokens_fixed = re.sub(r'([0-9])\-([0-9])', r'\g<1>E-\g<2>', ' '.join(tokens))
                    tokens_fixed = re.sub(r'([0-9])\+([0-9])', r'\g<1>E+\g<2>', tokens_fixed)
                    tokens_fixed = tokens_fixed.split()
                    logger.log(5, ind_str + str(tokens_fixed))
                    vals = list(map(float, tokens_fixed))

                output_unsorted.append(vals)

            if chunk == 'slices':
                if len(tokens) == 2 and tokens[1] == 'current':
                    out.I.append(float(tokens[0]))
                    out.n.append(nSlice)
                elif len(tokens) == 3 and tokens[1] == 'scan':
                    out.I.append(float(tokens[0]))
                    out.n.append(nSlice)

    # Check for consistency
    if chunk == '':
        logger.error(ind_str + 'File "' + out.filePath + '" has no genesis output information or is corrupted')
        raise ValueError('File "' + out.filePath + '" has no genesis output information or is corrupted')

    for parm in ['z', 'aw', 'qfld', 'I', 'n']:
        setattr(out, parm, np.array(getattr(out, parm)))

    if out('dgrid') == 0:
        rbeam = np.sqrt(out('rxbeam')**2 + out('rybeam')**2)
        ray = np.sqrt(out('zrayl') * out('xlamds') / np.pi * (1 + (out('zwaist') / out('zrayl'))**2))
        out.leng = out('rmax0') * (rbeam + ray)
    else:
        out.leng = 2 * out('dgrid')

    out.ncar = int(out('ncar'))  # Number of mesh points

    # Universal solution
    out.leng = out('meshsize') * (out.ncar - 1)

    out.nSlices = len(out.n)
    if out('entries_per_record') is None:
        logger.error(ind_str + 'In file "' + out.filePath + '" file header is missing')
        raise ValueError('In file "' + out.filePath + '" file header is missing')

    out.nZ = int(out('entries_per_record'))  # Number of records along the undulator
    logger.debug(ind_str + 'nSlices ' + str(out.nSlices))
    logger.debug(ind_str + 'nZ ' + str(out.nZ))

    if nSlice == 0:
        logger.error(ind_str + 'In file "' + out.filePath + '" number of recorded slices is zero')
        raise ValueError('In file "' + out.filePath + '" number of recorded slices is zero')

    n_missing = (out.n[-1] - out.n[0]) - (len(out.n) - 1) * out('ishsty')
    if n_missing != 0:
        logger.error(ind_str + 'File "' + out.filePath + '" is missing at least ' + str(n_missing) + ' slices')
        raise ValueError('File "' + out.filePath + '" is missing at least ' + str(n_missing) + ' slices')

    output_unsorted = np.array(output_unsorted)
    logger.debug('output_unsorted.shape = ' + str(output_unsorted.shape))
    logger.debug(ind_str + 'out.sliceKeys' + str(out.sliceKeys))

    for i in range(len(out.sliceKeys)):
        key = out.sliceKeys[int(i)]
        logger.debug(ind_str + 'key = ' + str(key))
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
            key = 'h{:}_'.format(hn) + key
            logger.debug(2*ind_str + 'key_new = ' + str(key))

        setattr(out, key.replace('-', '_').replace('<', '').replace('>', ''), output_unsorted[:, :, i])

    if hasattr(out, 'energy'):
        out.energy += out('gamma0')

    out.power_z = np.max(out.power, 0)
    out.sliceKeys_used = out.sliceKeys

    if out('itdp') == True:
        out.s = out('zsep') * out('xlamds') * (out.n - out.n[0])
        out.t = out.s / speed_of_light * 1.e+15
        out.dt = (out.t[1] - out.t[0]) * 1.e-15
        out.beam_charge = np.sum(out.I * out.dt)
        out.sn_Imax = np.argmax(out.I)  # Slice number with maximum current
        out.pulse_energy = np.sum(out.power * out.dt, axis=0)
    else:
        out.s = [0]

    if out('iscan') != 0:
        out.scv = out.I  # Scan value
        out.I = np.linspace(1, 1, len(out.scv))  # Because used as a weight

    logger.debug(ind_str + 'done in %.2f seconds' % (time.time() - start_time))
    return out


def convert_genesis2_output_to_genesis4_hdf5(filePath: str, outfilePath: str = None) -> str:
    """
    Convert Genesis2 output file to Genesis4 HDF5 format.

    Args:
        filePath: Path to Genesis2 .out file.
        outfilePath: Optional output path. Defaults to filePath + '.ipypostgenesis4.out.h5'.

    Returns:
        Path to the created HDF5 file.
    """
    g2 = _read_genesis2_out(filePath)
    outfilePath = outfilePath or filePath + '_ipypostgenesis4.out.h5'

    with h5py.File(outfilePath, 'w') as g4:
        # Meta group
        meta_group = g4.create_group('Meta')
        meta_group.create_dataset(
            'AAA',
            data=["Converted from Genesis1.3-Version2 output by post-genesis4"],
            dtype="|S128"
        )
        meta_group.create_dataset(
            'SliceData',
            data=[g2.SliceData],
            dtype="|S" + str(len(g2.SliceData))
        )
        meta_group.create_dataset(
            'InputFile',
            data=[g2.InputFile],
            dtype="|S" + str(len(g2.InputFile))
        )

        # Lattice group
        lattice_group = g4.create_group('Lattice')
        lattice_group.create_dataset('zplot', data=g2.z)
        lattice_group.create_dataset('z', data=g2.z)
        lattice_group.create_dataset('aw', data=g2.aw)
        lattice_group.create_dataset('qf', data=g2.qfld)

        # Global group
        global_group = g4.create_group('Global')
        global_group.create_dataset('s', data=g2.s)
        global_group.create_dataset('lambdaref', data=[g2('xlamds')], dtype='<f8')
        global_group.create_dataset('gamma0', data=[g2('gamma0')], dtype='<f8')
        global_group.create_dataset('one4one', data=[0], dtype='<f8')
        global_group.create_dataset('sample', data=[g2('zsep')], dtype='<f8')
        # TODO: add support for scan, slen, time, frequency in global_group

        # Beam group
        beam_group = g4.create_group('Beam')
        field_group = g4.create_group('Field')

        # Map beam parameters
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

        # Map field parameters
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
