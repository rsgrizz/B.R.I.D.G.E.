# B.R.I.D.G.E.

**Byte-level Routing for Image Data Graphical Extension**

A professional, high-performance Windows desktop application designed to convert, compile, verify, and carve digital forensic disk images. The application is built entirely in **Python 3** using the enterprise **PySide6** (Qt for Python) native framework.

---

## Key Features (Architectural Roadmap)
1. **Dynamic Format Detection**: Identifies image structures (magic byte signature matching) for E01, Ex01, DMG, RAW/DD, VMDK, VHD, VHDX, and QCOW2.
2. **Sequential BFS Planning**: Automatically generates optimal multi-step conversion paths using intermediate `.dd` templates when direct toolpaths are unsupported.
3. **Safe Subprocess Runner**: Asynchronously invokes precompiled `qemu-img` and `ewfexport` binaries, showing live console outputs and implementing cancellation locks.
4. **Pre-flight Integrity Checks**: Protects physical partitions via write validations, overwrite warnings, and proactive partition space checkers.
5. **Streamed Checksums**: Pass-through sequential hashing (calculates MD5, SHA-1, and SHA-256 simultaneously in blocks) to guarantee rigid Chain of Custody.
6. **Detailed Audit Logs**: Generates formatted HTML/plain text sessions log suitable for digital forensic expert witness reports.

---

## Directory Layout
```
B.R.I.D.G.E./
├── main.py                    # Application bootstrapper & event loop
├── app/
│   ├── core/                  # Pure Python core services (No Qt)
│   ├── ui/                    # Native PySide6 interface and dialog widgets
│   ├── workers/               # Background threads (QThread / QRunnable)
│   └── utils/                 # Path configurations and logging handlers
├── tools/                     # Precompiled CLI binaries (qemu-img.exe, etc.)
├── tests/                     # Extensible unit test modules
├── requirements.txt           # Main python dependencies
├── run.ps1                    # Boot script for Windows PowerShell
└── build.ps1                  # PyInstaller build stub
```

---

## Setup & Running Instructions (Windows)

### Prerequisites
* **Python 3.10 or newer** (with pip) is required.

### 1. Configure the Virtual Environment
Open PowerShell inside the application directory and run:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 2. Run the Application
Start the application using the PowerShell script:

```powershell
./run.ps1
```

### 3. Run the Automated Tests
Run unit tests to verify system wiring:

```powershell
python -m unittest discover -s tests
```
