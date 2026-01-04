import cv2
import pytesseract
import numpy as np
from PIL import ImageGrab, Image
import time
from pynput import keyboard

# Windows için Tesseract yolu (gerekirse açın)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# myOwnPrint fonksiyonunu start_system'den import et
try:
    from start_system import myOwnPrint, DEBUG_MODE
except ImportError:
    # Standalone modda çalışıyorsa fallback
    DEBUG_MODE = False
    def myOwnPrint(message):
        if DEBUG_MODE:
            print(message)

class RulerReader:
    def __init__(self, left, top, width, height):
        """
        Ekran yakalama bölgesi ayarları
        
        Args:
            left: Sol üst köşe X koordinatı
            top: Sol üst köşe Y koordinatı
            width: Genişlik (piksel)
            height: Yükseklik (piksel)
        """
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.bbox = (left, top, left + width, top + height)
    
    def capture_screen(self, save_path=None):
        """
        Ekranın belirtilen bölgesini yakalar
        
        Args:
            save_path: Kaydedilecek dosya yolu (opsiyonel)
        
        Returns:
            numpy array: Yakalanan görüntü
        """
        # Ekran bölgesini yakala
        screenshot = ImageGrab.grab(bbox=self.bbox)
        
        # PIL'den numpy array'e çevir
        img_np = np.array(screenshot)
        
        # RGB'den BGR'ye çevir (OpenCV için)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # Kaydet (istenirse)
        if save_path:
            cv2.imwrite(save_path, img_bgr)
            myOwnPrint(f"Görüntü kaydedildi: {save_path}")
        
        return img_bgr
    
    def extract_numbers_with_positions(self, img):
        """
        Cetvel üzerindeki sayıları ve pozisyonlarını çıkarır
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # DEBUG: Orijinal gri görüntü
        cv2.imwrite("debug_1_gray.png", gray)
        myOwnPrint("✓ Debug: gray görüntü kaydedildi")
        
        # Sol taraftaki cetvel bölgesini al
        roi = gray[0:height, 0:int(width*0.5)]
        
        # DEBUG: ROI
        cv2.imwrite("debug_2_roi.png", roi)
        myOwnPrint("✓ Debug: ROI kaydedildi")
        
        # Kontrast artırma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(roi)
        
        # DEBUG: Kontrast artırılmış
        cv2.imwrite("debug_3_enhanced.png", enhanced)
        myOwnPrint("✓ Debug: Enhanced görüntü kaydedildi")
        
        # Threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # DEBUG: Binary
        cv2.imwrite("debug_4_binary.png", binary)
        myOwnPrint("✓ Debug: Binary görüntü kaydedildi")
        
        # Gürültü azaltma
        denoised = cv2.fastNlMeansDenoising(binary, h=10)
        
        # DEBUG: Denoised
        cv2.imwrite("debug_5_denoised.png", denoised)
        myOwnPrint("✓ Debug: Denoised görüntü kaydedildi")
        
        # Morfolojik işlem
        kernel = np.ones((2,2), np.uint8)
        cleaned = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
        
        # DEBUG: Cleaned
        cv2.imwrite("debug_6_cleaned.png", cleaned)
        myOwnPrint("✓ Debug: Cleaned görüntü kaydedildi")
        
        # OCR
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
        data = pytesseract.image_to_data(cleaned, config=custom_config, 
                                        output_type=pytesseract.Output.DICT)
        
        # DEBUG: OCR sonuçlarını yazdır
        myOwnPrint("\n📝 OCR Sonuçları:")
        detected_texts = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if text:
                detected_texts.append(f"'{text}' (güven: {data['conf'][i]})")
        myOwnPrint(f"   Tespit edilen metinler: {', '.join(detected_texts)}")
        
        # DEBUG: OCR sonuçlarını görsel üzerine çiz
        debug_img = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if text:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(debug_img, text, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.imwrite("debug_7_ocr_results.png", debug_img)
        myOwnPrint("✓ Debug: OCR sonuçları görüntü üzerine çizildi")
        
        numbers_with_positions = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if text and len(text) >= 3 and text.isdigit():
                num = int(text)
                # 800-1580 aralığında kontrol et
                if 800 <= num <= 1580:
                    y_center = data['top'][i] + data['height'][i] // 2
                    numbers_with_positions.append({
                        'value': num,
                        'y': y_center
                    })
        
        myOwnPrint(f"   ✓ {len(numbers_with_positions)} adet geçerli sayı bulundu: {[n['value'] for n in numbers_with_positions]}\n")
        
        return numbers_with_positions
    
    def find_pointer_value(self, img):
        """
        Pointer'ın gösterdiği değeri hesaplar
        """
        height, width = img.shape[:2]
        
        # Pointer pozisyonu - görüntünün ortasında kabul et
        # Veya belirli bir Y koordinatı verebilirsin
        pointer_y = height // 2
        
        myOwnPrint(f"🎯 Pointer pozisyonu: Y={pointer_y} (Görüntü yüksekliği: {height})")
        
        # Sayıları çıkar
        numbers = self.extract_numbers_with_positions(img)
        
        if len(numbers) < 2:
            myOwnPrint(f"❌ Yeterli sayı okunamadı! Sadece {len(numbers)} sayı bulundu.")
            return None, "Yeterli sayı okunamadı"
        
        # Y pozisyonuna göre sırala
        numbers.sort(key=lambda x: x['y'])
        
        myOwnPrint("\n📊 Bulunan sayılar (Y pozisyonlarına göre sıralı):")
        for n in numbers:
            myOwnPrint(f"   {n['value']} -> Y={n['y']}")
        
        # ÖNEMLİ: Pointer tam bir sayının üzerinde mi kontrol et (±15 piksel tolerans)
        EXACT_MATCH_TOLERANCE = 5
        for n in numbers:
            distance = abs(n['y'] - pointer_y)
            if distance <= EXACT_MATCH_TOLERANCE:
                myOwnPrint(f"\n🎯 TAM EŞLEŞME BULUNDU! Pointer {n['value']} değerinin tam üzerinde (mesafe: {distance}px)")
                
                # DEBUG görüntüsü
                debug_img = img.copy()
                for num in numbers:
                    cv2.circle(debug_img, (50, num['y']), 5, (0, 255, 0), -1)
                    cv2.putText(debug_img, str(num['value']), (70, num['y']), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Tam eşleşen değeri vurgula
                cv2.circle(debug_img, (50, n['y']), 15, (255, 0, 255), 3)
                cv2.line(debug_img, (0, pointer_y), (debug_img.shape[1], pointer_y), (255, 0, 0), 2)
                cv2.putText(debug_img, f"TAM ESLESME: {n['value']}", (10, pointer_y-15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
                
                cv2.imwrite("debug_8_final_result.png", debug_img)
                myOwnPrint("✓ Debug: Final sonuç görüntüsü kaydedildi (tam eşleşme)")
                
                return float(n['value']), {'exact_match': True, 'value': n['value'], 'distance': distance}
        
        # Tam eşleşme yoksa, normal interpolasyon yap
        myOwnPrint("\n📍 Tam eşleşme yok, interpolasyon yapılıyor...")
        
        # Pointer'a en yakın üst ve alt sayıları bul
        above = [n for n in numbers if n['y'] < pointer_y]
        below = [n for n in numbers if n['y'] > pointer_y]
        
        myOwnPrint(f"\n🔼 Pointer üstündeki sayılar: {[n['value'] for n in above]}")
        myOwnPrint(f"🔽 Pointer altındaki sayılar: {[n['value'] for n in below]}")
        
        # EDGE CASE: Sadece bir tarafta sayı var (ekstrem pozisyonlar)
        if not above and below:
            # Pointer en üstte (minimum değer civarında, örn: 800)
            closest = min(below, key=lambda x: abs(x['y'] - pointer_y))
            distance = abs(closest['y'] - pointer_y)
            
            # Eğer en alttaki sayıya çok yakınsak, 800 olarak kabul et
            if closest['value'] >= 800 and closest['value'] <= 850:
                result = 800
                myOwnPrint(f"🔽 MINIMUM POZİSYON: En alttaki sayı {closest['value']}, mesafe {distance}px → {result}")
                return float(result), {'edge_case': 'minimum', 'closest': closest['value'], 'distance': distance}
            else:
                # Değilse, en yakın sayıyı kullan
                result = closest['value']
                myOwnPrint(f"⚠ Sadece altta sayı var, en yakını kullanılıyor: {result}")
                return float(result), {'edge_case': 'only_below', 'value': result}
        
        if not below and above:
            # Pointer en altta (maksimum değer civarında, örn: 1580)
            closest = max(above, key=lambda x: abs(x['y'] - pointer_y))
            distance = abs(closest['y'] - pointer_y)
            
            # Eğer en üstteki sayıya çok yakınsak, 1580 olarak kabul et
            if closest['value'] >= 1550 and closest['value'] <= 1580:
                result = 1580
                myOwnPrint(f"🔼 MAKSİMUM POZİSYON: En üstteki sayı {closest['value']}, mesafe {distance}px → {result}")
                return float(result), {'edge_case': 'maximum', 'closest': closest['value'], 'distance': distance}
            else:
                # Değilse, en yakın sayıyı kullan
                result = closest['value']
                myOwnPrint(f"⚠ Sadece üstte sayı var, en yakını kullanılıyor: {result}")
                return float(result), {'edge_case': 'only_above', 'value': result}
        
        if not above and not below:
            # Hiç sayı yok veya pointer tam ortada
            myOwnPrint("❌ Pointer pozisyonu bulunamadı!")
            return None, "Pointer pozisyonu bulunamadı"
        
        # En yakın olanları al
        closest_above = max(above, key=lambda x: x['y'])
        closest_below = min(below, key=lambda x: x['y'])
        
        myOwnPrint(f"\n🎯 En yakın sayılar:")
        myOwnPrint(f"   Üst: {closest_above['value']} (Y={closest_above['y']})")
        myOwnPrint(f"   Alt: {closest_below['value']} (Y={closest_below['y']})")
        
        # Lineer interpolasyon
        y_range = closest_below['y'] - closest_above['y']
        y_offset = pointer_y - closest_above['y']
        value_range = closest_below['value'] - closest_above['value']
        
        if y_range == 0:
            myOwnPrint("❌ Bölme hatası!")
            return None, "Bölme hatası"
        
        result = closest_above['value'] + (y_offset / y_range) * value_range
        
        myOwnPrint(f"\n🧮 Hesaplama:")
        myOwnPrint(f"   Y aralığı: {y_range}")
        myOwnPrint(f"   Y offset: {y_offset}")
        myOwnPrint(f"   Değer aralığı: {value_range}")
        myOwnPrint(f"   Sonuç: {closest_above['value']} + ({y_offset}/{y_range}) * {value_range} = {result}")
        
        # DEBUG: Görsel çıktı - bulunan sayıları ve pointer'ı göster
        debug_img = img.copy()
        for n in numbers:
            cv2.circle(debug_img, (50, n['y']), 5, (0, 255, 0), -1)
            cv2.putText(debug_img, str(n['value']), (70, n['y']), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Pointer çizgisi
        cv2.line(debug_img, (0, pointer_y), (debug_img.shape[1], pointer_y), (255, 0, 0), 2)
        cv2.putText(debug_img, f"POINTER: {round(result, 1)}", (10, pointer_y-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        
        # En yakın sayıları vurgula
        cv2.circle(debug_img, (50, closest_above['y']), 8, (0, 0, 255), 2)
        cv2.circle(debug_img, (50, closest_below['y']), 8, (0, 0, 255), 2)
        
        cv2.imwrite("debug_8_final_result.png", debug_img)
        myOwnPrint("✓ Debug: Final sonuç görüntüsü kaydedildi")
        
        # Debug bilgisi
        debug_info = {
            'above': closest_above['value'],
            'below': closest_below['value'],
            'pointer_y': pointer_y,
            'result': round(result, 1),
            'all_numbers': [n['value'] for n in numbers]
        }
        
        return round(result, 1), debug_info
    
    def read(self, save_screenshot=False):
        """
        Ekranı yakala ve cetvel değerini oku
        
        Args:
            save_screenshot: True ise yakalanan görüntüyü kaydet
        
        Returns:
            float: Okunan cetvel değeri
        """
        # Ekranı yakala
        screenshot_path = "ruler_capture.png" if save_screenshot else None
        img = self.capture_screen(screenshot_path)
        
        # Değeri oku
        value, debug = self.find_pointer_value(img)
        
        if value is None:
            myOwnPrint(f"Hata: {debug}")
            return None
        else:
            myOwnPrint(f"Okunan değer: {value}")
            myOwnPrint(f"Debug: {debug}")
            return value
    
    def continuous_reading(self, interval=1.0):
        """
        Belirli aralıklarla sürekli okuma yapar
        
        Args:
            interval: Okuma aralığı (saniye)
        """
        myOwnPrint(f"Sürekli okuma başlatıldı (Her {interval} saniyede)")
        myOwnPrint("Durdurmak için Ctrl+C basın\n")
        
        try:
            while True:
                value = self.read(save_screenshot=False)
                if value:
                    myOwnPrint(f"Değer: {value}")
                myOwnPrint("-" * 40)
                time.sleep(interval)
        except KeyboardInterrupt:
            myOwnPrint("\nOkuma durduruldu.")


# KULLANIM ÖRNEKLERİ
if __name__ == "__main__":
    
    # 1. Ekran bölgesi koordinatları (config.py'den)
    LEFT = config.RADIAN_LEFT
    TOP = config.RADIAN_TOP
    WIDTH = config.RADIAN_WIDTH
    HEIGHT = config.RADIAN_HEIGHT
    
    # Reader oluştur
    reader = RulerReader(LEFT, TOP, WIDTH, HEIGHT)
    
    myOwnPrint("="*50)
    myOwnPrint("CETVEL OKUYUCU - HOTKEY MOD")
    myOwnPrint("="*50)
    myOwnPrint("🎮 Kontroller:")
    myOwnPrint("   \\ tuşuna basın: Cetvel değerini oku")
    myOwnPrint("   Ctrl+C: Programı kapat\n")
    
    def on_press(key):
        """Klavye tuşlarını dinler"""
        try:
            if hasattr(key, 'char') and key.char == '\\':
                myOwnPrint("\n" + "="*50)
                myOwnPrint("📏 Okuma yapılıyor...")
                myOwnPrint("="*50)
                value = reader.read(save_screenshot=True)
                
                if value:
                    myOwnPrint(f"\n✓ Başarılı! Okunan değer: {value}")
                else:
                    myOwnPrint("\n✗ Okuma başarısız!")
                myOwnPrint("="*50 + "\n")
        except Exception as e:
            myOwnPrint(f"Hata: {e}")
    
    # Keyboard listener'ı başlat
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