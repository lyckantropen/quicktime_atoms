"""Parse QuickTime files and print height and width of any video tracks as well as sample rate of any audio tracks."""
from argparse import ArgumentParser
from pathlib import Path

from .atom_parsers import HdlrAtom, StsdSoundAtom, TkhdAtom
from .qt_atoms import get_atoms_by_type, read_atoms


def extract_track_size_and_sample_rate(filename: str, strict: bool = False) -> list:
    """
    Extract track size and sample rate from a QuickTime file.

    This method looks for all tracks in the file and determines the size of the
    video tracks by inspecting the `tkhd` atom and the sample rate of the audio
    tracks by inspecting the `stsd` atom.
    """
    file_path = Path(filename)
    file_size = file_path.stat().st_size
    with open(file_path, mode='rb') as f:
        atoms = read_atoms(f, file_size, raise_on_unknown=strict)

    tracks = get_atoms_by_type(atoms, ['trak'])

    metadata = []
    for track in tracks:
        try:
            hdlr_unparsed = get_atoms_by_type(track.children, ['hdlr'])[0]
        except IndexError:
            raise ValueError('No `hdlr` atom found in track')

        hdlr = HdlrAtom.from_payload_bytes(hdlr_unparsed.data)
        if hdlr.component_subtype == 'vide':
            try:
                tkhd_unparsed = get_atoms_by_type(track.children, ['tkhd'])[0]
            except IndexError:
                raise ValueError('No `tkhd` atom found in video track')

            tkhd = TkhdAtom.from_payload_bytes(tkhd_unparsed.data)
            metadata.append({'type': hdlr.component_subtype, 'height': tkhd.height, 'width': tkhd.width})
        elif hdlr.component_subtype == 'soun':
            try:
                stsd_unparsed = get_atoms_by_type(track.children, ['stsd'])[0]
            except IndexError:
                raise ValueError('No `stsd` atom found in audio track')

            stsd = StsdSoundAtom.from_payload_bytes(stsd_unparsed.data)
            metadata.append({'type': hdlr.component_subtype, 'sample_rate': stsd.sample_desc[0].sample_rate})
        else:
            metadata.append({'type': hdlr.component_subtype})

    return metadata


def print_all_atoms_in_file(filename: str, strict: bool = False) -> None:
    """Print all atoms in a QuickTime file."""
    file_path = Path(filename)
    file_size = file_path.stat().st_size
    with open(file_path, mode='rb') as f:
        atoms = read_atoms(f, file_size, raise_on_unknown=strict)

    for atom in atoms:
        print(atom.as_string())


def main():
    """Main entry point for the script."""
    parser = ArgumentParser(description='Parse QuickTime files and print height and width of any video tracks as well as sample rate of any audio tracks.')
    parser.add_argument('filename', help='QuickTime file to parse')
    parser.add_argument('--strict', action='store_true', help='Fail on unknown atom types')
    parser.add_argument('--print-all-atoms', action='store_true', help='Print all atoms in the file')
    args = parser.parse_args()

    print(f'Parsing {args.filename}')

    if args.print_all_atoms:
        print_all_atoms_in_file(args.filename, args.strict)

    try:
        track_info = extract_track_size_and_sample_rate(args.filename, args.strict)
    except BaseException as e:
        print(f'Error parsing file: {e}')
        return

    print(f'There are {len(track_info)} tracks in the file')

    for i, track in enumerate(track_info):
        print(f'{i}: {track}')


if __name__ == '__main__':
    main()
