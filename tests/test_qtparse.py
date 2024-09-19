from copy import deepcopy
from io import BytesIO
from pathlib import Path
from struct import pack

import pytest

from qtparse.atom_parsers import HdlrAtom, StsdSoundAtom, TkhdAtom
from qtparse.extract_metadata import extract_track_size_and_sample_rate
from qtparse.qt_atoms import (get_atoms_by_type, read_atoms, read_classic_atom,
                              read_qt_atom)


def _build_file(atom_tree):
    buf = BytesIO()
    atom_tree = deepcopy(atom_tree)

    def write_atom(buf, atom_tree):
        if atom_tree['is_qt']:
            # qt atom container header
            buf.write(b'\x00' * 12)

            # record position to write size later
            size_pos = buf.tell()

            type_bytes = atom_tree['type'].encode('ascii')
            id = 1 if atom_tree['type'] == 'sean' else 0

            # first 4 bytes reserved for size
            child_count = len(atom_tree['children']) if 'children' in atom_tree else 0

            buf.write(pack('>4x4sI2xH4x', type_bytes, id, child_count))
        else:
            # record position to write size later
            size_pos = buf.tell()

            # first 4 bytes reserved for size
            buf.write(pack('>4x4s', atom_tree['type'].encode('ascii')))

        if 'children' in atom_tree:
            for child in atom_tree['children']:
                write_atom(buf, child)
        if 'payload_size' in atom_tree:
            buf.write(b'\xff' * atom_tree['payload_size'])

        end = buf.tell()
        size = end - size_pos
        buf.seek(size_pos, 0)
        buf.write(size.to_bytes(4, 'big'))
        buf.seek(end, 0)

        # write stats back to atom_tree
        atom_tree['start'] = size_pos
        atom_tree['size'] = size
        atom_tree['end'] = end

    for root_atom in atom_tree:
        write_atom(buf, root_atom)

    size = buf.tell()

    return buf.getvalue()[:size], atom_tree


MIXED_ATOM_TREE = [{
    'type': 'sean',
    'is_qt': True,
    'children': [
        {
            'type': 'moov',
            'is_qt': True,
            'children': [
                {
                    'type': 'trak',
                    'is_qt': True,
                    'children': [
                        {
                            'type': 'mdia',
                            'is_qt': False,
                            'children': [
                                {
                                    'type': 'mdhd',
                                    'is_qt': False,
                                    'payload_size': 24
                                }
                            ]
                        }
                    ]
                },
                {
                    'type': 'trak',
                    'is_qt': False,
                    'children': [
                        {
                            'type': 'mdia',
                            'is_qt': False,
                            'children': [
                                {
                                    'type': 'mdhd',
                                    'is_qt': False,
                                    'payload_size': 24
                                }
                            ]
                        }
                    ]
                },
            ]
        }
    ]
}]

CLASSIC_ATOM_TREE = [{
    'type': 'moov',
    'is_qt': False,
    'children': [
        {
            'type': 'trak',
            'is_qt': False,
            'children': [
                {
                    'type': 'mdia',
                    'is_qt': False,
                    'children': [
                        {
                            'type': 'mdhd',
                            'is_qt': False,
                            'payload_size': 24
                        }
                    ]
                }
            ]
        },
        {
            'type': 'trak',
            'is_qt': False,
            'children': [
                {
                    'type': 'mdia',
                    'is_qt': False,
                    'children': [
                        {
                            'type': 'mdhd',
                            'is_qt': False,
                            'payload_size': 24
                        }
                    ]
                }
            ]
        },
    ]
}]


def test_extract_track_size_and_sample_rate():
    metadata = extract_track_size_and_sample_rate('test_content/sample.mov')

    assert metadata == [{'type': 'vide', 'height': 320.0, 'width': 560.0}, {'type': 'soun', 'sample_rate': 44100}]


def test_read_atoms():
    file_path = Path('test_content/sample.mov')
    file_size = file_path.stat().st_size
    with open(file_path, mode='rb') as f:
        atoms = read_atoms(f, file_size)

    assert len(atoms) == 4
    assert atoms[0].type == 'ftyp'
    assert atoms[1].type == 'wide'
    assert atoms[2].type == 'mdat'
    assert atoms[3].type == 'moov'
    assert atoms[0].size == 24
    assert atoms[1].size == 8
    assert atoms[2].size == 465536
    assert atoms[3].size == 6126


def test_read_classic_atom():
    atom_def = [
        {
            'type': 'mdhd',
            'is_qt': False,
            'payload_size': 24
        }
    ]

    file_bytes, _ = _build_file(atom_def)
    buf = BytesIO(file_bytes)

    atom = read_classic_atom(buf, len(file_bytes), )

    assert atom.type == 'mdhd'
    assert atom.size == 32


