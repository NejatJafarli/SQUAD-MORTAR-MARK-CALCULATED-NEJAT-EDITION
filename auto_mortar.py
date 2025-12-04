import sys
import re
import cv2
import numpy as np
import mss
import pytesseract
import os
import keyboard
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer, Qt, QObject, pyqtSignal, QThread
from PyQt5.QtGui import QFont

# Set the path to Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Replace with your path

os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (
    '--disable-background-timer-throttling '
    '--disable-renderer-backgrounding '
    '--disable-backgrounding-occluded-windows'
)

#####################################
# Utility Functions
#####################################
def is_coord_full(coord):
    if coord is None or coord == "Unknown":
        return False
    parts = coord.split('-')
    return len(parts) == 5

#####################################
# OCR and Formatting Functions
#####################################
def capture_ocr_region(left, top, width, height, debug=False):
    try:
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = sct.grab(monitor)
            img_pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            if debug:
                img_pil.save("capture_debug_ocr.png")
            # Image preprocessing
            img_gray = img_pil.convert('L')  # Convert to grayscale
            img_thresh = img_gray.point(lambda x: 0 if x < 128 else 255, '1')  # Binary thresholding
            if debug:
                img_thresh.save("capture_debug_ocr_preprocessed.png")
            # Use psm 6 for a text block organized in lines
            text = pytesseract.image_to_string(img_thresh, config='--psm 6')
            print(f"OCR text captured: {text}")  # Detailed log
            return text.strip()
    except Exception as e:
        print(f"Error during OCR capture: {e}")
        return ""

def format_coordinate(coord_text):


    # Adjust regex to capture different variations
    pattern = r"([A-Z])\s*(\d+)\s*[-–]\s*(\d+)\s*[-–]\s*(\d+)"
    match = re.search(pattern, coord_text)
    if match:
        letter = match.group(1).strip()
        main_num = match.group(2).zfill(2)  # Ensure two digits
        sub_num1 = match.group(3)
        sub_num2 = match.group(4)
        final_coord = f"{letter}{main_num}-{sub_num1}-{sub_num2}"
        print(f"Formatted coordinate: {final_coord}")  # Detailed log
        return final_coord
    print(f"Unformatted coordinate: {coord_text}")  # Detailed log
    return None

#####################################
# Capture and Color Detection Functions
#####################################
def capture_region(left, top, width, height, debug=False):
    try:
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = sct.grab(monitor)
            frame = np.array(img)[:, :, :3]
            frame = frame.astype(np.uint8)
            frame = np.ascontiguousarray(frame)
            if debug:
                cv2.imwrite("region_debug.png", frame)
            return frame
    except Exception as e:
        print(f"Error during region capture: {e}")
        return None

