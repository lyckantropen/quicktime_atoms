from copy import deepcopy
from io import BytesIO
from pathlib import Path
from struct import pack

from qtparse.atom_parsers import HdlrAtom, StsdSoundAtom, TkhdAtom
from qtparse.qt_atoms import get_atoms_by_type, read_atoms
from qtparse.extract_metadata import extract_track_size_and_sample_rate


def test_extract_track_size_and_sample_rate():
    metadata = extract_track_size_and_sample_rate('test_content/sample.mov')

    assert metadata == [{'type': 'vide', 'height': 320.0, 'width': 560.0}, {'type': 'soun', 'sample_rate': 44100}]


def test_read_file():
    file_path = Path('test_content/sample.mov')
    file_size = file_path.stat().st_size
    with open(file_path, mode='rb') as f:
        atoms = read_atoms(f, file_size)

    tracks = get_atoms_by_type(atoms, ['trak'])

    for atom in tracks:
        hdlr_unparsed = get_atoms_by_type(atom.children, ['hdlr'])[0]
        hdlr = HdlrAtom.from_payload_bytes(hdlr_unparsed.data)
        if hdlr.component_subtype == 'vide':
            tkhd_unparsed = get_atoms_by_type(atom.children, ['tkhd'])[0]
            tkhd = TkhdAtom.from_payload_bytes(tkhd_unparsed.data)
            print(tkhd)
        elif hdlr.component_subtype == 'soun':
            stsd_unparsed = get_atoms_by_type(atom.children, ['stsd'])[0]
            stsd = StsdSoundAtom.from_payload_bytes(stsd_unparsed.data)
            print(stsd)

    assert len(atoms) == 1


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
                                    'payload_size': 32
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
                                    'payload_size': 32
                                }
                            ]
                        }
                    ]
                },
            ]
        }
    ]
}]


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


def test_read_mixed_qt_file():
    file_bytes, result = _build_file(MIXED_ATOM_TREE)
    buf = BytesIO(file_bytes)

    atoms = read_atoms(buf, len(file_bytes))

    assert len(atoms) == 1
