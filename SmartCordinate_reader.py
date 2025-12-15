"""
SQUAD Coordinate Reader
Reads player and marker coordinates from the game screen and saves to JSON
"""

import re
import cv2
import numpy as np
import mss
import pytesseract
import json
import time
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image
import threading
from pynput import keyboard
from collections import defaultdict

# Configure Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

#####################################
# Configuration
#####################################
# OCR region (top-left text area)
OCR_LEFT, OCR_TOP = 720, 30
OCR_WIDTH, OCR_HEIGHT = 550, 55

# Map capture region
SCENE_LEFT, SCENE_TOP = 700, 120
SCENE_WIDTH, SCENE_HEIGHT = 1800, 1300

# Internal marker position (center of cropped area)
INTERNAL_MARKER_COORDS = (150, 150)

# Grid cell size (piksel)
CELL_SIZE = 145

# Colors to detect
PLAYER_COLOR_RGB = (217, 217, 0)    # Yellow player icon
PLAYER_TOLERANCE = 30                # Higher tolerance for yellow
MARKER_COLOR_RGB = (73, 182, 23)    # Green marker
MARKER_TOLERANCE = 50                # Higher tolerance for marker detection

# Update interval (seconds)
UPDATE_INTERVAL = 1.0

# Output file
OUTPUT_FILE = "coordinates.json"
FIRING_SOLUTION_FILE = "firing_solution.json"

# Last known coordinates (cached)
last_known_coords = {
    "player_base": None,
    "player_full": None,
    "marker_base": None,
    "marker_full": None
}

# Player lock state
player_locked = False
locked_player_coord = None

# Marker lock state
marker_locked = False
locked_marker_coord = None

#####################################
# OCR Functions
#####################################
def capture_ocr_region(left, top, width, height):
    """Capture and read text from screen region using OCR"""
    try:
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = sct.grab(monitor)
            img_pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            
            # Preprocess image for better OCR
            img_gray = img_pil.convert('L')
            img_thresh = img_gray.point(lambda x: 0 if x < 128 else 255, '1')
            
            # Run OCR
            text = pytesseract.image_to_string(img_thresh, config='--psm 6')
            return text.strip()
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""


def format_coordinate(coord_text):
    """Format coordinate string to standard format (e.g., G07-8-7)"""
    pattern = r"([A-Z])\s*(\d+)\s*[-–]\s*(\d+)\s*[-–]\s*(\d+)"
    match = re.search(pattern, coord_text)
    
    if match:
        letter = match.group(1).strip()
        main_num = match.group(2).zfill(2)  # Ensure two digits
        sub_num1 = match.group(3)
        sub_num2 = match.group(4)
        return f"{letter}{main_num}-{sub_num1}-{sub_num2}"
    
    return None


#####################################
# Image Processing Functions
#####################################
def capture_screen_region(left, top, width, height):
    """Capture a region of the screen"""
    try:
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            img = sct.grab(monitor)
            frame = np.array(img)[:, :, :3]
            frame = frame.astype(np.uint8)
            frame = np.ascontiguousarray(frame)
            return frame
    except Exception as e:
        print(f"Screen capture error: {e}")
        return None


