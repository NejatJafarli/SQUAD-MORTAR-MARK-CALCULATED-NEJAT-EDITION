import re
import time
import ctypes
import pyautogui
import pytesseract

# ====== AYARLAR ======
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_LANG = "eng"

# Bar'ın ekrandaki oranları (çözünürlükten bağımsız)
REL_REGION = (0.25, 0.00, 0.50, 0.06)


def get_region_pixels():
    w, h = pyautogui.size()
    left = int(w * REL_REGION[0])
    top = int(h * REL_REGION[1])
    width = int(w * REL_REGION[2])
    height = int(h * REL_REGION[3])
    return (left, top, width, height)


def is_capslock_on():
    return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)


def capture_bar_text():
    region_pixels = get_region_pixels()
    screenshot = pyautogui.screenshot(region=region_pixels)
    text = pytesseract.image_to_string(screenshot, lang=OCR_LANG)
    return text


def parse_coordinates(text):
    """
    Dil fark etmeksizin şu pattern'i arar:
        G7 - 9 - 2
    İlk bulunan -> Player
    İkinci bulunan -> Marked (yoksa None)
    """
    pattern = re.compile(r"([A-Z]\d)\s*-\s*(\d+)\s*-\s*(\d+)", re.IGNORECASE)

    matches = pattern.findall(text)

    if not matches:
        return None, None

    # İlk koordinat Player
    pl = matches[0]
    player = {
        "grid": pl[0],
        "y": int(pl[1]),
        "z": int(pl[2])
    }

    marked = None
    if len(matches) > 1:
        mk = matches[1]
        marked = {
            "grid": mk[0],
            "y": int(mk[1]),
            "z": int(mk[2])
        }

    return player, marked


def main():
    print("Dil bağımsız koordinat okuma sistemi çalışıyor.")
    print("CapsLock AÇIKKEN OCR okunur.\n")

    last_player = None
    last_marked = None
    last_caps = None

    while True:
        caps = is_capslock_on()

        if caps != last_caps:
            last_caps = caps
            print(f"CapsLock {'AÇIK' if caps else 'KAPALI'}")

        if caps:
            raw = capture_bar_text()
            player, marked = parse_coordinates(raw)

            if player:
                last_player = player
                if marked:
                    last_marked = marked

                print("\nYeni okunan:")
                print("Player:", player)
                if marked:
                    print("Marked:", marked)
                else:
                    print("Marked yok (tek koordinat bulundu).")
            else:
                print("\nKoordinat bulunamadı.")

            print("\nEn son kayıtlı değerler:")
            print("LAST Player:", last_player)
            print("LAST Marked:", last_marked)

            time.sleep(0.5)
        else:
            time.sleep(0.2)


if __name__ == "__main__":
    main()