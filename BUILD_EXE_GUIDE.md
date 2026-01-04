# 🚀 SQUAD Mortar Calculator - EXE Build Guide

## 📦 Tek EXE Oluşturma (All-in-One)

### Adım 1: Gerekli Paketleri Yükle

```bash
pip install pyinstaller opencv-python numpy mss pytesseract pillow pynput
```

### Adım 2: EXE Oluştur

```bash
pyinstaller squad_mortar.spec
```

EXE dosyası şurada oluşur: `dist/SQUAD_Mortar_Calculator.exe`

## 🎯 EXE Nasıl Çalışır?

1. **`SQUAD_Mortar_Calculator.exe`** çift tıkla
2. **Harita Seçim Penceresi** açılır (Tkinter GUI)
3. Harita seç → **START** butonuna tıkla
4. GUI kapanır
5. **Node.js** arka planda başlar (konsol yok ✅)
6. **SmartCordinateMouseOverride.py** overlay ile çalışır

## 📁 EXE ile Birlikte Gereken Dosyalar

EXE dosyası ile aynı klasörde bulunması gerekenler:

```
SQUAD_Mortar_Calculator.exe    ← TEK EXE DOSYASI
SmartCordinateMouseOverride.py  ← Python script
useLegacyMode.js                ← Node.js script
squadFiringSolution.js
squadFiringSolutionOld.js
squadHeightmaps.js
squadWeapons.js
package.json
data/
  ├── maps.js
  └── weapons.js
coordinates.json                 ← Otomatik oluşur
firing_solution.json             ← Otomatik oluşur
```

## ⚙️ Sistem Gereksinimleri (Target PC'de)

1. **Node.js** yüklü olmalı (PATH'te `node` komutu çalışmalı)
2. **Tesseract OCR** yüklü olmalı: `C:\Program Files\Tesseract-OCR\tesseract.exe`

## 🔧 EXE Özellikleri

✅ Tek EXE dosyası
✅ Modern Tkinter GUI ile harita seçimi
✅ Node.js arka planda sessizce çalışır (konsol açılmaz)
✅ Overlay sistem aktif
✅ Manuel mod (Ctrl+Click) destekli
✅ Koordinat lock sistemi

## 📝 Kullanım

```bash
# EXE'yi çalıştır
SQUAD_Mortar_Calculator.exe

# İşte bu kadar! 🎉
```

## 🐛 Sorun Giderme

**Node.js başlamıyorsa:**

- Node.js yüklü mü? → `node --version` test et
- `useLegacyMode.js` aynı klasörde mi?

**Tesseract hatası:**

- Tesseract OCR yüklü mü? → `C:\Program Files\Tesseract-OCR\`

**Import hatası:**

- `SmartCordinateMouseOverride.py` aynı klasörde mi?

## 🎨 Özelleştirme

**Harita seçimini atlamak için:**
GUI'de varsayılan Jensen seçili, direkt START'a basabilirsin.

**Debug mode:**
EXE'yi cmd'den çalıştır: `SQUAD_Mortar_Calculator.exe`
Konsol çıktılarını görebilirsin.

## 📊 Build Süreci

1. PyInstaller tüm Python bağımlılıklarını paketler
2. Tkinter GUI dahil edilir
3. SmartCordinateMouseOverride.py import edilebilir halde eklenir
4. Node.js scripts kopyalanır
5. Data klasörü dahil edilir

## ✨ Test

```bash
cd dist
SQUAD_Mortar_Calculator.exe
```

Harita seç, overlay çıkmalı, Node.js arka planda çalışmalı! 🚀
