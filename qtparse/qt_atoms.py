from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from io import BufferedReader
from struct import unpack
from typing import Dict, List, Optional, Union

ROOT_QT_ATOM = 'sean'


class AtomReadOp(Enum):
    """Enum for specifying how to read an atom."""

    READ = 0
    SKIP = 1


def safe_read(buf: BufferedReader, size: int) -> bytes:
    """Read exactly `size` bytes from the buffer, raise EOFError if not enough data is available."""
    data = buf.read(size)
    if len(data) != size:
        raise EOFError()
    return data


# if an atom has no children in the spec it doesn't mean it doesn't have any, it
# means that they should be ignored
DEFAULT_SPEC: Dict[str, Union[Dict, AtomReadOp]] = {
    'ftyp': AtomReadOp.SKIP,
    'moov': {
        'trak': {
            'tkhd': AtomReadOp.READ,
            'mdia': {
                'mdhd': AtomReadOp.SKIP,
                'hdlr': AtomReadOp.SKIP,
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
    'wide': AtomReadOp.SKIP
}


@dataclass
class Atom:
    """Class representing an atom in a QuickTime file."""

    size: int
    type: str
    data: bytes = b''
    id: Optional[int] = None
    children: List[Atom] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.size, self.type, self.data, self.id, tuple(self.children))


def tell_qt_container(buf: BufferedReader) -> bool:
    """Check if the current position in the buffer is the start of a QuickTime container."""

    if safe_read(buf, 12) == b'\0\0\0\0\0\0\0\0\0\0\0\0':
        return True
    else:
        buf.seek(-12, 1)
    return False


def read_classic_atom(buf: BufferedReader, parent: Optional[Atom] = None, spec: Optional[Dict] = None) -> Atom:
    """Read an atom from the buffer."""
    start = buf.tell()
    size, atom_type = unpack('>I4s', safe_read(buf, 8))
    atom_type = atom_type.decode('ascii')

    if size == 0:
        assert parent is None, 'Invalid atom size 0 for non-root atom'
        # TODO: process root atom (to the end of file)

    elif size == 1:
        # read extended size
        size = int.from_bytes(safe_read(buf, 8), 'big')

    payload_offset = buf.tell() - start
    payload_size = size - payload_offset

    if isinstance(spec, Dict):
        if atom_type not in spec:
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
            child = read_atom(buf, atom, spec)
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


def read_qt_atom(buf: BufferedReader, parent: Optional[Atom] = None, spec: Optional[Dict] = None) -> Atom:
    """Read an atom from the buffer."""
    start = buf.tell()
    size, atom_type = unpack('>I4s', safe_read(buf, 8))
    atom_type = atom_type.decode('ascii')

    if parent is None:
        assert atom_type == ROOT_QT_ATOM, f'Invalid type for root QT atom: {atom_type}'

    atom = Atom(size, atom_type)
    atom.id, child_count = unpack('>I2xH4x', safe_read(buf, 12))

    payload_offset = buf.tell() - start
    payload_size = size - payload_offset

    if atom_type != ROOT_QT_ATOM and isinstance(spec, Dict):
        if atom_type not in spec:
            # unknown atom type, skip
            buf.seek(payload_size, 1)
            return Atom(size, atom_type)
        else:
            # descend down spec tree
            spec = spec[atom_type]

    for _ in range(child_count):
        child = read_atom(buf, atom, spec)
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


def read_atom(buf: BufferedReader, parent: Optional[Atom] = None, spec: Optional[Dict] = None) -> Atom:
    """Read an atom from the buffer."""
    if tell_qt_container(buf):
        return read_qt_atom(buf, parent, spec)
    else:
        return read_classic_atom(buf, parent, spec)


def read_atoms(buf: BufferedReader, spec=None) -> List[Atom]:
    """Read all atoms from the buffer."""
    if spec is None:
        spec = DEFAULT_SPEC
    atoms = []
    while True:
        try:
            atoms.append(read_atom(buf, None, spec=spec))
        except EOFError:
            break
    return atoms
