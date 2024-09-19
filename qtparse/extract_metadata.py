"""Functions for extracting specific metadata (height, width and sample rate) from QuickTime files."""

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