def detect_color_position(image, target_rgb, tolerance=20, debug_name=""):
    """
    Detect the position of a specific color in an image
    Returns (x, y) coordinates or None if not found
    """
    try:
        # Convert RGB to BGR for OpenCV
        target_bgr = (target_rgb[2], target_rgb[1], target_rgb[0])
        
        # Create color range
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
        
        # Create mask and find contours
        mask = cv2.inRange(image, low_color, high_color)
        
        # Save mask for debugging
        if debug_name:
            cv2.imwrite(f"debug_{debug_name}_mask.png", mask)
        
        # More aggressive morphology for small icons
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            print(f"    No contours found for {debug_name}")
            return None
        
        # Get largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        print(f"    Largest contour area: {area:.0f} pixels")
        
        # Lower threshold for small icons
        if area < 20:
            print(f"    Area too small: {area}")
            return None
        
        # Calculate center
        M = cv2.moments(largest_contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Draw contour on debug image
            if debug_name:
                debug_img = image.copy()
                cv2.drawContours(debug_img, [largest_contour], -1, (0, 255, 0), 2)
                cv2.circle(debug_img, (cx, cy), 5, (0, 0, 255), -1)
                cv2.imwrite(f"debug_{debug_name}_contour.png", debug_img)
            
            return (cx, cy)
        
        return None
    
    except Exception as e:
        print(f"Color detection error: {e}")
        return None


#####################################
# SMART GRID DETECTION
#####################################
def find_closest_line(lines, marker_coord, orientation='horizontal', direction='before'):
    """
    Marker'a en yakın çizgiyi bul
    
    orientation: 'horizontal' (yatay) veya 'vertical' (dikey)
    direction: 'before' (üstte/solda) veya 'after' (altta/sağda)
    """
    if not lines:
        return None
    
    if orientation == 'horizontal':
        # Yatay çizgiler - Y koordinatına bak
        line_positions = [(l, l[1]) for l in lines]
        marker_pos = marker_coord[1]  # marker_y
    else:
        # Dikey çizgiler - X koordinatına bak
        line_positions = [(l, l[0]) for l in lines]
        marker_pos = marker_coord[0]  # marker_x
    
    # Direction'a göre filtrele
    if direction == 'before':
        # Marker'dan önce (üstte veya solda)
        candidates = [(l, pos) for l, pos in line_positions if pos < marker_pos]
        if not candidates:
            return None
        # En yakını bul (max)
        return max(candidates, key=lambda x: x[1])[0]
    else:
        # Marker'dan sonra (altta veya sağda)
        candidates = [(l, pos) for l, pos in line_positions if pos >= marker_pos]
        if not candidates:
            return None
        # En yakını bul (min)
        return min(candidates, key=lambda x: x[1])[0]


def merge_close_lines(lines, orientation, threshold=10):
    """Yakın çizgileri birleştir"""
    if not lines:
        return []
    
    coord_idx = 1 if orientation == 'horizontal' else 0
    sorted_lines = sorted(lines, key=lambda l: l[coord_idx])
    
    merged = []
    current_group = [sorted_lines[0]]
    
    for i in range(1, len(sorted_lines)):
        current_coord = sorted_lines[i][coord_idx]
        prev_coord = current_group[-1][coord_idx]
        
        if abs(current_coord - prev_coord) <= threshold:
            current_group.append(sorted_lines[i])
        else:
            avg_line = average_lines(current_group, orientation)
            merged.append(avg_line)
            current_group = [sorted_lines[i]]
    
    if current_group:
        avg_line = average_lines(current_group, orientation)
        merged.append(avg_line)
    
    return merged


def average_lines(lines, orientation):
    """Çizgi grubunun ortalaması"""
    if orientation == 'horizontal':
        avg_y = int(np.mean([l[1] for l in lines]))
        return (lines[0][0], avg_y, lines[0][2], avg_y)
    else:
        avg_x = int(np.mean([l[0] for l in lines]))
        return (avg_x, lines[0][1], avg_x, lines[0][3])


def detect_grid_lines_smart(image, marker_coords, cell_size=145, debug=True):
    """
    Akıllı grid algılama - Sadece 2 çizgi bul, diğer 2'sini oluştur
    
    marker_coords: (x, y) tuple
    cell_size: Hücre boyutu (piksel) - varsayılan 145
    """
    try:
        h, w = image.shape[:2]
        marker_x, marker_y = marker_coords
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Preprocessing
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        
        # Otsu thresholding
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological operations - çizgileri güçlendir
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25))
        
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)
        
        grid_structure = cv2.add(horizontal, vertical)
        edges = cv2.Canny(grid_structure, 50, 150, apertureSize=3)
        
        if debug:
            cv2.imwrite("debug_01_edges.png", edges)
        
        # Hough Line Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi/180,
            threshold=50,
            minLineLength=min(h, w) // 10,
            maxLineGap=20
        )
        
        if lines is None:
            print("    ❌ Hiç çizgi algılanamadı!")
            return None
        
        print(f"    🔍 Ham çizgi sayısı: {len(lines)}")
        
        # Çizgileri kategorize et
        horizontal_lines = []
        vertical_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(abs(y2 - y1), abs(x2 - x1)))
            
            if angle < 10:  # Horizontal
                y_avg = (y1 + y2) // 2
                horizontal_lines.append((0, y_avg, w, y_avg))
            elif angle > 80:  # Vertical
                x_avg = (x1 + x2) // 2
                vertical_lines.append((x_avg, 0, x_avg, h))
        
        # Yakın çizgileri birleştir
        horizontal_lines = merge_close_lines(horizontal_lines, 'horizontal', threshold=10)
        vertical_lines = merge_close_lines(vertical_lines, 'vertical', threshold=10)
        
        print(f"    📏 Yatay çizgiler: {len(horizontal_lines)}")
        print(f"    📏 Dikey çizgiler: {len(vertical_lines)}")
        print(f"    📍 Marker: ({marker_x}, {marker_y})")
        
        # 1️⃣ MARKER'IN KUZEYINDE (ÜSTÜNDE) YATAY ÇİZGİ BUL
        top_line = find_closest_line(horizontal_lines, marker_coords, 'horizontal', 'before')
        
        # 2️⃣ MARKER'IN SAĞINDA DİKEY ÇİZGİ BUL  
        right_line = find_closest_line(vertical_lines, marker_coords, 'vertical', 'after')
        
        if top_line is None or right_line is None:
            print("    ❌ Üst veya sağ çizgi bulunamadı!")
            print(f"       Üst çizgi: {top_line}")
            print(f"       Sağ çizgi: {right_line}")
            return None
        
        top_y = top_line[1]
        right_x = right_line[0]
        
        print(f"    ✅ Üst çizgi Y: {top_y}")
        print(f"    ✅ Sağ çizgi X: {right_x}")
        
        # 3️⃣ DİĞER 2 ÇİZGİYİ SABİT MESAFE İLE OLUŞTUR
        bottom_y = top_y + cell_size
        left_x = right_x - cell_size
        
        print(f"    🔨 Alt çizgi Y: {bottom_y} (üst + {cell_size})")
        print(f"    🔨 Sol çizgi X: {left_x} (sağ - {cell_size})")
        
        # 4 çizgiyi döndür
        cell_lines = {
            'top': (0, top_y, w, top_y),
            'bottom': (0, bottom_y, w, bottom_y),
            'left': (left_x, 0, left_x, h),
            'right': (right_x, 0, right_x, h)
        }
        
        # Debug görseli
        if debug:
            debug_img = image.copy()
            cv2.line(debug_img, (0, top_y), (w, top_y), (0, 255, 0), 2)  # Yeşil - üst (gerçek)
            cv2.line(debug_img, (0, bottom_y), (w, bottom_y), (255, 0, 255), 2)  # Mor - alt (sanal)
            cv2.line(debug_img, (left_x, 0), (left_x, h), (255, 0, 255), 2)  # Mor - sol (sanal)
            cv2.line(debug_img, (right_x, 0), (right_x, h), (0, 255, 0), 2)  # Yeşil - sağ (gerçek)
            cv2.circle(debug_img, (marker_x, marker_y), 10, (0, 0, 255), -1)
            
            cv2.imwrite("debug_02_cell_boundaries.png", debug_img)
        
        return cell_lines
    
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        return None


