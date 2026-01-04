import cv2
import pytesseract
import numpy as np
from PIL import ImageGrab
import time
import re
import config

# Windows için Tesseract yolu
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

# myOwnPrint fonksiyonunu start_system'den import et
try:
    from start_system import myOwnPrint, DEBUG_MODE
except ImportError:
    # Standalone modda çalışıyorsa fallback
    DEBUG_MODE = False
    def myOwnPrint(message):
        if DEBUG_MODE:
            print(message)
            
class BearingReader:
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
    
    def preprocess_image(self, img):
        """
        Görüntüyü OCR için hazırlar
        """
        # Gri tonlamaya çevir
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Görüntüyü büyüt (daha iyi OCR için)
        scale_factor = 3
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
    
    def extract_bearing_value(self, img):
        """
        Bearing değerini çıkarır
        
        Returns:
            float: Bearing değeri (0-360 arası)
        """
        # Görüntüyü işle
        processed = self.preprocess_image(img)
        
        # OCR config - sadece sayılar ve nokta
        custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.'
        
        # OCR uygula
        text = pytesseract.image_to_string(processed, config=custom_config)
        
        # Sonucu temizle
        text = text.strip().replace(' ', '').replace('\n', '')
        
        # Sayıyı çıkar
        # Regex ile sayı bul (ondalıklı veya tam sayı)
        match = re.search(r'\d+\.?\d*', text)
        
        if match:
            try:
                value = float(match.group())
                # 0-360 aralığında kontrol et
                if 0 <= value <= 360:
                    return value
                else:
                    myOwnPrint(f"Uyarı: Değer aralık dışı: {value}")
                    return None
            except ValueError:
                myOwnPrint(f"Değer dönüştürme hatası: {text}")
                return None
        else:
            myOwnPrint(f"Sayı bulunamadı. OCR sonucu: '{text}'")
            return None
    
    def read(self, save_screenshot=False):
        """
        Ekranı yakala ve bearing değerini oku
        
        Args:
            save_screenshot: True ise yakalanan görüntüyü kaydet
        
        Returns:
            float: Okunan bearing değeri
        """
        # Ekranı yakala
        screenshot_path = "bearing_capture.png" if save_screenshot else None
        img = self.capture_screen(screenshot_path)
        
        # Değeri oku
        value = self.extract_bearing_value(img)
        
        if value is not None:
            myOwnPrint(f"✓ Bearing: {value}°")
            return value
        else:
            myOwnPrint("✗ Okuma başarısız!")
            return None
    
    def continuous_reading(self, interval=0.5):
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
                myOwnPrint("-" * 40)
                time.sleep(interval)
        except KeyboardInterrupt:
            myOwnPrint("\nOkuma durduruldu.")


# KULLANIM
if __name__ == "__main__":
    
    # Bearing bölgesi koordinatları (config.py'den)
    LEFT = config.BEARING_LEFT
    TOP = config.BEARING_TOP
    WIDTH = config.BEARING_WIDTH
    HEIGHT = config.BEARING_HEIGHT
    
    # Reader oluştur
    reader = BearingReader(LEFT, TOP, WIDTH, HEIGHT)
    
    myOwnPrint("="*50)
    myOwnPrint("BEARING OKUYUCU")
    myOwnPrint("="*50)
    
    time.sleep(2)  # Başlamadan önce kısa bekleme
    # TEK OKUMA - Görüntüyü kaydet ve değeri oku
    myOwnPrint("\nBearing değeri okunuyor...")
    value = reader.read(save_screenshot=True)
    
    if value:
        myOwnPrint(f"\n✓ Başarılı! Bearing: {value}°")
    else:
        myOwnPrint("\n✗ Okuma başarısız!")
        myOwnPrint("bearing_capture.png dosyasını kontrol edin")
    
    # SÜREKLİ OKUMA (İstenirse)
    # Aşağıdaki satırın yorumunu kaldır
    # reader.continuous_reading(interval=0.5)
    
    myOwnPrint("\n" + "="*50)
    myOwnPrint("KULLANIM:")
    myOwnPrint("="*50)
    myOwnPrint("Tek okuma:")
    myOwnPrint("  value = reader.read(save_screenshot=True)")
    myOwnPrint("\nSürekli okuma:")
    myOwnPrint("  reader.continuous_reading(interval=0.5)")
    myOwnPrint("="*50)