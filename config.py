"""
SQUAD Mortar Calculator - Central Configuration
Tüm ayarlar bu dosyadan kontrol edilir
"""

# ==========================================
# DEBUG & GENERAL SETTINGS
# ==========================================
DEBUG_MODE = True  # True=Debug mesajları göster, False=Gizle

# ==========================================
# MAP SETTINGS
# ==========================================
MAPS = [
    "AlBasrah", "Anvil", "Belaya", "BlackCoast", "Chora", "Fallujah",
    "FoolsRoad", "GooseBay", "Gorodok", "Jensen", "Harju", "Kamdesh",
    "Kohat", "Kokan", "Lashkar", "Logar", "Manicouagan", "Mestia",
    "Mutaha", "Narva", "Narva_f", "Pacific", "Sanxian", "Skorpo",
    "Sumari", "Tallil", "Yehorivka"
]

# ==========================================
# TESSERACT OCR SETTINGS
# ==========================================
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ==========================================
# COORDINATE DETECTION SETTINGS
# ==========================================
# 1 = AUTO MODE (Shape detection)
# 2 = MANUAL MODE (Ctrl+Click to mark positions)
DETECTION_MODE = 2

# OCR region (top-left text area)
OCR_LEFT = 720
OCR_TOP = 30
OCR_WIDTH = 550
OCR_HEIGHT = 55

# Map capture region
SCENE_LEFT = 700
SCENE_TOP = 120
SCENE_WIDTH = 1800
SCENE_HEIGHT = 1300

# Grid configuration
GRID_100M_SIZE = 310  # 100m grid size in pixels
GRID_33M_SIZE = 103   # 33m sub-grid size (310/3 ≈ 103)

# Colors to detect (for AUTO mode)
PLAYER_COLOR_RGB = (217, 217, 0)    # Yellow player icon
PLAYER_TOLERANCE = 30
MARKER_COLOR_RGB = (73, 182, 23)    # Green marker
MARKER_TOLERANCE = 50

# Update interval (seconds)
UPDATE_INTERVAL = 1.0

# Output files
OUTPUT_FILE = "coordinates.json"
FIRING_SOLUTION_FILE = "firing_solution.json"

# ==========================================
# CORDINATES READER (POZISYON Okuyucu)
# ==========================================
# 910, 40, 110, 40
PLAYER_CORDINATES = [910, 40, 110, 40]  # left, top, width, height

# MARKER CORDINATES (İŞARETLEYİCİ Koordinatları)
MARKER_CORDINATES = [1165, 40, 110, 40]  # left, top, width, height


# BM21GRAD Degree Reader (İŞARETLEYİCİ Koordinatları)
BM21GRAD_DEGREES = [1250, 1280, 50, 25]  # left, top, width, height

BM21GRAD_BEARING = [1260, 1395, 40, 30]  # left, top, width, height

# ==========================================
# BEARING READER SETTINGS (Derece Okuyucu)
# ==========================================
BEARING_LEFT = 1245
BEARING_TOP = 1395
BEARING_WIDTH = 65
BEARING_HEIGHT = 35

# ==========================================
# RADIAN READER SETTINGS (Cetvel Okuyucu)
# ==========================================
RADIAN_LEFT = 650
RADIAN_TOP = 190
RADIAN_WIDTH = 300
RADIAN_HEIGHT = 1050

# ==========================================
# AUTO TARGETING SETTINGS (Makro Ayarları)
# ==========================================
MORTAR_MACRO_Y_PATH = r"C:\Users\NejatJafarli\Desktop\SQUAD MORTAR MARK CALCULATED NEJAT EDITION\MORTAR_MacroY_For_2K.xml"
MORTAR_MACRO_X_PATH = r"C:\Users\NejatJafarli\Desktop\SQUAD MORTAR MARK CALCULATED NEJAT EDITION\MORTAR_MacroX_For_2K.xml"

UKRANIA_BM21GRAD_MACRO_Y_PATH = r"C:\Users\NejatJafarli\Desktop\SQUAD MORTAR MARK CALCULATED NEJAT EDITION\UKRANIA_Bm21_MacroY_For_2K.xml"
UKRANIA_BM21GRAD_MACRO_X_PATH = r"C:\Users\NejatJafarli\Desktop\SQUAD MORTAR MARK CALCULATED NEJAT EDITION\UKRANIA_Bm21_MacroX_For_2K.xml"


DPI_SCALE = 1.25  # Mouse DPI ölçeklendirme faktörü

# In-game mouse sensitivity setting
# Bu değer oyun içi sensitivity ayarı ile eşleşmelidir!
# Sensitivity yüksekse (örn: 2.0) -> Mouse hareketi azaltılır
# Sensitivity düşükse (örn: 0.5) -> Mouse hareketi artırılır
SENSITIVITY = 1.00  # Oyun içi sensitivity (varsayılan: 1.00)

# ==========================================
# GAME RESOLUTION SETTINGS
# ==========================================
GAME_RESOLUTION = "1920x1080"  # Oyun çözünürlüğü (örn: 1920x1080, 2560x1440)

# ==========================================
# WEAPON SETTINGS
# ==========================================
AVAILABLE_WEAPONS = [
    "Mortar",
    "UB-32",
    "HellCannon",
    "Tech.Mortar",
    "Tech.UB-32",
    "BM-21Grad-UKRANIA",
    "M1064M121",
    "Mk19",
    "BTR4-AGS",
    "M109",
    "M777",
    "T62.DUMP.TRUCK",
    "HIMARS",
    "TOS-1A",
    "MTLB_FAB500"
]
DEFAULT_WEAPON = "Mortar"  # Varsayılan silah

# ==========================================
# PLAYER STARTING COORDINATES
# ==========================================
PLAYER_Y_START = 800.0  # Elevation başlangıç değeri
PLAYER_X_START = 0.0    # Bearing başlangıç değeri (derece)
PLAYER_Y_DEGREE_START = 13.9    # Bearing başlangıç değeri (derece)
