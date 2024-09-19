"""
Functions for parsing generic QuickTime atoms (without interpreting their payload).

Most function in this module accept a spec parameter that (at the root level) is
a dictionary of expected atom types and their children. The children can be
either a dictionary of children or an AtomReadOp enum value, which determines
whether the atom is merely expected or if it is to be read as well. If the
atom is not in the spec, it is skipped.

This spec is required mainly because of how classic atoms work. They don't have
a header that specifies the number of children, so the parser needs to know
which atoms have children and which don't, and what kinds of children to expect
at which level of the tree. It is also used for QT atoms as an additional check.

Walking of the atom tree is done recursively and as we do so, we descend down
the spec tree as well.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from io import BufferedReader
from struct import unpack
from typing import Dict, List, Optional, Union

ROOT_QT_ATOM = 'sean'


def safe_read(buf: BufferedReader, size: int) -> bytes:
    """Read exactly `size` bytes from the buffer, raise EOFError if not enough data is available."""
    data = buf.read(size)
    if len(data) != size:
        raise EOFError()
    return data


class AtomReadOp(Enum):
    """Enum for specifying how to read an atom."""

    READ = 0  # read entire payload as bytes
    SKIP = 1  # skip payload


# This spec describes all the atoms that are recognized by the parser. Only some
# are read in full, others are skipped. It is not exhaustive. If an atom has no
# children in the spec it doesn't mean it doesn't have any, it means that they
# should be ignored.
DEFAULT_SPEC: Dict[str, Union[Dict, AtomReadOp]] = {
    'ftyp': AtomReadOp.SKIP,
    'moov': {
        'trak': {
            'tkhd': AtomReadOp.READ,
            'mdia': {
                'mdhd': AtomReadOp.SKIP,
                'hdlr': AtomReadOp.READ,
                'minf': {
                    'vmhd': AtomReadOp.SKIP,
                    'dinf': {
                        'dref': AtomReadOp.SKIP,
                    },
                    'stbl': {
                        'stsd': AtomReadOp.READ,
                        'stts': AtomReadOp.SKIP,
                        'stsc': AtomReadOp.SKIP,
                        'stsz': AtomReadOp.SKIP,
                        'stco': AtomReadOp.SKIP,
                    },
                },
            },
        },
        'mvhd': AtomReadOp.SKIP,
        'iods': AtomReadOp.SKIP,
        'udta': AtomReadOp.SKIP,
        'clip': AtomReadOp.SKIP,
        'ctab': AtomReadOp.SKIP,
    },
    'mdat': AtomReadOp.SKIP,
    'free': AtomReadOp.SKIP,
    'skip': AtomReadOp.SKIP,
    'wide': AtomReadOp.SKIP,
    'pnot': AtomReadOp.SKIP,
}


@dataclass
class Atom:
    """Class representing an atom in a QuickTime file."""

    size: int
    type: str
    data: bytes = b''
    id: Optional[int] = None  # only filled in QT atoms
    children: List[Atom] = field(default_factory=list)

    def as_string(self, level: int = 0) -> str:
        """Return a string representation of the atom tree."""
        repr = f'{"  " * level}- {self.type} ({self.size})'
        for child in self.children:
            repr += '\n' + child.as_string(level + 1)
        return repr


def tell_qt_container(buf: BufferedReader) -> bool:
    """Check if the current position in the buffer is the start of a QT atom container."""

    if safe_read(buf, 12) == b'\0\0\0\0\0\0\0\0\0\0\0\0':
        return True
    else:
        buf.seek(-12, 1)
    return False


def read_classic_atom(buf: BufferedReader, file_size: int, parent: Optional[Atom] = None, spec: Optional[Dict] = None, raise_on_unknown: bool = False) -> Atom:
    """
    Read a classic atom from the buffer.

    Parameters
    ----------
    buf : BufferedReader
        The buffer to read from.
    file_size : int
        The size of the file.
    parent : Optional[Atom], optional
        The parent atom, by default None.
    spec : Optional[Dict], optional
        The spec for the atom, if None the default spec is used.
    raise_on_unknown : bool, optional
        Raise an error if an unknown atom is encountered, by default False.

    Returns
    -------
    Atom
        The atom that was read.
    """
    if spec is None:
        spec = DEFAULT_SPEC

    start = buf.tell()
    # read atom size and type
    size, atom_type = unpack('>I4s', safe_read(buf, 8))
    atom_type = atom_type.decode('ascii')

    if size == 0:
        assert parent is None, 'Invalid atom size 0 for non-root atom'
        size = file_size - start
    elif size == 1:
        # read extended size
        size = int.from_bytes(safe_read(buf, 8), 'big')

    payload_offset = buf.tell() - start
    payload_size = size - payload_offset

    if isinstance(spec, Dict):
        if atom_type not in spec:
            # unknown root atom, raise error
            if parent is None and raise_on_unknown:
                raise ValueError(f'Unknown root atom type: {atom_type}')
            # unknown atom type, skip
            buf.seek(payload_size, 1)
            return Atom(size, atom_type)
        else:
            # descend down spec tree
            spec = spec[atom_type]

    if isinstance(spec, Dict):
        # atom with children
        atom = Atom(size, atom_type)
        offset_in_payload = 0
        while offset_in_payload < payload_size:
            child = read_atom(buf, file_size, atom, spec)
            atom.children.append(child)
            offset_in_payload += child.size
        return atom
    elif spec == AtomReadOp.SKIP:
        # atom to skip
        buf.seek(payload_size, 1)
        return Atom(size, atom_type)
    elif spec == AtomReadOp.READ:
        # atom to read
        return Atom(size, atom_type, safe_read(buf, payload_size))
    else:
        raise ValueError(f'Invalid spec value: {spec}')


def read_qt_atom(buf: BufferedReader, file_size: int, parent: Optional[Atom] = None, spec: Optional[Dict] = None, raise_on_unknown: bool = False) -> Atom:
    """
    Read a QT atom from the buffer.

    This does not include the 12 byte QT atom container header, which needs to
    have been read already.

    Parameters
    ----------
    buf : BufferedReader
        The buffer to read from.
    file_size : int
        The size of the file.
    parent : Optional[Atom], optional
        The parent atom, by default None.
    spec : Optional[Dict], optional
        The spec for the atom, if None the default spec is used.
    raise_on_unknown : bool, optional
        Raise an error if an unknown atom is encountered, by default False.

    Returns
    -------
    Atom
        The atom that was read
    """
    if spec is None:
        spec = DEFAULT_SPEC

    start = buf.tell()
    # read atom size and type
    size, atom_type = unpack('>I4s', safe_read(buf, 8))
    atom_type = atom_type.decode('ascii')

    if parent is None:
        assert atom_type == ROOT_QT_ATOM, f'Invalid type for root QT atom: {atom_type}'

    atom = Atom(size, atom_type)

    # read rest of QT atom header
    atom.id, child_count = unpack('>I2xH4x', safe_read(buf, 12))

    payload_offset = buf.tell() - start
    payload_size = size - payload_offset

    if atom_type != ROOT_QT_ATOM and isinstance(spec, Dict):
        if atom_type not in spec:
            # unknown root atom, raise error
            if parent is None and raise_on_unknown:
                raise ValueError(f'Unknown root atom type: {atom_type}')
            # unknown atom type, skip
            buf.seek(payload_size, 1)
            return Atom(size, atom_type)
        else:
            # descend down spec tree
            spec = spec[atom_type]

    for _ in range(child_count):
        child = read_atom(buf, file_size, atom, spec)
        atom.children.append(child)

    if child_count == 0:
        assert isinstance(spec, AtomReadOp), f'Conflicting spec for atom {atom_type}, expected children but child count was 0.'

        if spec == AtomReadOp.SKIP:
            # atom to skip
            buf.seek(payload_size, 1)
        elif spec == AtomReadOp.READ:
            # atom to read
            atom.data = safe_read(buf, payload_size)
        else:
            raise ValueError(f'Invalid spec value: {spec}')

    assert buf.tell() - start == size, f'Invalid atom size: {buf.tell() - start}, expected {size}'

    return atom


def read_atom(buf: BufferedReader, file_size: int, parent: Optional[Atom] = None, spec: Optional[Dict] = None, raise_on_unknown: bool = False) -> Atom:
    """Read an atom from the buffer, classic or QT."""
    if spec is None:
        spec = DEFAULT_SPEC

    if tell_qt_container(buf):
        return read_qt_atom(buf, file_size, parent, spec, raise_on_unknown)
    else:
        return read_classic_atom(buf, file_size, parent, spec, raise_on_unknown)


def read_atoms(buf: BufferedReader, file_size: int, spec: Optional[Dict] = None, raise_on_unknown: bool = False) -> List[Atom]:
    """Read all atoms from the buffer."""
    if spec is None:
        spec = DEFAULT_SPEC

    atoms = []
    while True:
        try:
            atoms.append(read_atom(buf, file_size, None, spec, raise_on_unknown))
        except EOFError:
            break
    return atoms


def get_atoms_by_type(atoms: List[Atom], atom_types: List[str]) -> List[Atom]:
    """Get all atoms from a tree structure with the specified type."""
    result = []
    for atom in atoms:
        if atom.type in atom_types:
            result.append(atom)
        result.extend(get_atoms_by_type(atom.children, atom_types))
    return result