def crop_to_cell(image, cell_lines, marker_coords, padding=5, debug=True):
    """
    Bulunan hücreyi kırp
    
    cell_lines: dict with 'top', 'bottom', 'left', 'right' keys
    """
    try:
        top = cell_lines['top'][1]
        bottom = cell_lines['bottom'][1]
        left = cell_lines['left'][0]
        right = cell_lines['right'][0]
        
        marker_x, marker_y = marker_coords
        
        # Padding ekle
        top = max(0, top + padding)
        bottom = min(image.shape[0], bottom - padding)
        left = max(0, left + padding)
        right = min(image.shape[1], right - padding)
        
        print(f"    ✂️  Crop bölgesi:")
        print(f"       X: {left} → {right} (genişlik: {right-left})")
        print(f"       Y: {top} → {bottom} (yükseklik: {bottom-top})")
        
        # Crop
        cropped = image[top:bottom, left:right]
        
        # Yeni marker koordinatları
        new_marker_x = marker_x - left
        new_marker_y = marker_y - top
        
        print(f"    📍 Yeni marker: ({new_marker_x}, {new_marker_y})")
        
        if debug:
            debug_img = image.copy()
            cv2.rectangle(debug_img, (left, top), (right, bottom), (0, 255, 255), 3)
            cv2.circle(debug_img, (marker_x, marker_y), 10, (0, 0, 255), -1)
            cv2.imwrite("debug_03_crop_region.png", debug_img)
            cv2.imwrite("debug_04_cropped_cell.png", cropped)
        
        return cropped, (new_marker_x, new_marker_y)
    
    except Exception as e:
        print(f"❌ Crop hatası: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def find_subgrid_position(image, target_rgb, step=1, icon_name=""):
    """
    Divide image into 3x3 grid and find which cell contains most of the target color
    Grid numbering:
        7  8  9
        4  5  6
        1  2  3
    """
    try:
        h, w, _ = image.shape
        sub_width = w // 3
        sub_height = h // 3
        
        max_percentage = 0
        selected_cell = -1
        selected_sub_img = None
        
        print(f"  [Step {step}] Analyzing 3x3 grid ({w}x{h} pixels)...")
        
        # Use higher tolerance for player (yellow is harder to detect)
        color_tolerance = 20 if "player" in icon_name.lower() else 10
        
        for i in range(3):  # Rows
            for j in range(3):  # Columns
                x_start = j * sub_width
                y_start = i * sub_height
                sub_img = image[y_start:y_start + sub_height, x_start:x_start + sub_width]
                
                # Create mask for target color with adaptive tolerance
                mask = cv2.inRange(
                    sub_img,
                    np.array([target_rgb[2] - color_tolerance, target_rgb[1] - color_tolerance, target_rgb[0] - color_tolerance]),
                    np.array([target_rgb[2] + color_tolerance, target_rgb[1] + color_tolerance, target_rgb[0] + color_tolerance])
                )
                
                # Calculate percentage of target color
                percentage = (cv2.countNonZero(mask) / (sub_width * sub_height)) * 100
                
                # Grid cell number (keypad style)
                cell_number = 7 + j - i * 3
                
                print(f"    Cell {cell_number}: {percentage:.2f}% color match")
                
                if percentage > max_percentage:
                    max_percentage = percentage
                    selected_cell = cell_number
                    selected_sub_img = sub_img
        
        # Draw grid lines for debugging
        debug_img = image.copy()
        for i in range(1, 3):
            cv2.line(debug_img, (i * sub_width, 0), (i * sub_width, h), (255, 0, 0), 2)
            cv2.line(debug_img, (0, i * sub_height), (w, i * sub_height), (255, 0, 0), 2)
        cv2.imwrite(f"debug_subgrid_step_{step}.png", debug_img)
        
        print(f"  [Step {step}] Selected cell: {selected_cell} ({max_percentage:.2f}%)")
        
        return selected_cell, selected_sub_img
    
    except Exception as e:
        print(f"Subgrid detection error: {e}")
        return None, None


def get_full_coordinates(base_coord, screen_img, color_rgb, icon_name):
    """
    Get full 5-part coordinates by:
    1. Starting with base coordinate (3 parts from OCR)
    2. Finding icon position on map
    3. Detecting which sub-grid cells it's in (2 more parts)
    """
    
    print(f"\n[{icon_name}] Starting coordinate detection...")
    print(f"  Base coordinate: {base_coord}")
    
    if not base_coord:
        print(f"  ❌ No base coordinate")
        return None
    
    # Find icon position on screen with appropriate tolerance
    tolerance = PLAYER_TOLERANCE if icon_name == "Player" else MARKER_TOLERANCE
    icon_pos = detect_color_position(screen_img, color_rgb, tolerance=tolerance, debug_name=icon_name.lower())
    
    if not icon_pos:
        print(f"  ❌ Icon not found on map (color RGB: {color_rgb}, tolerance: {tolerance})")
        return base_coord  # Return base coordinate only
    
    x, y = icon_pos
    print(f"  ✓ Icon found at ({x}, {y})")
    
    # Crop area around icon
    half_size = 150
    h, w, _ = screen_img.shape
    x_start = max(0, x - half_size)
    x_end = min(w, x + half_size)
    y_start = max(0, y - half_size)
    y_end = min(h, y + half_size)
    
    cropped = screen_img[y_start:y_end, x_start:x_end]
    cv2.imwrite(f"debug_{icon_name.lower()}_cropped.png", cropped)
    print(f"  ✓ Cropped to {cropped.shape[1]}x{cropped.shape[0]} around icon")
    
    # SMART GRID DETECTION - Sadece 2 çizgi bul, diğer 2'sini oluştur
    # Cropped image içindeki marker pozisyonu (merkez)
    cropped_marker_x = x - x_start
    cropped_marker_y = y - y_start
    
    cell_lines = detect_grid_lines_smart(
        cropped, 
        (cropped_marker_x, cropped_marker_y),
        cell_size=CELL_SIZE,
        debug=True
    )
    
    if cell_lines is None:
        print(f"  ❌ Grid algılanamadı")
        return base_coord
    
    print(f"  ✅ Grid sınırları belirlendi")
    
    # Crop to specific grid cell
    cell_img, new_coords = crop_to_cell(
        cropped, 
        cell_lines, 
        (cropped_marker_x, cropped_marker_y),
        padding=5,
        debug=True
    )
    
    if cell_img is None:
        print(f"  ❌ Could not crop to grid cell")
        return base_coord
    
    cv2.imwrite(f"debug_{icon_name.lower()}_cell.png", cell_img)
    print(f"  ✓ Cropped to grid cell: {cell_img.shape[1]}x{cell_img.shape[0]}")
    
    # Find first subgrid level
    first_subgrid, first_sub_img = find_subgrid_position(cell_img, color_rgb, step=1, icon_name=icon_name)
    
    if not first_subgrid or first_sub_img is None:
        print(f"  ❌ First subgrid not detected")
        return base_coord
    
    print(f"  ✓ First subgrid: {first_subgrid}")
    
    # Find second subgrid level
    second_subgrid, _ = find_subgrid_position(first_sub_img, color_rgb, step=2, icon_name=icon_name)
    
    if not second_subgrid:
        print(f"  ⚠️ Second subgrid not detected, using 4-part coordinate")
        return f"{base_coord}-{first_subgrid}"
    
    print(f"  ✓ Second subgrid: {second_subgrid}")
    
    # Return full coordinate
    full_coord = f"{base_coord}-{first_subgrid}-{second_subgrid}"
    print(f"  ✅ Full coordinate: {full_coord}")
    return full_coord


#####################################
# Main Reader Loop
#####################################
def read_coordinates():
    """Read coordinates from screen and return dictionary"""
    global last_known_coords, player_locked, locked_player_coord, marker_locked, locked_marker_coord
    
    # If player is locked, use locked coordinate
    if player_locked and locked_player_coord:
        print(f"\n🔒 PLAYER LOCKED: {locked_player_coord}")
        player_coord = locked_player_coord
        player_base = '-'.join(locked_player_coord.split('-')[:3])
    else:
        # Read OCR text for player
        ocr_text = capture_ocr_region(OCR_LEFT, OCR_TOP, OCR_WIDTH, OCR_HEIGHT)
        player_pattern = r"Player Position:\s*([A-Z]\d+\s*[-–]\s*\d+\s*[-–]\s*\d+)"
        player_match = re.search(player_pattern, ocr_text)
        player_base = format_coordinate(player_match.group(1)) if player_match else None
    
    # If marker is locked, use locked coordinate
    if marker_locked and locked_marker_coord:
        print(f"🔒 MARKER LOCKED: {locked_marker_coord}")
        marker_coord = locked_marker_coord
        marker_base = '-'.join(locked_marker_coord.split('-')[:3])
    else:
        # Read marker coordinates from OCR
        ocr_text = capture_ocr_region(OCR_LEFT, OCR_TOP, OCR_WIDTH, OCR_HEIGHT)
        marker_pattern = r"Marked Position:\s*([A-Z]\d+\s*[-–]\s*\d+\s*[-–]\s*\d+)"
        marker_match = re.search(marker_pattern, ocr_text)
        marker_base = format_coordinate(marker_match.group(1)) if marker_match else None
    
    # Use last known base coordinates if current ones are None
    if not player_locked:
        if player_base is None:
            player_base = last_known_coords["player_base"]
            print(f"  Using cached player base: {player_base}")
        else:
            last_known_coords["player_base"] = player_base
    
    if not marker_locked:
        if marker_base is None:
            marker_base = last_known_coords["marker_base"]
            print(f"  Using cached marker base: {marker_base}")
        else:
            last_known_coords["marker_base"] = marker_base
    
    print(f"\nOCR Results:")
    if not player_locked:
        print(f"  Player Base: {player_base}")
    if not marker_locked:
        print(f"  Marker Base: {marker_base}")
    
    # Capture screen
    screen_img = capture_screen_region(SCENE_LEFT, SCENE_TOP, SCENE_WIDTH, SCENE_HEIGHT)
    
    if screen_img is None:
        print("Failed to capture screen")
        return None
    
    # Get full coordinates with subgrids
    if not player_locked:
        player_coord = get_full_coordinates(player_base, screen_img, PLAYER_COLOR_RGB, "Player")
        # Check if player coordinate is now 5 parts and lock it
        if player_coord and len(player_coord.split('-')) >= 5:
            player_locked = True
            locked_player_coord = player_coord
            print(f"🔒 PLAYER LOCKED at {player_coord}")
            print(f"   Press Ctrl+' to unlock")
    
    if not marker_locked:
        marker_coord = get_full_coordinates(marker_base, screen_img, MARKER_COLOR_RGB, "Marker")
        # Check if marker coordinate is now 5 parts and lock it
        if marker_coord and len(marker_coord.split('-')) >= 5:
            marker_locked = True
            locked_marker_coord = marker_coord
            print(f"🔒 MARKER LOCKED at {marker_coord}")
            print(f"   Press Ctrl+; to unlock")
    
    # Update cache with new full coordinates if they're valid
    if player_coord is not None:
        last_known_coords["player_full"] = player_coord
    else:
        player_coord = last_known_coords["player_full"]
        print(f"  Using cached player full: {player_coord}")
    
    if marker_coord is not None:
        last_known_coords["marker_full"] = marker_coord
    else:
        marker_coord = last_known_coords["marker_full"]
        print(f"  Using cached marker full: {marker_coord}")
    
    print(f"\nFull Coordinates:")
    print(f"  Player: {player_coord}")
    print(f"  Marker: {marker_coord}")
    
    # Only create result if we have at least one valid coordinate
    if player_coord is None and marker_coord is None:
        print("No valid coordinates available")
        return None
    
    # Create result dictionary
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "player": {
            "base": player_base,
            "full": player_coord
        },
        "marker": {
            "base": marker_base,
            "full": marker_coord
        }
    }
    
    return result


