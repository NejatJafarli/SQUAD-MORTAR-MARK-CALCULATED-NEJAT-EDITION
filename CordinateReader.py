import cv2
import pytesseract
import numpy as np
from PIL import ImageGrab
import re
import time
import config

# Windows için Tesseract yolu (gerekirse açın)
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

class CoordinateReader:
    def __init__(self, left, top, width, height):
        """
        Koordinat okuyucu
        
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
            print(f"Görüntü kaydedildi: {save_path}")
        
        return img_bgr
    
    def preprocess_image(self, img):
        """
        Görüntüyü OCR için hazırlar
        """
        # Gri tonlamaya çevir
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Görüntüyü büyüt (3x daha iyi OCR için)
        scale_factor = 3
        height, width = gray.shape
        resized = cv2.resize(gray, (width * scale_factor, height * scale_factor), 
                            interpolation=cv2.INTER_CUBIC)
        
        # Kontrast artırma
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(resized)
        
        # Binary threshold (Otsu)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Gürültü azaltma
        denoised = cv2.fastNlMeansDenoising(binary, h=10)
        
        return denoised
    
    def fix_ocr_errors(self, text):
        """
        Yaygın OCR hatalarını düzelt
        """
        # Küçük harfleri büyük yap
        text = text.upper()
        
        # Küçük L → büyük I
        text = text.replace('L', 'I')
        
        return text.strip()
    
    def parse_coordinate(self, text):
        """
        Koordinat metnini parse et
        
        FORMAT KURALI:
        - Harf (A-Z): 1 karakter
        - İlk sayı: 1-2 haneli (7 veya 12)
        - İkinci sayı: TEK HANELİ (0-9)
        - Üçüncü sayı: TEK HANELİ (0-9)
        
        Örnekler:
        - G7-8-6   → G07-8-6   ✓
        - G12-9-7  → G12-9-7   ✓
        - I5-3-1   → I05-3-1   ✓
        - J04-49-9 → J04-4-9   ✓ (49 → 4, ikinci sayı tek haneli olmalı)
        """
        text = self.fix_ocr_errors(text)
        
        # Pattern: Harf + sayılar + tire + sayılar + tire + sayılar
        pattern = r'([A-Z])[\s\-]*(\d{1,3})[\s\-]+(\d+)[\s\-]+(\d+)'
        
        match = re.search(pattern, text)
        
        if match:
            letter = match.group(1)
            main_num = match.group(2)
            sub_num1 = match.group(3)
            sub_num2 = match.group(4)
            
            # İlk sayıyı düzelt (1-2 haneli olmalı, 2 haneli yap)
            if len(main_num) > 2:
                # Eğer 3+ haneli ise ilk 2 hanesini al
                main_num = main_num[:2]
            main_num = main_num.zfill(2)  # 2 haneli yap: 7→07, 12→12
            
            # İkinci sayıyı düzelt (TEK HANELİ olmalı, 0-9)
            if len(sub_num1) > 1:
                # Eğer çift haneli ise (örn: 49), ilk hanesini al
                sub_num1 = sub_num1[0]
                print(f"  ⚠️ İkinci sayı düzeltildi: {match.group(3)} → {sub_num1}")
            
            # Üçüncü sayıyı düzelt (TEK HANELİ olmalı, 0-9)
            if len(sub_num2) > 1:
                # Eğer çift haneli ise, ilk hanesini al
                sub_num2 = sub_num2[0]
                print(f"  ⚠️ Üçüncü sayı düzeltildi: {match.group(4)} → {sub_num2}")
            
            # 0-9 aralığında kontrol
            try:
                if not (0 <= int(sub_num1) <= 9):
                    print(f"  ⚠️ İkinci sayı aralık dışı: {sub_num1}")
                    return None
                if not (0 <= int(sub_num2) <= 9):
                    print(f"  ⚠️ Üçüncü sayı aralık dışı: {sub_num2}")
                    return None
            except ValueError:
                print(f"  ⚠️ Sayı dönüştürme hatası")
                return None
            
            result = f"{letter}{main_num}-{sub_num1}-{sub_num2}"
            return result
        
        return None
    
    def read_coordinate(self, save_screenshot=False):
        """
        Ekranı yakala ve koordinatı oku
        
        Args:
            save_screenshot: True ise yakalanan görüntüyü kaydet
        
        Returns:
            str: Okunan koordinat (örn: "G07-8-6")
        """
        # Ekranı yakala
        screenshot_path = "coordinate_capture.png" if save_screenshot else None
        img = self.capture_screen(screenshot_path)
        
        # Görüntüyü işle
        processed = self.preprocess_image(img)
        
        # Debug için kaydet
        if save_screenshot:
            cv2.imwrite("coordinate_processed.png", processed)
        
        # OCR config - sadece büyük harfler, sayılar ve tire
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
        
        # OCR uygula
        text = pytesseract.image_to_string(processed, config=custom_config)
        
        print(f"  OCR ham sonuç: '{text.strip()}'")
        
        # Parse et
        coordinate = self.parse_coordinate(text)
        
        if coordinate:
            print(f"✓ Koordinat: {coordinate}")
            return coordinate
        else:
            print(f"✗ Koordinat okunamadı")
            return None
    
    def continuous_reading(self, interval=0.5):
        """
        Belirli aralıklarla sürekli okuma yapar
        """
        import time
        
        print(f"Sürekli okuma başlatıldı (Her {interval} saniyede)")
        print("Durdurmak için Ctrl+C basın\n")
        
        try:
            while True:
                coord = self.read_coordinate(save_screenshot=False)
                print("-" * 40)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nOkuma durduruldu.")


# =====================================================
# KULLANIM
# =====================================================

if __name__ == "__main__":
    
    # Reader oluştur
    reader = CoordinateReader(1175, 40, 110, 40)
    
    print("="*50)
    print("KOORDINAT OKUYUCU (GELİŞTİRİLMİŞ)")
    print("="*50)
    print("\nFORMAT KURALLARI:")
    print("  Harf: A-Z (1 karakter)")
    print("  İlk sayı: 01-99 (2 haneli)")
    print("  İkinci sayı: 0-9 (TEK HANELİ)")
    print("  Üçüncü sayı: 0-9 (TEK HANELİ)")
    print("\nÖRNEKLER:")
    print("  G7-8-6   → G07-8-6   ✓")
    print("  G12-9-7  → G12-9-7   ✓")
    print("  I5-3-1   → I05-3-1   ✓")
    print("  J04-49-9 → J04-4-9   ✓ (otomatik düzeltme)")
    print("="*50)

    time.sleep(2)  # Başlamadan önce bekle
    
    # TEK OKUMA
    print("\nKoordinat okunuyor...")
    coord = reader.read_coordinate(save_screenshot=True)
    
    if coord:
        print(f"\n✅ BAŞARILI! Koordinat: {coord}")
    else:
        print("\n❌ OKUMA BAŞARISIZ!")
        print("coordinate_capture.png ve coordinate_processed.png dosyalarını kontrol edin")
    
    # SÜREKLİ OKUMA (İstenirse)
    # Aşağıdaki satırın yorumunu kaldır
    # reader.continuous_reading(interval=0.5)
    
    print("\n" + "="*50)