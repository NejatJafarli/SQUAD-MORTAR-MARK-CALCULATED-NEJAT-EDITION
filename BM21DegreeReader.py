import cv2
import pytesseract
import numpy as np
from PIL import ImageGrab
import re
import config

# Windows için Tesseract yolu (gerekirse açın)
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

class DegreeReader:
    def __init__(self, left, top, width, height):
        """
        Derece okuyucu
        
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
        
        # Görüntüyü büyüt (4x daha iyi OCR için - küçük alan)
        scale_factor = 4
        height, width = gray.shape
        resized = cv2.resize(gray, (width * scale_factor, height * scale_factor), 
                            interpolation=cv2.INTER_CUBIC)
        
        # Kontrast artırma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(resized)
        
        # Binary threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Gürültü azaltma
        denoised = cv2.fastNlMeansDenoising(binary, h=10)
        
        return denoised
    
    def parse_degree(self, text):
        """
        Derece metnini parse et
        
        Format: 43.5° veya 43.5 veya 327.9°
        Çıktı: 43.5 (float)
        """
        # Temizle
        text = text.strip()
        
        # ° işaretini kaldır
        text = text.replace('°', '')
        text = text.replace('o', '')  # Bazen o harfi olarak algılanabilir
        text = text.replace('O', '')
        
        # Regex ile sayı bul (ondalıklı veya tam sayı)
        # 43.5 veya 327.9 gibi
        match = re.search(r'(\d+\.?\d*)', text)
        
        if match:
            try:
                value = float(match.group(1))
                # 0-360 aralığında kontrol et
                if 0 <= value <= 360:
                    return value
                else:
                    print(f"Uyarı: Değer aralık dışı: {value}")
                    return None
            except ValueError:
                print(f"Değer dönüştürme hatası: {text}")
                return None
        
        return None
    
    def read(self, save_screenshot=False):
        """
        Ekranı yakala ve dereceyi oku
        
        Args:
            save_screenshot: True ise yakalanan görüntüyü kaydet
        
        Returns:
            float: Okunan derece (örn: 43.5)
        """
        # Ekranı yakala
        screenshot_path = "degree_capture.png" if save_screenshot else None
        img = self.capture_screen(screenshot_path)
        
        # Görüntüyü işle
        processed = self.preprocess_image(img)
        
        # Debug için kaydet
        if save_screenshot:
            cv2.imwrite("degree_processed.png", processed)
        
        # OCR config - sadece sayılar, nokta ve derece işareti
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.°'
        
        # OCR uygula
        text = pytesseract.image_to_string(processed, config=custom_config)
        
        # Parse et
        degree = self.parse_degree(text)
        
        if degree is not None:
            print(f"✓ Derece: {degree}°")
            return degree
        else:
            print(f"✗ Derece okunamadı. OCR sonucu: '{text.strip()}'")
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
                degree = self.read(save_screenshot=False)
                print("-" * 40)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nOkuma durduruldu.")


# =====================================================
# KULLANIM
# =====================================================

if __name__ == "__main__":
    
    # Derece bölgesi (örnek koordinatlar)
    LEFT = 100
    TOP = 100
    WIDTH = 80    # Derece genişliği (43.5° gibi küçük)
    HEIGHT = 30   # Derece yüksekliği
    
    # Reader oluştur
    reader = DegreeReader(LEFT, TOP, WIDTH, HEIGHT)
    
    print("="*50)
    print("DERECE OKUYUCU")
    print("="*50)
    
    # TEK OKUMA
    print("\nDerece okunuyor...")
    degree = reader.read(save_screenshot=True)
    
    if degree is not None:
        print(f"\n✓ Başarılı! Derece: {degree}°")
        print("\nÖrnekler:")
        print("  43.5°")
        print("  327.9°")
        print("  180.0°")
    else:
        print("\n✗ Okuma başarısız!")
        print("degree_capture.png ve degree_processed.png dosyalarını kontrol edin")
    
    # SÜREKLİ OKUMA (İstenirse)
    # Aşağıdaki satırın yorumunu kaldır
    # reader.continuous_reading(interval=0.5)
    
    print("\n" + "="*50)
    print("KULLANIM:")
    print("="*50)
    print("Tek okuma:")
    print("  degree = reader.read_degree(save_screenshot=True)")
    print("\nSürekli okuma:")
    print("  reader.continuous_reading(interval=0.5)")
    print("="*50)