def save_to_json(data, filename=OUTPUT_FILE):
    """Save coordinates to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\n✓ Saved to {filename}")
    except Exception as e:
        print(f"Error saving to JSON: {e}")


def read_firing_solution():
    """Read firing solution from JSON file"""
    try:
        with open(FIRING_SOLUTION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading firing solution: {e}")
        return None


#####################################
# Overlay Window
#####################################
class FiringSolutionOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Firing Solution")
        
        # Window properties - always on top, no border, transparent background
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        self.root.overrideredirect(True)
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Position at top right (to avoid OCR region)
        window_width = 500
        window_height = 220
        x = screen_width - window_width - 50  # 50 pixels from right edge
        y = 20  # 20 pixels from top
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.configure(bg='black')
        
        # Create main frame with border
        self.frame = tk.Frame(self.root, bg='#1a1a1a', highlightbackground='#00ff00', 
                             highlightthickness=2)
        self.frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create labels with larger fonts
        bold_font = tkfont.Font(family='Consolas', size=16, weight='bold')
        normal_font = tkfont.Font(family='Consolas', size=14)
        
        # Elevation label
        self.elevation_label = tk.Label(
            self.frame,
            text="ELEVATION: ---",
            font=bold_font,
            fg='#00ff00',
            bg='#1a1a1a'
        )
        self.elevation_label.pack(pady=(10, 5))
        
        # Bearing label
        self.bearing_label = tk.Label(
            self.frame,
            text="BEARING: ---",
            font=bold_font,
            fg='#00ff00',
            bg='#1a1a1a'
        )
        self.bearing_label.pack(pady=5)
        
        # Status label
        self.status_label = tk.Label(
            self.frame,
            text="Waiting for data...",
            font=normal_font,
            fg='#ffff00',
            bg='#1a1a1a'
        )
        self.status_label.pack(pady=(5, 10))
        
        # Lock status label
        self.lock_label = tk.Label(
            self.frame,
            text="",
            font=tkfont.Font(family='Consolas', size=11),
            fg='#00ffff',
            bg='#1a1a1a',
            justify='left'
        )
        self.lock_label.pack(pady=(0, 5))
        
        self.last_update_time = 0
        
    def update_display(self, firing_solution, coord_status, player_locked=False, marker_locked=False, locked_player_coord=None, locked_marker_coord=None):
        """Update overlay display with firing solution and status"""
        current_time = time.time()
        
        # Update lock status
        lock_text = []
        if player_locked and locked_player_coord:
            lock_text.append(f"🔒 PLAYER LOCKED: {locked_player_coord}")
        else:
            lock_text.append("🔓 PLAYER UNLOCKED")
        
        if marker_locked and locked_marker_coord:
            lock_text.append(f"🔒 MARKER LOCKED: {locked_marker_coord}")
        else:
            lock_text.append("🔓 MARKER UNLOCKED")
        
        self.lock_label.config(
            text="\n".join(lock_text),
            fg='#00ffff'
        )
        
        if firing_solution:
            # Update firing solution display
            elevation = firing_solution.get('elevation', '---')
            unit = firing_solution.get('elevationUnit', 'mil')
            bearing = firing_solution.get('bearing', '---')
            
            self.elevation_label.config(
                text=f"ELEVATION: {elevation} {unit}",
                fg='#00ff00'
            )
            self.bearing_label.config(
                text=f"BEARING: {bearing}°",
                fg='#00ff00'
            )
            
            # Check if data is stale (older than 5 seconds)
            if current_time - self.last_update_time > 5:
                self.status_label.config(
                    text="⚠️ Data may be outdated",
                    fg='#ff8800'
                )
            else:
                self.status_label.config(text="✓ Ready", fg='#00ff00')
        else:
            # No firing solution available
            self.elevation_label.config(text="ELEVATION: ---", fg='#666666')
            self.bearing_label.config(text="BEARING: ---", fg='#666666')
        
        # Update status based on coordinate detection
        if coord_status:
            # Collect all error messages
            errors = []
            
            if not coord_status.get('player_detected', False):
                errors.append("PLAYER not detected")
            if not coord_status.get('marker_detected', False):
                errors.append("MARKER not detected")
            if not coord_status.get('player_full', False) and coord_status.get('player_detected', False):
                errors.append("PLAYER incomplete")
            if not coord_status.get('marker_full', False) and coord_status.get('marker_detected', False):
                errors.append("MARKER incomplete")
            
            # Display errors or ready status
            if errors:
                # Determine color based on severity
                if any("not detected" in err for err in errors):
                    color = '#ff0000'  # Red for critical errors
                else:
                    color = '#ff8800'  # Orange for warnings
                
                # Combine errors with separator
                error_text = " | ".join(errors)
                self.status_label.config(
                    text=f"⚠️ {error_text}",
                    fg=color
                )
            elif firing_solution:
                self.status_label.config(text="✓ Ready", fg='#00ff00')
                self.last_update_time = current_time
        
        self.root.update()
    
    def run(self):
        """Start the overlay window"""
        self.root.mainloop()


#####################################
# Main Program
#####################################
def on_player_unlock():
    """Callback when Ctrl+' is pressed"""
    global player_locked, locked_player_coord
    player_locked = False
    locked_player_coord = None
    print("\n🔓 PLAYER UNLOCKED - Will refresh on next cycle")


