# QuickTime Atoms

Homework I did for a recruitment.

The entry point for the script is `qtparse/__main__.py`.

Breakdown of files:

- `qtparse/qt_atoms.py` - functions for extracting the tree of atoms from a
  file, the user would most likely use `read_atoms` to read all atoms;
- `qtparse/atom_parsers.py` - dataclasses for interpreting the payloads of
  several specific atoms needed for completing the task;
- `qtparse/extract_metadata.py` - contains the logic that uses the above two
  files to extract the relevant atoms and infer the size of the video and the
  sample rate of the audio track;

## Running

At least Python 3.7 is required.

```bash
python3 -m qtparse test_content/Clouds.mov
```

### Additional features

This will print all atoms recognized by the tool:

```bash
python3 -m qtparse test_content/Clouds.mov --print-all-atoms
```

### Building a single bundled executable

```bash
pip install pyinstaller
pyinstaller --onefile --name qtparse qtparse/__main__.py
```

The executable will be put in the `dist` subfolder.
