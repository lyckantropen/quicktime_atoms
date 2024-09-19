from copy import deepcopy
from io import BytesIO
from struct import pack

from qtparse.qt_atoms import read_atoms


def test_read_file():
    # with open('test_content/file_example_MOV_480_700kB.mov', mode='rb') as f:
    with open('test_content/Clouds.mov', mode='rb') as f:
        atoms = read_atoms(f)

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


def build_atom_tree(atom_tree):
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
    file_bytes, result = build_atom_tree(MIXED_ATOM_TREE)
    buf = BytesIO(file_bytes)

    atoms = read_atoms(buf)
    
    assert len(atoms) == 1