def detect_specific_color(scene_img, target_rgb=(241,243,4), tolerance=20):
    try:
        target_bgr = (target_rgb[2], target_rgb[1], target_rgb[0])
        low_color = np.array([
            max(0, target_bgr[0] - tolerance),
            max(0, target_bgr[1] - tolerance),
            max(0, target_bgr[2] - tolerance)
        ], dtype=np.uint8)
        high_color = np.array([
            min(255, target_bgr[0] + tolerance),
            min(255, target_bgr[1] + tolerance),
            min(255, target_bgr[2] + tolerance)
        ], dtype=np.uint8)
        mask = cv2.inRange(scene_img, low_color, high_color)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        if area < 50:
            return None
        M = cv2.moments(largest_contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            return (cx, cy)
        else:
            return None
    except Exception as e:
        print(f"Error during specific color detection: {e}")
        return None

def detect_color(scene_img, target_rgb, tolerance=10):
    try:
        target_bgr = (target_rgb[2], target_rgb[1], target_rgb[0])
        low_color = np.array([
            max(0, target_bgr[0] - tolerance),
            max(0, target_bgr[1] - tolerance),
            max(0, target_bgr[2] - tolerance)
        ], dtype=np.uint8)
        high_color = np.array([
            min(255, target_bgr[0] + tolerance),
            min(255, target_bgr[1] + tolerance),
            min(255, target_bgr[2] + tolerance)
        ], dtype=np.uint8)
        mask = cv2.inRange(scene_img, low_color, high_color)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        if area < 50:
            return None
        M = cv2.moments(largest_contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            return (cx, cy)
        return None
    except Exception as e:
        print(f"Error during color detection: {e}")
        return None

#####################################
# Grid Line Detection and Subdivision
#####################################
def detect_grid_lines(scene_img):
    try:
        gray = cv2.cvtColor(scene_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
        line_coordinates = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if (abs(angle) < 5) or (abs(angle - 90) < 5) or (abs(angle + 90) < 5):
                    line_coordinates.append((x1, y1, x2, y2))
        # Verify that captured lines cover the entire grid
        print(f"Lines detected: {len(line_coordinates)}")  # Detailed log
        return line_coordinates
    except Exception as e:
        print(f"Error during grid line detection: {e}")
        return []

def crop_to_case(scene_img, grid_lines, marker_coords):
    try:
        horizontal_lines = sorted([line for line in grid_lines if line[1] == line[3]], key=lambda l: l[1])
        vertical_lines = sorted([line for line in grid_lines if line[0] == line[2]], key=lambda l: l[0])
        marker_x, marker_y = marker_coords
        case_left = case_right = case_top = case_bottom = None
        for i in range(len(vertical_lines) - 1):
            if vertical_lines[i][0] <= marker_x < vertical_lines[i + 1][0]:
                case_left = vertical_lines[i][0]
                case_right = vertical_lines[i + 1][0]
                break
        for i in range(len(horizontal_lines) - 1):
            if horizontal_lines[i][1] <= marker_y < horizontal_lines[i + 1][1]:
                case_top = horizontal_lines[i][1]
                case_bottom = horizontal_lines[i + 1][1]
                break
        if case_left is not None and case_right is not None and case_top is not None and case_bottom is not None:
            cropped_img = scene_img[case_top:case_bottom, case_left:case_right]
            new_marker_x = marker_x - case_left
            new_marker_y = marker_y - case_top
            return cropped_img, (new_marker_x, new_marker_y)
        else:
            print("Cropping failed: case coordinates not found.")  # Detailed log
            return None, None
    except Exception as e:
        print(f"Error during case cropping: {e}")
        return None, None

def subdivide_and_find_green(cropped_img, target_rgb, step):
    try:
        h, w, _ = cropped_img.shape
        sub_width = w // 3
        sub_height = h // 3
        max_green_percentage = 0
        selected_subcase = -1
        selected_sub_img = None
        for i in range(3):
            for j in range(3):
                x_start = j * sub_width
                y_start = i * sub_height
                sub_img = cropped_img[y_start:y_start + sub_height, x_start:x_start + sub_width]
                mask = cv2.inRange(
                    sub_img,
                    np.array([target_rgb[2] - 10, target_rgb[1] - 10, target_rgb[0] - 10]),
                    np.array([target_rgb[2] + 10, target_rgb[1] + 10, target_rgb[0] + 10])
                )
                green_percentage = (cv2.countNonZero(mask) / (sub_width * sub_height)) * 100
                case_number = 7 + j - i*3
                if green_percentage > max_green_percentage:
                    max_green_percentage = green_percentage
                    selected_subcase = case_number
                    selected_sub_img = sub_img
        for i in range(1, 3):
            cv2.line(cropped_img, (i * sub_width, 0), (i * sub_width, h), (255, 0, 0), 2)
            cv2.line(cropped_img, (0, i * sub_height), (w, i * sub_height), (255, 0, 0), 2)
        cv2.imwrite(f"subdivided_step_{step}.png", cropped_img)
        print(f"Selected subcase: {selected_subcase} with {max_green_percentage:.2f}% green.")  # Detailed log
        return selected_subcase, selected_sub_img
    except Exception as e:
        print(f"Error during subdivision and green detection: {e}")
        return -1, None

def subdivide_case_and_find_green(cropped_img, target_rgb):
    try:
        first_subcase, first_sub_img = subdivide_and_find_green(cropped_img, target_rgb, step=1)
        if first_sub_img is None:
            return None, None
        second_subcase, _ = subdivide_and_find_green(first_sub_img, target_rgb, step=2)
        return first_subcase, second_subcase
    except Exception as e:
        print(f"Error during case subdivision: {e}")
        return None, None

#####################################
# Parameters and Global Variables
#####################################
ocr_left, ocr_top = 720, 30
ocr_width, ocr_height = 550, 55
scene_left, scene_top = 700, 120
scene_width, scene_height = 1800, 1300
internal_marker_coords = (150, 150)
player_detection_active = False
marker_detection_active = False
last_player_coord = "A00-0-0"  # Initialize with default value
last_marker_coord = "A00-0-0"  # Initialize with default value
update_interval = 0.2
main_window = None
overlay_visible = True

#####################################
# Detection Workers
#####################################
class PlayerDetectionWorker(QObject):
    player_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        global last_player_coord
        while self.running:
            ocr_result = capture_ocr_region(ocr_left, ocr_top, ocr_width, ocr_height, debug=True)
            player_pattern = r"Player Position:\s*([A-Z]\d+\s*[-–]\s*\d+\s*[-–]\s*\d+)"
            player_match = re.search(player_pattern, ocr_result)
            if player_match:
                base_coord = format_coordinate(player_match.group(1))
            else:
                if last_player_coord != "Unknown":
                    base_coord = '-'.join(last_player_coord.split('-')[:3])
                else:
                    base_coord = "A00-00-00"  # Default value
            scene_img = capture_region(scene_left, scene_top, scene_width, scene_height, debug=False)
            if scene_img is None:
                continue
            player_pos = detect_specific_color(scene_img, (241,243,4), 20)
            if player_pos is not None and base_coord is not None:
                x, y = player_pos
                half_size = 150
                h, w, _ = scene_img.shape
                x_start = max(0, x - half_size)
                x_end = min(w, x + half_size)
                y_start = max(0, y - half_size)
                y_end = min(h, y + half_size)
                cropped = scene_img[y_start:y_end, x_start:x_end]
                icon_img = cropped.copy()
                if icon_img is not None:
                    grid_lines = detect_grid_lines(icon_img)
                    if grid_lines:
                        cropped_case_img, new_marker_coords = crop_to_case(icon_img, grid_lines, internal_marker_coords)
                        if cropped_case_img is not None:
                            player_first_subcase, player_second_subcase = subdivide_case_and_find_green(cropped_case_img, (241,243,4))
                            if player_first_subcase and player_second_subcase:
                                temp_coord = f"{base_coord}-{player_first_subcase}-{player_second_subcase}"
                                if is_coord_full(temp_coord):
                                    last_player_coord = temp_coord
                                    print(f"Player coordinate updated: {last_player_coord}")  # Detailed log
                                    self.player_updated.emit(last_player_coord)
                            else:
                                if is_coord_full(base_coord):
                                    last_player_coord = base_coord
                                    print(f"Player coordinate updated with base_coord: {last_player_coord}")  # Detailed log
                                    self.player_updated.emit(last_player_coord)
                        else:
                            if is_coord_full(base_coord):
                                last_player_coord = base_coord
                                print(f"Player coordinate updated with base_coord (cropped_case_img None): {last_player_coord}")  # Detailed log
                                self.player_updated.emit(last_player_coord)
                    else:
                        if is_coord_full(base_coord):
                            last_player_coord = base_coord
                            print(f"Player coordinate updated with base_coord (grid_lines None): {last_player_coord}")  # Detailed log
                            self.player_updated.emit(last_player_coord)
                else:
                    if is_coord_full(base_coord):
                        last_player_coord = base_coord
                        print(f"Player coordinate updated with base_coord (icon_img None): {last_player_coord}")  # Detailed log
                        self.player_updated.emit(last_player_coord)
            else:
                if base_coord is not None and is_coord_full(base_coord):
                    last_player_coord = base_coord
                    print(f"Player coordinate updated with base_coord (player_pos None): {last_player_coord}")  # Detailed log
                    self.player_updated.emit(last_player_coord)
            QThread.msleep(int(update_interval * 1000))  # Pause between updates

    def stop(self):
        self.running = False

class MarkerDetectionWorker(QObject):
    marker_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        global last_marker_coord
        while self.running:
            ocr_result = capture_ocr_region(ocr_left, ocr_top, ocr_width, ocr_height, debug=True)
            marker_pattern = r"Marked Position:\s*([A-Z]\d+\s*[-–]\s*\d+\s*[-–]\s*\d+)"
            marker_match = re.search(marker_pattern, ocr_result)
            if marker_match:
                base_coord = format_coordinate(marker_match.group(1))
            else:
                if last_marker_coord != "Unknown":
                    base_coord = '-'.join(last_marker_coord.split('-')[:3])
                else:
                    base_coord = "A00-00-00"  # Default value
            scene_img = capture_region(scene_left, scene_top, scene_width, scene_height, debug=False)
            if scene_img is None:
                continue
            marker_pos = detect_color(scene_img, (124,233,68), tolerance=25)
            if marker_pos is not None and base_coord is not None:
                x, y = marker_pos
                half_size = 150
                h, w, _ = scene_img.shape
                x_start = max(0, x - half_size)
                x_end = min(w, x + half_size)
                y_start = max(0, y - half_size)
                y_end = min(h, y + half_size)
                cropped = scene_img[y_start:y_end, x_start:x_end]
                marker_img = cropped.copy()
                if marker_img is not None:
                    grid_lines = detect_grid_lines(marker_img)
                    if grid_lines:
                        cropped_case_img, new_marker_coords = crop_to_case(marker_img, grid_lines, internal_marker_coords)
                        if cropped_case_img is not None:
                            marker_first_subcase, marker_second_subcase = subdivide_case_and_find_green(cropped_case_img, (124,233,68))
                            if marker_first_subcase and marker_second_subcase:
                                temp_coord = f"{base_coord}-{marker_first_subcase}-{marker_second_subcase}"
                                if is_coord_full(temp_coord):
                                    last_marker_coord = temp_coord
                                    print(f"Marker coordinate updated: {last_marker_coord}")  # Detailed log
                                    self.marker_updated.emit(last_marker_coord)
                            else:
                                if is_coord_full(base_coord):
                                    last_marker_coord = base_coord
                                    print(f"Marker coordinate updated with base_coord: {last_marker_coord}")  # Detailed log
                                    self.marker_updated.emit(last_marker_coord)
                        else:
                            if is_coord_full(base_coord):
                                last_marker_coord = base_coord
                                print(f"Marker coordinate updated with base_coord (cropped_case_img None): {last_marker_coord}")  # Detailed log
                                self.marker_updated.emit(last_marker_coord)
                    else:
                        if is_coord_full(base_coord):
                            last_marker_coord = base_coord
                            print(f"Marker coordinate updated with base_coord (grid_lines None): {last_marker_coord}")  # Detailed log
                            self.marker_updated.emit(last_marker_coord)
                else:
                    if is_coord_full(base_coord):
                        last_marker_coord = base_coord
                        print(f"Marker coordinate updated with base_coord (marker_img None): {last_marker_coord}")  # Detailed log
                        self.marker_updated.emit(last_marker_coord)
            else:
                if base_coord is not None and is_coord_full(base_coord):
                    last_marker_coord = base_coord
                    print(f"Marker coordinate updated with base_coord (marker_pos None): {last_marker_coord}")  # Detailed log
                    self.marker_updated.emit(last_marker_coord)
            QThread.msleep(int(update_interval * 1000))  # Pause between updates

    def stop(self):
        self.running = False

#####################################
# Overlay Window
#####################################
class OverlayWindow(QWidget):
    def __init__(self, scale_factor=1.0):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.label = QLabel("Elevation: ???", self)
        font = QFont("Arial", int(30 * scale_factor), QFont.Bold)
        self.label.setFont(font)
        self.label.setStyleSheet("color: white;")
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.resize(int(250 * scale_factor), int(75 * scale_factor))
        self.move(int(380 * scale_factor), int(650 * scale_factor))

    def update_elevation(self, elevation):
        self.label.setText(f"Elevation: {elevation}")

#####################################
# Main Class
#####################################
class MainWindow(QMainWindow):
    def __init__(self, scale_factor=1.0):
        super().__init__()
        self.setWindowTitle("Detection Interface")
        base_width = int(1200 * scale_factor)
        base_height = int(800 * scale_factor)
        self.setGeometry(100, 100, base_width, base_height)
        self.overlay = OverlayWindow(scale_factor)
        self.overlay.show()
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        control_layout = QVBoxLayout()

        self.player_label = QLabel("Player Position:")
        control_layout.addWidget(self.player_label)

        self.player_entry = QLineEdit()
        self.player_entry.setText(last_player_coord)
        control_layout.addWidget(self.player_entry)

        self.marker_label = QLabel("Marker Position:")
        control_layout.addWidget(self.marker_label)

        self.marker_entry = QLineEdit()
        self.marker_entry.setText(last_marker_coord)
        control_layout.addWidget(self.marker_entry)

        self.player_state_label = QLabel("Player Detection: Inactive")
        control_layout.addWidget(self.player_state_label)

        self.marker_state_label = QLabel("Marker Detection: Inactive")
        control_layout.addWidget(self.marker_state_label)

        self.toggle_player_button = QPushButton("Toggle Player Detection")
        self.toggle_player_button.clicked.connect(self.local_toggle_player)
        control_layout.addWidget(self.toggle_player_button)

        self.toggle_marker_button = QPushButton("Toggle Marker Detection")
        self.toggle_marker_button.clicked.connect(self.local_toggle_marker)
        control_layout.addWidget(self.toggle_marker_button)

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://squadcalc.app"))
        
        # Wait for page to load before running JavaScript
        self.page_loaded = False
        self.browser.loadFinished.connect(self.on_page_loaded)
        
        main_layout.addLayout(control_layout, 1)
        main_layout.addWidget(self.browser, 3)
        self.setCentralWidget(central_widget)

        # Worker and thread configuration
        self.player_thread = None
        self.marker_thread = None
        self.player_worker = None
        self.marker_worker = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_elevation)
        self.timer.start(int(update_interval * 1000))

    def on_page_loaded(self, success):
        """Called when the web page finishes loading"""
        if success:
            self.page_loaded = True
            print("Web page loaded successfully.")
        else:
            print("Web page failed to load.")

    def local_toggle_player(self):
        global player_detection_active
        player_detection_active = not player_detection_active
        if player_detection_active:
            self.start_player_detection()
        else:
            self.stop_player_detection()
        self.update_state_labels()

    def local_toggle_marker(self):
        global marker_detection_active
        marker_detection_active = not marker_detection_active
        if marker_detection_active:
            self.start_marker_detection()
        else:
            self.stop_marker_detection()
        self.update_state_labels()

    def start_player_detection(self):
        if self.player_thread is None:
            self.player_worker = PlayerDetectionWorker()
            self.player_thread = QThread()
            self.player_worker.moveToThread(self.player_thread)
            self.player_thread.started.connect(self.player_worker.run)
            self.player_worker.player_updated.connect(self.update_player_coord)
            self.player_thread.start()
            print("Player detection thread started.")

    def stop_player_detection(self):
        if self.player_worker:
            self.player_worker.stop()
            self.player_thread.quit()
            self.player_thread.wait()
            self.player_worker = None
            self.player_thread = None
            print("Player detection thread stopped.")

    def start_marker_detection(self):
        if self.marker_thread is None:
            self.marker_worker = MarkerDetectionWorker()
            self.marker_thread = QThread()
            self.marker_worker.moveToThread(self.marker_thread)
            self.marker_thread.started.connect(self.marker_worker.run)
            self.marker_worker.marker_updated.connect(self.update_marker_coord)
            self.marker_thread.start()
            print("Marker detection thread started.")

    def stop_marker_detection(self):
        if self.marker_worker:
            self.marker_worker.stop()
            self.marker_thread.quit()
            self.marker_thread.wait()
            self.marker_worker = None
            self.marker_thread = None
            print("Marker detection thread stopped.")

    def update_player_coord(self, coord):
        global last_player_coord
        last_player_coord = coord
        self.player_entry.setText(coord)
        self.update_coordinates_on_web(last_player_coord, last_marker_coord)

    def update_marker_coord(self, coord):
        global last_marker_coord
        last_marker_coord = coord
        self.marker_entry.setText(coord)
        self.update_coordinates_on_web(last_player_coord, last_marker_coord)

    def update_state_labels(self):
        if player_detection_active:
            self.player_state_label.setText("Player Detection: Active")
        else:
            self.player_state_label.setText("Player Detection: Inactive")
        if marker_detection_active:
            self.marker_state_label.setText("Marker Detection: Active")
        else:
            self.marker_state_label.setText("Marker Detection: Inactive")

    def update_coordinates_on_web(self, player_coord, marker_coord):
        # Only run JavaScript if page is loaded
        if not self.page_loaded:
            return
            
        if is_coord_full(player_coord) and is_coord_full(marker_coord):
            # Escape characters for safe JavaScript string
            player_coord_safe = player_coord.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            marker_coord_safe = marker_coord.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            
            js_code = """
            (function() {
                try {
                    var playerInput = document.querySelector('#mortar-location');
                    var markerInput = document.querySelector('#target-location');
                    if (playerInput && markerInput) {
                        playerInput.value = '""" + player_coord_safe + """';
                        markerInput.value = '""" + marker_coord_safe + """';
                        var event = new Event('input', {bubbles: true});
                        playerInput.dispatchEvent(event);
                        markerInput.dispatchEvent(event);
                    }
                } catch(e) {
                    console.error('Error updating coordinates:', e);
                }
            })();
            """
            self.browser.page().runJavaScript(js_code)

    def fetch_elevation(self):
        # Only run JavaScript if page is loaded
        if not self.page_loaded:
            return
            
        js_code = """
        (function() {
            try {
                var elevElem = document.querySelector('#elevationNum');
                if (elevElem) {
                    return elevElem.innerText;
                } else {
                    return "???";
                }
            } catch(e) {
                console.error('Error fetching elevation:', e);
                return "???";
            }
        })();
        """
        self.browser.page().runJavaScript(js_code, self.handle_elevation_result)

    def handle_elevation_result(self, result):
        if result is None or result.strip() == "":
            result = "???"
        self.overlay.update_elevation(result)

    def closeEvent(self, event):
        # Stop threads when closing the application
        self.stop_player_detection()
        self.stop_marker_detection()
        event.accept()

#####################################
# Toggle Overlay
#####################################
def toggle_overlay():
    global main_window, overlay_visible
    print("Delete key pressed.")
    if main_window and main_window.overlay:
        print(f"Current overlay_visible state: {overlay_visible}")
        if overlay_visible:
            main_window.overlay.hide()
            overlay_visible = False
            print("Overlay disabled.")
        else:
            main_window.overlay.show()
            overlay_visible = True
            print("Overlay enabled.")
    else:
        print("main_window or overlay not defined.")

#####################################
# Execution
#####################################
if __name__ == '__main__':
    import time  # Import added for initial delay

    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    rect = screen.availableGeometry()
    screen_width = rect.width()
    screen_height = rect.height()

    scale_factor = 1.0
    if screen_width >= 3840 and screen_height >= 2160:
        scale_factor = 2.0
    elif screen_width >= 2560 and screen_height >= 1440:
        scale_factor = 1.33
    # Otherwise Full HD, scale_factor = 1.0

    # Create and assign global MainWindow after a delay to ensure everything is loaded
    main_window = MainWindow(scale_factor=scale_factor)

    # Add keybinds after main_window is assigned
    keyboard.add_hotkey('home', main_window.local_toggle_player)
    keyboard.add_hotkey('end', main_window.local_toggle_marker)
    keyboard.add_hotkey('delete', toggle_overlay)

    # Optional: Add a delay before starting to ensure the interface is ready
    # time.sleep(5)  # Uncomment if necessary

    main_window.show()
    sys.exit(app.exec_())
