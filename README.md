# B.R.I.D.G.E.

**Byte-level Routing for Image Data Graphical Extension**

<p align="center">
  <img src="app/assets/bridge_logo.jpeg" alt="B.R.I.D.G.E. logo" width="420">
</p>

B.R.I.D.G.E. is a professional Windows desktop tool for converting, compiling,
verifying, and carving digital forensic disk images. The application is built in
Python 3 with the native PySide6 (Qt for Python) framework.

---

## Key Features

1. **Dynamic Format Detection**: Identifies image structures using magic byte
   signatures and extensions for E01, Ex01, DMG, RAW/DD, VMDK, VHD, VHDX, and
   QCOW2.
2. **Sequential BFS Planning**: Generates optimal multi-step conversion paths
   using intermediate `.dd` templates when direct toolpaths are unsupported.
3. **Safe Subprocess Runner**: Runs precompiled `qemu-img` and `ewfexport`
   binaries asynchronously with live console output and cancellation handling.
4. **Pre-flight Integrity Checks**: Validates source paths, destinations,
   overwrite intent, and destination disk space before execution.
5. **Streamed Checksums**: Calculates MD5, SHA-1, and SHA-256 in blocks for
   chain-of-custody records.
6. **Detailed Audit Logs**: Writes session logs suitable for forensic workflow
   documentation.

---

## Tool Guide

Use the desktop interface to choose a source forensic or virtual disk image,
select a target output format, choose an output directory, and run the conversion
pipeline. Enable **Dry Run Mode** to validate the planned operation and print
the exact commands without modifying files.

The B.R.I.D.G.E. logo is bundled into the GUI header, About dialog, GitHub guide,
and Windows executable icon through:

```text
app/assets/bridge_logo.jpeg
app/assets/bridge.ico
```

---

## Directory Layout

```text
B.R.I.D.G.E./
|-- main.py                    # Application bootstrapper and event loop
|-- app/
|   |-- assets/                # Logo and icon assets
|   |-- core/                  # Pure Python core services
|   |-- ui/                    # Native PySide6 interface and dialogs
|   |-- workers/               # Background threads
|   `-- utils/                 # Path configuration and logging
|-- tools/                     # Precompiled CLI binaries
|-- tests/                     # Unit and integration tests
|-- requirements.txt           # Python dependencies
|-- run.ps1                    # Windows PowerShell launch script
|-- build.ps1                  # PyInstaller packaging script
`-- BRIDGE.spec                # PyInstaller packaging specification
```

---

## Setup And Running Instructions

### Prerequisites

* Python 3.10 or newer with pip.
* Windows PowerShell.

### 1. Configure The Virtual Environment

Open PowerShell inside the application directory and run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run The Application

```powershell
.\run.ps1
```

### 3. Run The Automated Tests

```powershell
python -m unittest discover -s tests
```

---

## Standalone Packaging

B.R.I.D.G.E. supports native standalone packaging on Windows using PyInstaller in
one-directory mode. The package bundles source modules, PySide6 resources,
branding assets, and external forensic tool dependencies without requiring a
Python interpreter on the host system.

### Packaging Prerequisites

* PySide6 and PyInstaller installed in the active environment.
* Precompiled external tool binaries, such as `qemu-img.exe` and `ewfexport.exe`,
  placed in the local `tools/` directory.

### Build Command

Run the build automation script inside PowerShell:

```powershell
.\build.ps1
```

The script will:

1. Clean prior build and distribution artifacts.
2. Execute the automated test suite.
3. Abort packaging if tests fail.
4. Package the application using `BRIDGE.spec`.
5. Copy external tools and branding assets into the packaged folder.

### Package Distribution Output

```text
dist/BRIDGE/
|-- BRIDGE.exe                # Standalone windowed GUI executable
|-- _internal/                # Packaged system libraries and dependencies
|-- app/assets/               # Logo and icon assets
|-- tools/                    # Bundled external command-line utilities
`-- logs/                     # Runtime log directory
```

Runtime logs are written to:

```text
dist/BRIDGE/logs/bridge.log
```

### Run The Packaged Application

```powershell
.\dist\BRIDGE\BRIDGE.exe
```

### Windows Packaging Troubleshooting

* **Obsolete `pathlib` Package Hook Conflict**: PyInstaller can crash if the
  obsolete third-party PyPI backport of `pathlib` is installed. Resolve it with:

  ```powershell
  python -m pip uninstall -y pathlib
  ```

* **Virtual Environment Recognition**: If you use a custom virtual environment,
  activate it before calling `.\build.ps1`.

* **Missing DLL Errors**: If `BRIDGE.exe` fails with missing Qt or PySide6 DLLs,
  clear the build cache and reinstall PySide6:

  ```powershell
  python -m pip install --force-reinstall PySide6
  .\build.ps1
  ```
