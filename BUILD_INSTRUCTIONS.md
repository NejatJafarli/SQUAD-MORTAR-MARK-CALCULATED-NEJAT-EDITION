# SQUAD Mortar Calculator - Build Instructions

## 📋 Prerequisites

Before building the EXE, make sure you have:

1. **Python 3.8+** installed
2. **Node.js** installed
3. **Tesseract OCR** installed at: `C:\Program Files\Tesseract-OCR\`
4. All Python dependencies installed

## 🔧 Install Dependencies

```bash
# Install Python packages
pip install opencv-python numpy mss pytesseract pillow pynput pyinstaller

# Verify Node.js is installed
node --version

# Install Node.js dependencies
npm install
```

## 🏗️ Building the EXE

### Method 1: Using PyInstaller directly (Simple)

```bash
pyinstaller --onefile --console --name "SQUAD_Mortar_Calculator" start_system.py
```

This creates: `dist/SQUAD_Mortar_Calculator.exe`

### Method 2: Using the spec file (Recommended - includes all files)

```bash
pyinstaller squad_mortar.spec
```

This creates: `dist/SQUAD_Mortar_Calculator.exe` with all necessary files bundled

## ⚠️ Important Notes

1. **Tesseract OCR** must be installed on the target PC at:
   - `C:\Program Files\Tesseract-OCR\tesseract.exe`
2. **Node.js** must be installed on the target PC (the EXE calls `node` command)

3. The EXE needs these files in the same directory:
   - `SmartCordinateMouseOverride.py`
   - `useLegacyMode.js`
   - `data/` folder (with maps.js and weapons.js)
   - All squad\*.js files

## 🚀 Running the EXE

1. Double-click `SQUAD_Mortar_Calculator.exe`
2. Select your map from the list (1-27 or type name)
3. Two windows will open:
   - Python coordinate reader
   - Node.js mortar calculator

## 📦 Distribution Package

For distribution, include:

```
SQUAD_Mortar_Calculator.exe
SmartCordinateMouseOverride.py
useLegacyMode.js
squadFiringSolution.js
squadFiringSolutionOld.js
squadHeightmaps.js
squadWeapons.js
data/
  ├── maps.js
  └── weapons.js
```

## 🧪 Testing

After building, test the EXE:

```bash
cd dist
SQUAD_Mortar_Calculator.exe
```

Select a map and verify both systems start correctly.

## 🛠️ Alternative: Portable Version (Recommended)

Instead of a single EXE, create a portable folder:

1. Copy all files to a new folder
2. Use the batch file: `start_mortar_system.bat`
3. No build needed - just distribute the folder!

This is easier because:

- No EXE compilation needed
- Easier to update
- No bundling issues
- Works immediately