def test_read_qt_atom():
    atom_def = [{
        'type': 'sean',
        'is_qt': True,
        'children': [
            {
                'type': 'mdhd',
                'is_qt': True,
                'payload_size': 24
            }
        ]
    }]

    file_bytes, _ = _build_file(atom_def)
    buf = BytesIO(file_bytes)

    buf.read(12)
    atom = read_qt_atom(buf, len(file_bytes))

    assert atom.type == 'sean'
    assert atom.size == 76
    assert atom.children[0].type == 'mdhd'


@pytest.mark.parametrize('atom_tree', [
    MIXED_ATOM_TREE,
    CLASSIC_ATOM_TREE,
])
def test_get_atoms_by_type(atom_tree):
    file_bytes, result = _build_file(atom_tree)
    buf = BytesIO(file_bytes)

    atoms = read_atoms(buf, len(file_bytes))

    trak_atoms = get_atoms_by_type(atoms, ['trak'])

    assert len(trak_atoms) == 2


@pytest.mark.parametrize('atom_tree', [
    MIXED_ATOM_TREE,
    CLASSIC_ATOM_TREE,
])
def test_read_atom_tree(atom_tree):
    file_bytes, result = _build_file(atom_tree)
    buf = BytesIO(file_bytes)

    atoms = read_atoms(buf, len(file_bytes))

    assert len(atoms) == 1

    def validate_atoms(atoms, result):
        for (atom_res, atom_ref) in zip(atoms, result):
            assert atom_res.type == atom_ref['type']
            assert atom_res.size == atom_ref['size']
            if 'children' in atom_ref:
                for child_res, child_ref in zip(atom_res.children, atom_ref['children']):
                    validate_atoms([child_res], [child_ref])

    validate_atoms(atoms, result)


def test_hdlr_atom():
    EXAMPLE_HDLR = [0x0, 0x0, 0x0, 0x0, 0x6d, 0x68, 0x6c, 0x72, 0x76, 0x69, 0x64, 0x65, 0x0, 0x0, 0x0, 0x0, 0x0,
                    0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0xc, 0x56, 0x69, 0x64, 0x65, 0x6f, 0x48, 0x61, 0x6e, 0x64,
                    0x6c, 0x65, 0x72]

    hdlr = HdlrAtom.from_payload_bytes(bytes(EXAMPLE_HDLR))

    assert hdlr.component_type == 'mhlr'
    assert hdlr.component_subtype == 'vide'


def test_stsd_atom():
    EXAMPLE_STSD = [0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0xa7, 0x6d, 0x70, 0x34, 0x61, 0x0,
                    0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0,
                    0x10, 0xff, 0xfe, 0x0, 0x0, 0xac, 0x44, 0x0, 0x0, 0x0, 0x0, 0x4, 0x0, 0x0, 0x0, 0x0, 0x0,
                    0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x2, 0x0, 0x0, 0x0, 0x5b, 0x77, 0x61, 0x76, 0x65, 0x0,
                    0x0, 0x0, 0xc, 0x66, 0x72, 0x6d, 0x61, 0x6d, 0x70, 0x34, 0x61, 0x0, 0x0, 0x0, 0xc, 0x6d,
                    0x70, 0x34, 0x61, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x33, 0x65, 0x73, 0x64, 0x73, 0x0,
                    0x0, 0x0, 0x0, 0x3, 0x80, 0x80, 0x80, 0x22, 0x0, 0x2, 0x0, 0x4, 0x80, 0x80, 0x80, 0x14,
                    0x40, 0x15, 0x0, 0x0, 0x0, 0x0, 0x1, 0xf4, 0x0, 0x0, 0x1, 0x2a, 0xc5, 0x5, 0x80, 0x80,
                    0x80, 0x2, 0x12, 0x8, 0x6, 0x80, 0x80, 0x80, 0x1, 0x2, 0x0, 0x0, 0x0, 0x8, 0x0, 0x0, 0x0,
                    0x0, 0x0, 0x0, 0x0, 0x18, 0x63, 0x68, 0x61, 0x6e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x64, 0x0, 0x1,
                    0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]

    stsd = StsdSoundAtom.from_payload_bytes(bytes(EXAMPLE_STSD))

    assert stsd.sample_desc[0].sample_rate == 44100


def test_tkhd_atom():
    EXAMPLE_TKHD = [0x0, 0x0, 0x0, 0xf, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0,
                    0x0, 0x0, 0x15, 0x9e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0,
                    0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0,
                    0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x40, 0x0, 0x0, 0x0, 0x2, 0x30,
                    0x0, 0x0, 0x1, 0x40, 0x0, 0x0]

    tkhd = TkhdAtom.from_payload_bytes(bytes(EXAMPLE_TKHD))

    assert tkhd.width == 560.0
    assert tkhd.height == 320.0
    assert tkhd.volume == 0.0
