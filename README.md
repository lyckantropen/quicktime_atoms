# Telestream homework

Homework for Telestream recruitment

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
pyinstaller --onefile --name qtparse -p path_to_package qtparse/__main__.py
```

The executable will be put in the `dist` subfolder.
