import ctypes
import time
from turtle import degrees
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pynput import keyboard
from RadianReader import RulerReader
from BearingReader import BearingReader
from BM21DegreeReader import DegreeReader
import config

# DirectInput için Windows API fonksiyonları
user32 = ctypes.windll.user32
SendInput = user32.SendInput
globalMortarMacroPathY = config.MORTAR_MACRO_Y_PATH
globalMortarMacroPathX = config.MORTAR_MACRO_X_PATH

selectedWeapon=None
Processing=False


globalUKRANIABM21MacroPathY = config.UKRANIA_BM21GRAD_MACRO_Y_PATH
globalUKRANIABM21MacroPathX = config.UKRANIA_BM21GRAD_MACRO_X_PATH
# myOwnPrint fonksiyonunu start_system'den import et
try:
    from start_system import myOwnPrint, DEBUG_MODE
except ImportError:
    # Standalone modda çalışıyorsa fallback
    DEBUG_MODE = False
    def myOwnPrint(message):
        if DEBUG_MODE:
            print(message)

# Input yapıları
PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Mouse event flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

class RazerMacroPlayer:
    def __init__(self, xml_file_path, dpi_scale=1.0, sensitivity=1.0, Controller=None, reader=None):
        """
        XML dosyasından makroyu yükler
        
        Args:
            xml_file_path: Razer Synapse XML dosyasının yolu
            dpi_scale: DPI ölçeklendirme faktörü (örn: 0.8, 1.0, 1.25)
            sensitivity: Oyun içi mouse sensitivity (örn: 0.5, 1.0, 2.0)
            ruler_reader: RulerReader instance (OCR kalibrasyon için)
        """
        self.movements = []
        self.dpi_scale = dpi_scale
        self.sensitivity = sensitivity
        self.current_coordinate = float(800)  # Başlangıç koordinatı
        self.abort = False  # İşlemleri durdurmak için bayrak
        self.reader = reader  # OCR reader
        self.play_coordinate_call_count = 0  # Çağrı sayacı
        self.load_from_xml(xml_file_path)
        
        self.PlayerY=False
        self.PlayerX=False

        if Controller == "X":
            self.PlayerX=True
        elif Controller == "Y":
            self.PlayerY=True
        
        # BM-21 Grad için kalibrasyon tablosu (doğrusal olmayan davranışı telafi eder)
        self.bm21_calibration = self._build_bm21_calibration_table()
        
    def _build_bm21_calibration_table(self):
        """
        BM-21 Grad için kalibrasyon tablosu oluşturur.
        Yükseldikçe artan kayma oranlarını telafi eder.
        
        Gözlemlenen kayma (referans nokta: 14°):
        - Yaklaşık her 10 derece için +1° kayma artışı
        - Bu pattern 5°-100° aralığında geçerli
        
        Düzeltme faktörü formülü:
        correction = 1.0 + ((degree - 14) / 100)
        
        Örnekler:
        - 5-14°: 1.0x (referans)
        - 24°: ~1.10x
        - 34°: ~1.20x
        - 44°: ~1.30x
        - 54°: ~1.40x
        - 100°: ~1.86x
        """
        calibration = {}
        
        # 5°-100° arası için dinamik kalibrasyon
        for deg in range(5, 101):
            if deg <= 14:
                # 5-14 arası referans bölge (kayma yok)
                calibration[deg] = 1.0
            else:
                # 14'ten sonra her derece için artış
                # Her 10 derece ~0.10 artış (lineer yaklaşım)
                base_correction = 1.0
                degrees_above_ref = deg - 14
                correction_increase = degrees_above_ref * 0.001  # Her derece için %0.5 artış
                calibration[deg] = base_correction + correction_increase
        
        return calibration
    
    def _get_bm21_correction_factor(self, start_coord, target_coord):
        """
        BM-21 Grad için düzeltme faktörünü hesaplar.
        Başlangıç ve hedef koordinat arasındaki ortalama düzeltme faktörünü döndürür.
        """
        global selectedWeapon
        
        # Sadece BM-21 Grad Y ekseni için kalibrasyon uygula
        if selectedWeapon != "BM-21Grad-UKRANIA" or not self.PlayerY:
            return 1.0
        
        # Aralıktaki tüm derecelerin düzeltme faktörlerini topla
        start = int(start_coord)
        end = int(target_coord)
        
        if start == end:
            return self.bm21_calibration.get(start, 1.0)
        
        # Aralıktaki ortalama düzeltme faktörü
        total_correction = 0
        count = 0
        
        for deg in range(min(start, end), max(start, end) + 1):
            total_correction += self.bm21_calibration.get(deg, 1.0)
            count += 1
        
        avg_correction = total_correction / count if count > 0 else 1.0
        
        myOwnPrint(f"🔧 BM-21 Düzeltme: {start}°→{end}° için faktör: {avg_correction:.3f}")
        
        return avg_correction
    
    def load_from_xml(self, xml_file_path):
        """XML dosyasından fare hareketlerini parse eder"""
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            # Tüm Buffer elementlerini bul
            buffers = root.findall('.//Buffer')
            
            for buffer in buffers:
                x_elem = buffer.find('x')
                y_elem = buffer.find('y')
                time_elem = buffer.find('time')
                
                if x_elem is not None and y_elem is not None and time_elem is not None:
                    x = int(x_elem.text)
                    y = int(y_elem.text)
                    delay = float(time_elem.text) / 1000.0  # milisaniyeyi saniyeye çevir
                    
                    self.movements.append((x, y, delay))
            
            myOwnPrint(f"✓ {len(self.movements)} hareket yüklendi")
            self.analyze_macro()
            
        except Exception as e:
            myOwnPrint(f"✗ XML yükleme hatası: {e}")
            raise
    
    def analyze_macro(self):
        """Makroyu analiz eder ve istatistikler gösterir"""
        if not self.movements:
            return
        
        # Toplam hareket mesafesi
        total_dx = 0
        total_dy = 0
        total_time = 0
        
        prev_x, prev_y = self.movements[0][0], self.movements[0][1]
        
        for x, y, delay in self.movements[1:]:
            dx = x - prev_x
            dy = y - prev_y
            total_dx += abs(dx)
            total_dy += abs(dy)
            total_time += delay
            prev_x, prev_y = x, y
        
        myOwnPrint(f"\n📊 MAKRO ANALİZİ:")
        myOwnPrint(f"   • Toplam Hareket: X={total_dx}px, Y={total_dy}px")
        myOwnPrint(f"   • Toplam Süre: {total_time:.2f} saniye")
        myOwnPrint(f"   • Ortalama Delay: {(total_time / len(self.movements)):.4f} saniye")
        myOwnPrint(f"   • Y Hareketi (0-100): {total_dy}px\n")
        
        # Adım başına hareket miktarını hesapla
        self.step_movement = total_dy / 100  # 100 birim için gereken piksel
        myOwnPrint(f"💡 1 birim = {self.step_movement:.2f} piksel hareket\n")
    
    def move_mouse_absolute(self, x, y):
        """
        Fareyi belirtilen koordinata DirectInput ile taşır
        
        Args:
            x, y: Ekran koordinatları
        """
        # Ekran boyutlarını al
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Koordinatları 0-65535 aralığına normalize et (DirectInput için)
        normalized_x = int(x * 65535 / screen_width)
        normalized_y = int(y * 65535 / screen_height)
        
        # Mouse input oluştur
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(normalized_x, normalized_y, 0, 
                           MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 
                           ctypes.pointer(extra))
        
        x_input = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
        SendInput(1, ctypes.pointer(x_input), ctypes.sizeof(x_input))
    
    def move_mouse_relative(self, dx, dy):
        """
        Fareyi göreceli olarak hareket ettirir
        
        Args:
            dx, dy: Piksel cinsinden hareket miktarı
        """
        # DPI ölçeklendirmesi ve sensitivity kompensasyonu uygula
        # Sensitivity yüksekse (2.0) -> Daha az hareket gerekir (bölünerek azaltılır)
        # Sensitivity düşükse (0.5) -> Daha fazla hareket gerekir (bölünerek artırılır)
        effective_scale = self.dpi_scale / self.sensitivity
        dx = int(dx * effective_scale)
        dy = int(dy * effective_scale)
        
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(dx, dy, 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
        
        x_input = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
        SendInput(1, ctypes.pointer(x_input), ctypes.sizeof(x_input))
    
    def set_abort(self, value):
        """Abort bayrağını ayarlar."""
        self.abort = value
    
    def play_macro(self, use_absolute=False, smooth=True):
        """
        Makroyu oynatır
        
        Args:
            use_absolute: True ise mutlak koordinatlar, False ise göreceli hareket (ÖNERİLEN: False)
            smooth: True ise her hareketi ayrı ayrı gönderir
        """
        if not self.movements:
            myOwnPrint("✗ Hareket verisi yok!")
            return
        
        myOwnPrint(f"▶ Makro başlıyor... ({len(self.movements)} hareket)")
        myOwnPrint(f"   Mod: {'Mutlak Koordinat' if use_absolute else 'Göreceli Hareket'}")
        myOwnPrint(f"   DPI Ölçek: {self.dpi_scale}")
        myOwnPrint(f"   Sensitivity: {self.sensitivity}")
        myOwnPrint(f"   Efektif Ölçek: {self.dpi_scale / self.sensitivity:.3f}")
        myOwnPrint("   İptal etmek için Ctrl+C veya abort bayrağını ayarlayın")
        
        try:
            if use_absolute:
                # MUTLAK KOORDİNAT MODU (Eski)
                for i, (x, y, delay) in enumerate(self.movements):
                    if self.abort:
                        myOwnPrint("✗ Makro durduruldu (abort bayrağı ayarlandı)")
                        return
                    if i > 0:
                        time.sleep(delay)
                    self.move_mouse_absolute(x, y)
                    
                    if (i + 1) % 100 == 0:
                        myOwnPrint(f"  {i + 1}/{len(self.movements)} tamamlandı...")
            else:
                # GÖRECELİ HAREKET MODU (Önerilen - Razer ile aynı)
                prev_x, prev_y = self.movements[0][0], self.movements[0][1]
                
                for i, (x, y, delay) in enumerate(self.movements):
                    if self.abort:
                        myOwnPrint("✗ Makro durduruldu (abort bayrağı ayarlandı)")
                        return
                    if i > 0:
                        time.sleep(delay)
                        
                        # Göreceli hareket hesapla
                        dx = x - prev_x
                        dy = y - prev_y
                        
                        if dx != 0 or dy != 0:
                            self.move_mouse_relative(dx, dy)
                        
                        prev_x, prev_y = x, y
                    
                    if (i + 1) % 100 == 0:
                        myOwnPrint(f"  {i + 1}/{len(self.movements)} tamamlandı...")
            
            myOwnPrint("✓ Makro tamamlandı!")
            
        except KeyboardInterrupt:
            myOwnPrint("\n✗ Makro kullanıcı tarafından durduruldu")
        except Exception as e:
            myOwnPrint(f"\n✗ Hata: {e}")
    
    def calculate_steps_needed(self, target_coordinate, start_coordinate=800, max_coordinate=1580):
        """
        Verilen koordinata ulaşmak için kaç tane hangi adımdan atmak gerektiğini hesaplar
        
        Args:
            target_coordinate: Hedef koordinat (örn: 1135)
            start_coordinate: Başlangıç koordinatı (varsayılan: 800)
            max_coordinate: Maksimum koordinat (varsayılan: 1580)
        
        Returns:
            dict: Her adım için kaç tane gerektiği {100: 3, 10: 3, 5: 1} gibi
            None: Eğer koordinat ulaşılamaz ise
        """
        # Mevcut adımlar (büyükten küçüğe sıralı)
        # X ekseni (360°) için 50'lik adımlar, Y ekseni (1580) için 100'lük adımlar
        if max_coordinate == 360:
            available_steps = [50, 25, 10, 5, 1, 0.5, 0.1]
        elif max_coordinate == 1580:
            available_steps = [100, 50, 10, 5, 1]
        elif max_coordinate == 100:  # BM-21 Grad yeni limit
            available_steps = [10, 5, 1, 0.5, 0.1]
        # Hedef kontrol
        if target_coordinate < start_coordinate:
            myOwnPrint(f"✗ Hedef koordinat ({target_coordinate}) başlangıçtan ({start_coordinate}) küçük!")
            return None
        
        if target_coordinate > max_coordinate:
            myOwnPrint(f"✗ Hedef koordinat ({target_coordinate}) maksimum koordinattan ({max_coordinate}) büyük!")
            return None
        
        # Kaç birim ilerlemek gerekiyor
        distance = target_coordinate - start_coordinate
        
        # BM-21 Grad düzeltme faktörünü uygula
        correction_factor = self._get_bm21_correction_factor(start_coordinate, target_coordinate)
        distance = distance * correction_factor
        
        # Hangi adımlardan kaç tane gerekiyor
        steps_needed = {}
        remaining = distance
        
        for step_size in available_steps:
            count = int(remaining // step_size)
            if count > 0:
                steps_needed[step_size] = count
                remaining = round(remaining - (count * step_size), 10)  # Float precision fix
        
        # Float precision hatalarını tolere et (1e-9'dan küçük değerler 0 kabul edilir)
        EPSILON = 1e-9
        if remaining > EPSILON:
            myOwnPrint(f"⚠ Uyarı: Tam olarak {target_coordinate} koordinatına ulaşılamadı!")
            myOwnPrint(f"   Kalan mesafe: {remaining:.6f} piksel")
            myOwnPrint(f"   Ulaşılabilecek en yakın: {target_coordinate - remaining:.6f}")
        
        return steps_needed
    
    def calculate_steps_needed_reverse(self, distance, max_coordinate=1580):
        """
        Geriye gitmek için kaç adım gerektiğini hesaplar
        
        Args:
            distance: Geri gidilecek mesafe
            max_coordinate: Maksimum koordinat (adım boyutlarını belirler)
        
        Returns:
            dict: Her adım için kaç tane gerektiği {100: 3, 10: 3, 5: 1} veya {50: 7, 10: 1} gibi
        """
        # X ekseni (360°) için 50'lik adımlar, Y ekseni (1580) için 100'lük adımlar
        if max_coordinate == 360:
            available_steps = [50, 25, 10, 5, 1, 0.5, 0.1]
        elif max_coordinate == 1580:
            available_steps = [100, 50, 10, 5, 1]
        elif max_coordinate == 100:  # BM-21 Grad yeni limit
            available_steps = [10, 5, 1, 0.5, 0.1]
        steps_needed = {}
        remaining = distance
        
        for step_size in available_steps:
            count = int(remaining // step_size)
            if count > 0:
                steps_needed[step_size] = count
                remaining = round(remaining - (count * step_size), 10)  # Float precision fix
        
        # Float precision hatalarını tolere et (1e-9'dan küçük değerler 0 kabul edilir)
        EPSILON = 1e-9
        if remaining > EPSILON:
            myOwnPrint(f"⚠ Uyarı: Tam olarak {distance:.6f} piksel geri gidilemedi!")
            myOwnPrint(f"   Kalan mesafe: {remaining:.6f} piksel")
        
        return steps_needed
    def play_to_coordinate_calibrated(self, target_coordinate, max_coordinate=1580, speed_multiplier=1.0):
        global selectedWeapon ,Processing
        myBool=True
        if Processing:
            myOwnPrint("⚠️ Zaten bir koordinata oynatılıyor, lütfen bekleyin...")
            return
        
        while myBool:

            if self.PlayerY:
                print(f"\n🔧 KALIBRASYON #{self.play_coordinate_call_count}: OCR ile gerçek pozisyon kontrol ediliyor...")
                ocr_value = self.reader.read(save_screenshot=True)
                print(f" OCR Degeri PLAYER Y: {ocr_value}")
                if ocr_value is not None:
                    if(selectedWeapon=="BM-21Grad-UKRANIA"):
                        ocr_coord = float(ocr_value)
                    elif(selectedWeapon=="Mortar"):
                        ocr_coord = int(ocr_value)
                    # Oyun ici kordinati cek ve sonrasinda play cordinate i cagir
                    self.current_coordinate = ocr_coord
                else :
                    print("✗ OCR ile koordinat okunamadı, kalibrasyon atlanıyor.")
                    continue
            elif self.PlayerX:
                print(f"\n🔧 KALIBRASYON #{self.play_coordinate_call_count}: OCR ile bearing kontrol ediliyor...")
                ocr_value = self.reader.read(save_screenshot=True)
                print(f" OCR Degeri Player X: {ocr_value}")
                if ocr_value is not None:
                    ocr_coord = float(ocr_value)
                    self.current_coordinate = ocr_coord
                else :
                    print("✗ OCR ile koordinat okunamadı, kalibrasyon atlanıyor.")
                    continue

            if(self.PlayerX):
                tolerance=0.1  # Bearing için tolerans (derece)

                if(selectedWeapon=="BM-21Grad-UKRANIA"):
                    tolerance=0.1  # BM21Grad için tolerans (derece)
                    target_coordinate=int(target_coordinate)
                
                print(f" PlayerX:  Mevcut koordinat: {self.current_coordinate}°, Hedef: {target_coordinate}°")
                if target_coordinate - tolerance <= self.current_coordinate <= target_coordinate + tolerance:
                    print("✓ Zaten hedef koordinattasınız!")
                    myBool=False
                    break
            elif (self.PlayerY):
                if(selectedWeapon=="Mortar"):
                    target_coordinate=int(target_coordinate)
                    tolerance=3
                elif(selectedWeapon=="BM-21Grad-UKRANIA"):
                    tolerance=0
                    target_coordinate=round(target_coordinate,1)
                print(f" PlayerY:  Mevcut koordinat: {self.current_coordinate}, Hedef: {target_coordinate}")
                if target_coordinate - tolerance <= self.current_coordinate <= target_coordinate + tolerance:
                    print("✓ Zaten hedef koordinattasınız!")
                    myBool=False
                    break
            if myBool:
                Processing=True
                self.play_to_coordinate(target_coordinate, speed_multiplier=speed_multiplier, max_coordinate=max_coordinate)
                time.sleep(0.1)  # Add a short delay to prevent rapid execution
        Processing=False

    def play_to_coordinate(self, target_coordinate, max_coordinate=1580, speed_multiplier=1.0):
        global selectedWeapon
        """
        Belirtilen koordinata ulaşmak için gerekli adımları oynatır
        
        Args:
            target_coordinate: Hedef koordinat (örn: 1135)
            max_coordinate: Maksimum koordinat (varsayılan: 1580)
            speed_multiplier: Hız çarpanı (1.0=normal, 2.0=2x hızlı)
        """
        # Current pozisyondan gerekli adımları hesapla
        start_coordinate = self.current_coordinate
        myOwnPrint (f"\n▶ Hedef koordinata gidiliyor: {target_coordinate} (Mevcut: {start_coordinate})")

        # 360 derece sistemi için en kısa yolu bul (wrap-around)
        if max_coordinate == 360 or selectedWeapon=="BM-21Grad-UKRANIA":
            # 3 farklı yolu hesapla
            diff_normal = target_coordinate - start_coordinate  # Normal yol
            diff_wrap_forward = diff_normal - 360  # İleri gidip wrap
            diff_wrap_backward = diff_normal + 360  # Geri gidip wrap
            
            # En kısa yolu seç (mutlak değer en küçük olan)
            options = [
                (diff_normal, "Normal"),
                (diff_wrap_forward, "İleri-Wrap"),
                (diff_wrap_backward, "Geri-Wrap")
            ]
            
            best_diff, path_type = min(options, key=lambda x: abs(x[0]))
            
            # print(f"\n🔄 360° Wrap-Around Analizi:")
            # print(f"   • Normal yol: {abs(diff_normal):.1f}° {'(ileri)' if diff_normal >= 0 else '(geri)'}")
            # print(f"   • İleri-Wrap: {abs(diff_wrap_forward):.1f}° (360→0 üzerinden)")
            # print(f"   • Geri-Wrap: {abs(diff_wrap_backward):.1f}° (0→360 üzerinden)")
            # print(f"   ✅ Seçilen: {path_type} ({abs(best_diff):.1f}°)")
            
            # Seçilen yola göre distance ve direction belirle
            distance = abs(best_diff)
            is_reverse = best_diff < 0
        else:
            # Normal mod (1580 sistemi) - wrap-around yok
            if target_coordinate < start_coordinate:
                # GERİYE GİT
                distance = start_coordinate - target_coordinate
                is_reverse = True
            else:
                # İLERİYE GİT
                distance = target_coordinate - start_coordinate
                is_reverse = False
        
        # Adımları hesapla
        # 360° sisteminde distance direkt kullan (wrap-around için)
        if max_coordinate == 360 or selectedWeapon=="BM-21Grad-UKRANIA":
            steps_needed = self.calculate_steps_needed_reverse(distance, max_coordinate)
        elif is_reverse:
            steps_needed = self.calculate_steps_needed_reverse(distance, max_coordinate)
        else:
            steps_needed = self.calculate_steps_needed(target_coordinate, start_coordinate, max_coordinate)
        
        if steps_needed is None:
            return
        
        if not steps_needed:
            myOwnPrint("✓ Zaten hedef koordinattasınız!")
            return

        # 100 sistemi (BM-21 Grad) için yönü ters çevir
        is_reverse = not is_reverse if max_coordinate == 100 else is_reverse
        
        # Adımları göster
        myOwnPrint(f"\n📍 Hedef Koordinat: {target_coordinate}")
        myOwnPrint(f"   Mevcut Pozisyon: {start_coordinate}")
        myOwnPrint(f"   Yön: {'◀ GERİ' if is_reverse else '▶ İLERİ'}")
        myOwnPrint(f"   Mesafe: {distance:.2f} {'derece' if max_coordinate == 360 else 'piksel'}")
        myOwnPrint(f"\n📋 Gerekli Adımlar:")
        
        for step_size, count in steps_needed.items():
            myOwnPrint(f"   • {count} tane {step_size}'lik adım {'(geri)' if is_reverse else '(ileri)'}")
        
        # Adımları sırayla oynat - her adım büyüklüğü için ayrı ayrı
        for step_size, count in steps_needed.items():
            for i in range((int)(count)):
                # max_coordinate parametresine göre makro menzilini belirle
                macro_range = 50 if max_coordinate == 360 else 100
                macro_range = 10 if max_coordinate == 100 else macro_range  # BM-21 Grad
                step_size_adjusted = step_size / 2 if max_coordinate == 360 and selectedWeapon=="Mortar" else step_size
                
                self.play_steps(step_size_adjusted if not is_reverse else -step_size_adjusted, speed_multiplier, max_range=macro_range)
        
        # Current pozisyonu güncelle
        self.current_coordinate = target_coordinate
        myOwnPrint(f"\n✓ Hedef koordinata ulaşıldı: {target_coordinate}")
        myOwnPrint(f"   Mevcut Pozisyon: {self.current_coordinate}")
    
    def play_steps(self, steps, speed_multiplier=1.0, max_range=100):
        """
        Belirli adım kadar makroyu oynatır (0-max_range sistemine göre)
        Negatif steps değeri ile geriye hareket eder
        
        Args:
            steps: Kaç adım ilerlemek istediğiniz (5, 10, 50 gibi) - Negatif değer geriye gider
            speed_multiplier: Hız çarpanı (1.0=normal, 2.0=2x hızlı, 0.5=yarı hız)
            max_range: Makronun maksimum menzili (100 veya 50)
        """
        if not self.movements:
            myOwnPrint("✗ Hareket verisi yok!")
            return
        
        # Yön kontrolü
        is_reverse = steps < 0
        abs_steps = abs(steps)
        
        # Kaç hareket gerektiğini hesapla (steps/max_range oranında)
        total_movements = len(self.movements)
        movements_to_play = int((abs_steps / max_range) * total_movements)
        
        if movements_to_play < 1:
            movements_to_play = 1
        if movements_to_play > total_movements:
            movements_to_play = total_movements
        
        direction_text = 'geri' if is_reverse else 'ileri'
        
        try:
            prev_x, prev_y = self.movements[0][0], self.movements[0][1]
            
            for i in range(movements_to_play):
                x, y, delay = self.movements[i]
                
                if i > 0:
                    # Hız çarpanını uygula
                    adjusted_delay = delay / speed_multiplier
                    time.sleep(adjusted_delay)
                    
                    # Göreceli hareket hesapla
                    dx = x - prev_x
                    dy = y - prev_y
                    
                    # Eğer geriye gidiyorsak hareketi ters çevir
                    if is_reverse:
                        dx = -dx
                        dy = -dy
                    
                    if dx != 0 or dy != 0:
                        self.move_mouse_relative(dx, dy)
                    
                    prev_x, prev_y = x, y
            
            # Current pozisyonu güncelle
            if is_reverse:
                self.current_coordinate -= abs_steps
            else:
                self.current_coordinate += abs_steps
            
            myOwnPrint(f"✓ {abs_steps} adım ({direction_text}) tamamlandı!")
            myOwnPrint(f"   Mevcut Pozisyon: {self.current_coordinate}")
            
        except KeyboardInterrupt:
            myOwnPrint("\n✗ Durduruldu")
        except Exception as e:
            myOwnPrint(f"\n✗ Hata: {e}")

playerX, playerY = None, None

playersAreSetted=False
def initMortar():
    global playerX, playerY, playersAreSetted , selectedWeapon
    # RulerReader instance oluştur (cetvel okuma için - config.py'den)
    ruler_reader = RulerReader(left=config.RADIAN_LEFT, top=config.RADIAN_TOP, width=config.RADIAN_WIDTH, height=config.RADIAN_HEIGHT)
    bearing_reader = BearingReader(left=config.BEARING_LEFT, top=config.BEARING_TOP, width=config.BEARING_WIDTH, height=config.BEARING_HEIGHT)
    # RazerMacroPlayer instance'larını OCR reader ile oluştur (config.py'den)
    # sensitivity parametresi oyun içi mouse hassasiyetini kompanse eder
    playerY = RazerMacroPlayer(globalMortarMacroPathY, dpi_scale=config.DPI_SCALE, sensitivity=config.SENSITIVITY, Controller="Y", reader=ruler_reader)
    playerX = RazerMacroPlayer(globalMortarMacroPathX, dpi_scale=config.DPI_SCALE, sensitivity=config.SENSITIVITY, Controller="X", reader=bearing_reader)
    # Başlangıç koordinatları (config.py'den)
    playerY.current_coordinate = config.PLAYER_Y_START
    playerX.current_coordinate = config.PLAYER_X_START
    playersAreSetted=True
    selectedWeapon="Mortar"


def initUKRANIABm21Grad():
    global playerY, playerX,playersAreSetted,selectedWeapon
    # RulerReader instance oluştur (cetvel okuma için - config.py'den)
    degree_reader = DegreeReader(config.BM21GRAD_DEGREES[0], config.BM21GRAD_DEGREES[1], config.BM21GRAD_DEGREES[2], config.BM21GRAD_DEGREES[3])
    bearing_reader = BearingReader(config.BM21GRAD_BEARING[0], config.BM21GRAD_BEARING[1], config.BM21GRAD_BEARING[2], config.BM21GRAD_BEARING[3])
    # RazerMacroPlayer instance'ını OCR reader ile oluştur (config.py'den)
    # sensitivity parametresi oyun içi mouse hassasiyetini kompanse eder
    playerY = RazerMacroPlayer(globalUKRANIABM21MacroPathY, dpi_scale=config.DPI_SCALE, sensitivity=config.SENSITIVITY, Controller="Y", reader=degree_reader)
    playerX = RazerMacroPlayer(globalUKRANIABM21MacroPathX, dpi_scale=config.DPI_SCALE, sensitivity=config.SENSITIVITY, Controller="X", reader=bearing_reader)
    # Başlangıç koordinatları (config.py'den)
    playerY.current_coordinate = config.PLAYER_Y_DEGREE_START
    playerX.current_coordinate = 0
    playersAreSetted=True
    selectedWeapon="BM-21Grad-UKRANIA"


def calibrateRadian(radian):
    global playerY
    playerY.play_to_coordinate_calibrated(radian)

def calibrateBmDegree(degree):
    global playerY
    playerY.play_to_coordinate_calibrated(degree, max_coordinate=100,speed_multiplier=2.0)

def calibrateDegrees(degrees):
    global playerX
    # Derece kontrolü: 0-360 arası olmalı
    if 0 <= degrees <= 360:
        playerX.play_to_coordinate_calibrated(degrees, max_coordinate=360, speed_multiplier=2.0)
    else:
        myOwnPrint(f"✗ Hata: Derece değeri 0-360 arasında olmalı! (Girilen: {degrees})")

def abortRadian():
    global playerY
    playerY.set_abort(True)
    myOwnPrint("Radian calibration aborted.")
    

def abortDegrees():
    global playerX
    playerX.set_abort(True)
    myOwnPrint("Degrees calibration aborted.")


# KULLANIM ÖRNEKLERİ
if __name__ == "__main__":
    initUKRANIABm21Grad()
    current = 0  # Başlangıç derecesi
    
    def on_press(key):
        global current
        """Klavye tuşlarını dinler"""
        try:
            if hasattr(key, 'char') and key.char == ']':
                myOwnPrint(f"\n] Tuşuna basıldı - {current} → {current+10}° gidiliyor...")
                current += 50
                playerX.play_to_coordinate_calibrated(current, max_coordinate=360)
                
            if hasattr(key, 'char') and key.char == '[':
                myOwnPrint(f"\n[ Tuşuna basıldı - {current} → {current-10}° gidiliyor...")
                current -= 50
                playerX.play_to_coordinate_calibrated(current, max_coordinate=360)
                
            if hasattr(key, 'char') and key.char == '\'':
                myOwnPrint(f"\n' Tuşuna basıldı - 90° (test pozisyonu) gidiliyor...")
                current = 210
                playerX.play_to_coordinate_calibrated(210, max_coordinate=360)

        except Exception as e:
            myOwnPrint(f"Hata: {e}")


    # Keyboard listener'ı başlat
    myOwnPrint("\n" + "="*60)
    myOwnPrint("🎮 BM-21 GRAD KALİBRASYON SİSTEMİ AKTIF")
    myOwnPrint("="*60)
    myOwnPrint(f"📊 Derece Aralığı: 5° - 100° (Mevcut: {current}°)")
    myOwnPrint("\n⌨️  Kontroller:")
    myOwnPrint("   ] tuşu: +10° ileri git")
    myOwnPrint("   [ tuşu: -10° geri git")
    myOwnPrint("   ' tuşu: 90° test pozisyonuna git")
    myOwnPrint("\n🔧 Kalibrasyon Sistemi:")
    myOwnPrint("   • 5-14°: Referans bölge (düzeltme yok)")
    myOwnPrint("   • 14°+: Her derece için %1 artış")
    myOwnPrint("   • 100°: Maksimum düzeltme (~%86)")
    myOwnPrint("\n⚠️  Çıkmak için Ctrl+C")
    myOwnPrint("="*60 + "\n")

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

    try:
        # Sonsuz döngü - Ctrl+C ile çıkılabilir
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        myOwnPrint("\n✓ Program sonlandırıldı")
        listener.stop()