"""Parse QuickTime files and print height and width of any video tracks as well as sample rate of any audio tracks."""
from argparse import ArgumentParser
from pathlib import Path

from qtparse.extract_metadata import extract_track_size_and_sample_rate
from qtparse.qt_atoms import read_atoms


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