def on_marker_unlock():
    """Callback when Ctrl+; is pressed"""
    global marker_locked, locked_marker_coord
    marker_locked = False
    locked_marker_coord = None
    print("\n🔓 MARKER UNLOCKED - Will refresh on next cycle")


def coordinate_reader_loop(overlay):
    """Main coordinate reading loop running in background thread"""
    print("=" * 50)
    print("SQUAD Coordinate Reader - SMART GRID DETECTION")
    print("=" * 50)
    print("\nPress Ctrl+' to unlock PLAYER coordinate")
    print("Press Ctrl+; to unlock MARKER coordinate")
    print("Press Ctrl+C in terminal to stop\n")
    
    # Setup hotkey listeners
    def for_canonical(f):
        return lambda k: f(keyboard_listener.canonical(k))
    
    # Player unlock hotkey (Ctrl+')
    player_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse("<ctrl>+'"),
        on_player_unlock
    )
    
    # Marker unlock hotkey (Ctrl+;)
    marker_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse('<ctrl>+;'),
        on_marker_unlock
    )
    
    def on_press(key):
        player_hotkey.press(keyboard_listener.canonical(key))
        marker_hotkey.press(keyboard_listener.canonical(key))
    
    def on_release(key):
        player_hotkey.release(keyboard_listener.canonical(key))
        marker_hotkey.release(keyboard_listener.canonical(key))
    
    keyboard_listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    )
    keyboard_listener.start()
    
    try:
        while True:
            print("-" * 50)
            
            # Read coordinates
            coords = read_coordinates()
            
            # Determine coordinate status
            coord_status = {
                'player_detected': False,
                'marker_detected': False,
                'player_full': False,
                'marker_full': False
            }
            
            if coords:
                # Save to JSON
                save_to_json(coords)
                
                # Check coordinate completeness
                player_coord = coords.get('player', {}).get('full')
                marker_coord = coords.get('marker', {}).get('full')
                
                if player_coord:
                    coord_status['player_detected'] = True
                    # Check if 5-part coordinate (full precision)
                    if player_coord and len(player_coord.split('-')) >= 5:
                        coord_status['player_full'] = True
                
                if marker_coord:
                    coord_status['marker_detected'] = True
                    # Check if 5-part coordinate (full precision)
                    if marker_coord and len(marker_coord.split('-')) >= 5:
                        coord_status['marker_full'] = True
            else:
                print("Failed to read coordinates")
            
            # Read firing solution
            firing_solution = read_firing_solution()
            
            # Update overlay
            try:
                overlay.update_display(firing_solution, coord_status, player_locked, marker_locked, locked_player_coord, locked_marker_coord)
            except:
                pass  # Overlay might be closed
            
            # Wait before next update
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    # Create overlay window
    overlay = FiringSolutionOverlay()
    
    # Start coordinate reading in background thread
    reader_thread = threading.Thread(target=coordinate_reader_loop, args=(overlay,), daemon=True)
    reader_thread.start()
    
    # Run overlay window (blocks until window is closed)
    overlay.run()