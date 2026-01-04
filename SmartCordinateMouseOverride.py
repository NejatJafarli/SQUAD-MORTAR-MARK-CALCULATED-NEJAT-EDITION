"""
SQUAD Coordinate Reader v11 - 100m Grid Detection with Manual Override
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
from pynput import keyboard, mouse
from collections import defaultdict
import os
import sys
import autoTargeting
import config
from CordinateReader import CoordinateReader

# Configure Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH

# myOwnPrint fonksiyonunu start_system'den import et
try:
    from start_system import myOwnPrint, DEBUG_MODE
except ImportError:
    # Standalone modda çalışıyorsa fallback
    DEBUG_MODE = config.DEBUG_MODE
    def myOwnPrint(message):
        if DEBUG_MODE:
            print(message)
    
#####################################
# Configuration - config.py'den alınıyor
#####################################
DETECTION_MODE = config.DETECTION_MODE
SCENE_LEFT = config.SCENE_LEFT
SCENE_TOP = config.SCENE_TOP
SCENE_WIDTH = config.SCENE_WIDTH
SCENE_HEIGHT = config.SCENE_HEIGHT
GRID_100M_SIZE = config.GRID_100M_SIZE
GRID_33M_SIZE = config.GRID_33M_SIZE
PLAYER_COLOR_RGB = config.PLAYER_COLOR_RGB
PLAYER_TOLERANCE = config.PLAYER_TOLERANCE
MARKER_COLOR_RGB = config.MARKER_COLOR_RGB
MARKER_TOLERANCE = config.MARKER_TOLERANCE
UPDATE_INTERVAL = config.UPDATE_INTERVAL
OUTPUT_FILE = config.OUTPUT_FILE
FIRING_SOLUTION_FILE = config.FIRING_SOLUTION_FILE

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

# MANUAL MODE - Mouse click positions
manual_player_pos = None  # (x, y) in screen coordinates
manual_marker_pos = None  # (x, y) in screen coordinates

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
        myOwnPrint(f"Screen capture error: {e}")
        return None


#####################################
# SHAPE DETECTION (AUTO MODE)
#####################################
def detect_marker_shape(image, target_rgb, tolerance=50, debug_name="marker"):
    """
    Detect MARKER with shape validation (green arrow/triangle shape)
    Returns position of the marker
    """
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
        
        mask = cv2.inRange(image, low_color, high_color)
        
        if debug_name:
            cv2.imwrite(f"debug_{debug_name}_mask.png", mask)
        
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            myOwnPrint(f"    ❌ No green contours found")
            return None
        
        myOwnPrint(f"    🔍 Found {len(contours)} green contours")
        
        valid_markers = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if area < 50 or area > 500:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h if h > 0 else 0
            
            if aspect_ratio < 0.2 or aspect_ratio > 2.0:
                continue
            
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            
            if circularity > 0.7:
                continue
            
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                score = area * (1.0 - circularity)
                
                valid_markers.append({
                    'position': (cx, cy),
                    'area': area,
                    'aspect_ratio': aspect_ratio,
                    'circularity': circularity,
                    'score': score,
                    'contour': contour
                })
                
                myOwnPrint(f"    ✓ Valid marker candidate: area={area:.0f}, aspect={aspect_ratio:.2f}, circ={circularity:.2f}, score={score:.0f}")
        
        if not valid_markers:
            myOwnPrint(f"    ❌ No valid marker shapes found")
            return None
        
        best_marker = max(valid_markers, key=lambda x: x['score'])
        
        myOwnPrint(f"    ✅ MARKER detected: area={best_marker['area']:.0f}, score={best_marker['score']:.0f}")
        
        if debug_name:
            debug_img = image.copy()
            cv2.drawContours(debug_img, [best_marker['contour']], -1, (0, 255, 0), 2)
            cv2.circle(debug_img, best_marker['position'], 5, (0, 0, 255), -1)
            cv2.imwrite(f"debug_{debug_name}_shape_detected.png", debug_img)
        
        return best_marker['position']
    
    except Exception as e:
        myOwnPrint(f"Marker shape detection error: {e}")
        import traceback
        traceback.print_exc()
        return None


def detect_player_shape(image, target_rgb, tolerance=30, debug_name="player"):
    """
    Detect PLAYER (mortar icon) with shape validation
    Rotation-invariant detection for 360-degree rotation
    """
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
        
        mask = cv2.inRange(image, low_color, high_color)
        
        if debug_name:
            cv2.imwrite(f"debug_{debug_name}_mask.png", mask)
        
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            myOwnPrint(f"    ❌ No yellow contours found")
            return None
        
        myOwnPrint(f"    🔍 Found {len(contours)} yellow contours")
        
        valid_players = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if area < 80 or area > 600:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            
            aspect_ratio = float(w) / h if h > 0 else 0
            
            if aspect_ratio < 0.4 or aspect_ratio > 2.5:
                continue
            
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            
            if circularity < 0.3 or circularity > 0.9:
                continue
            
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                score = area * circularity
                
                valid_players.append({
                    'position': (cx, cy),
                    'area': area,
                    'aspect_ratio': aspect_ratio,
                    'circularity': circularity,
                    'score': score,
                    'contour': contour
                })
                
                myOwnPrint(f"    ✓ Valid player candidate: area={area:.0f}, aspect={aspect_ratio:.2f}, circ={circularity:.2f}, score={score:.0f}")
        
        if not valid_players:
            myOwnPrint(f"    ❌ No valid player shapes found")
            return None
        
        best_player = max(valid_players, key=lambda x: x['score'])
        
        myOwnPrint(f"    ✅ PLAYER detected: area={best_player['area']:.0f}, score={best_player['score']:.0f}")
        
        if debug_name:
            debug_img = image.copy()
            cv2.drawContours(debug_img, [best_player['contour']], -1, (0, 255, 0), 2)
            cv2.circle(debug_img, best_player['position'], 5, (0, 0, 255), -1)
            cv2.imwrite(f"debug_{debug_name}_shape_detected.png", debug_img)
        
        return best_player['position']
    
    except Exception as e:
        myOwnPrint(f"Player shape detection error: {e}")
        import traceback
        traceback.print_exc()
        return None


#####################################
# 100M GRID DETECTION (BLACK LINES)
#####################################
def detect_100m_grid_lines(image, marker_coords, debug=True):
    """
    Detect 100m grid lines (BLACK color, ~310px spacing)
    IMPROVED: Validates grid spacing and line quality
    """
    try:
        h, w = image.shape[:2]
        marker_x, marker_y = marker_coords
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        inverted = cv2.bitwise_not(gray)
        _, binary = cv2.threshold(inverted, 220, 255, cv2.THRESH_BINARY)
        
        if debug:
            cv2.imwrite("debug_100m_binary.png", binary)
        
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (60, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 60))
        
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)
        
        grid_structure = cv2.add(horizontal, vertical)
        
        if debug:
            cv2.imwrite("debug_100m_grid_structure.png", grid_structure)
        
        edges = cv2.Canny(grid_structure, 50, 150, apertureSize=3)
        
        if debug:
            cv2.imwrite("debug_100m_edges.png", edges)
        
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi/180,
            threshold=100,
            minLineLength=min(h, w) // 4,
            maxLineGap=50
        )
        
        if lines is None:
            myOwnPrint("    ❌ No 100m grid lines detected!")
            return None
        
        myOwnPrint(f"    🔍 Raw lines detected: {len(lines)}")
        
        horizontal_lines = []
        vertical_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            angle = np.degrees(np.arctan2(abs(y2 - y1), abs(x2 - x1)))
            
            if angle < 10:
                y_avg = (y1 + y2) // 2
                horizontal_lines.append({
                    'line': (0, y_avg, w, y_avg),
                    'y': y_avg,
                    'length': length
                })
            elif angle > 80:
                x_avg = (x1 + x2) // 2
                vertical_lines.append({
                    'line': (x_avg, 0, x_avg, h),
                    'x': x_avg,
                    'length': length
                })
        
        myOwnPrint(f"    📏 Horizontal candidates: {len(horizontal_lines)}")
        myOwnPrint(f"    📏 Vertical candidates: {len(vertical_lines)}")
        
        horizontal_lines = sorted(horizontal_lines, key=lambda x: x['length'], reverse=True)
        vertical_lines = sorted(vertical_lines, key=lambda x: x['length'], reverse=True)
        
        h_lines = [item['line'] for item in horizontal_lines]
        v_lines = [item['line'] for item in vertical_lines]
        
        h_lines = merge_close_lines(h_lines, 'horizontal', threshold=20)
        v_lines = merge_close_lines(v_lines, 'vertical', threshold=20)
        
        myOwnPrint(f"    📏 Merged horizontal lines: {len(h_lines)}")
        myOwnPrint(f"    📏 Merged vertical lines: {len(v_lines)}")
        myOwnPrint(f"    📍 Marker: ({marker_x}, {marker_y})")
        
        top_line = find_grid_line_with_spacing_validation(
            h_lines, marker_coords, 'horizontal', 'before', 
            expected_spacing=GRID_100M_SIZE, image_size=(w, h)
        )
        bottom_line = find_grid_line_with_spacing_validation(
            h_lines, marker_coords, 'horizontal', 'after',
            expected_spacing=GRID_100M_SIZE, image_size=(w, h)
        )
        left_line = find_grid_line_with_spacing_validation(
            v_lines, marker_coords, 'vertical', 'before',
            expected_spacing=GRID_100M_SIZE, image_size=(w, h)
        )
        right_line = find_grid_line_with_spacing_validation(
            v_lines, marker_coords, 'vertical', 'after',
            expected_spacing=GRID_100M_SIZE, image_size=(w, h)
        )
        
        if not all([top_line, bottom_line, left_line, right_line]):
            myOwnPrint("    ❌ Could not find all 4 boundaries with spacing validation!")
            myOwnPrint(f"       Top: {top_line}")
            myOwnPrint(f"       Bottom: {bottom_line}")
            myOwnPrint(f"       Left: {left_line}")
            myOwnPrint(f"       Right: {right_line}")
            return None
        
        cell_lines = {
            'top': top_line,
            'bottom': bottom_line,
            'left': left_line,
            'right': right_line
        }
        
        top_y = top_line[1]
        bottom_y = bottom_line[1]
        left_x = left_line[0]
        right_x = right_line[0]
        
        cell_width = right_x - left_x
        cell_height = bottom_y - top_y
        
        myOwnPrint(f"    ✅ 100m Grid boundaries:")
        myOwnPrint(f"       Top Y: {top_y}")
        myOwnPrint(f"       Bottom Y: {bottom_y}")
        myOwnPrint(f"       Left X: {left_x}")
        myOwnPrint(f"       Right X: {right_x}")
        myOwnPrint(f"       Cell size: {cell_width}x{cell_height} pixels")
        
        if abs(cell_width - GRID_100M_SIZE) > 100 or abs(cell_height - GRID_100M_SIZE) > 100:
            myOwnPrint(f"    ⚠️  WARNING: Cell dimensions far from expected {GRID_100M_SIZE}px")
            myOwnPrint(f"       Width diff: {abs(cell_width - GRID_100M_SIZE)}px")
            myOwnPrint(f"       Height diff: {abs(cell_height - GRID_100M_SIZE)}px")
        
        if debug:
            debug_img = image.copy()
            for line in h_lines:
                cv2.line(debug_img, (line[0], line[1]), (line[2], line[3]), (255, 0, 0), 1)
            for line in v_lines:
                cv2.line(debug_img, (line[0], line[1]), (line[2], line[3]), (255, 0, 0), 1)
            
            cv2.line(debug_img, (0, top_y), (w, top_y), (0, 255, 0), 3)
            cv2.line(debug_img, (0, bottom_y), (w, bottom_y), (0, 255, 0), 3)
            cv2.line(debug_img, (left_x, 0), (left_x, h), (0, 255, 0), 3)
            cv2.line(debug_img, (right_x, 0), (right_x, h), (0, 255, 0), 3)
            
            cv2.circle(debug_img, (marker_x, marker_y), 10, (0, 0, 255), -1)
            
            cv2.imwrite("debug_100m_cell_boundaries.png", debug_img)
        
        return cell_lines
    
    except Exception as e:
        myOwnPrint(f"❌ 100m grid detection error: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_grid_line_with_spacing_validation(lines, marker_coord, orientation='horizontal', 
                                          direction='before', expected_spacing=310, image_size=(800, 800)):
    """Find closest grid line to marker WITH spacing validation"""
    if not lines:
        myOwnPrint(f"      ⚠️  No {orientation} lines to validate")
        return None
    
    if orientation == 'horizontal':
        line_positions = [(l, l[1]) for l in lines]
        marker_pos = marker_coord[1]
        image_dimension = image_size[1]
    else:
        line_positions = [(l, l[0]) for l in lines]
        marker_pos = marker_coord[0]
        image_dimension = image_size[0]
    
    if direction == 'before':
        candidates = [(l, pos) for l, pos in line_positions if pos < marker_pos]
        if not candidates:
            myOwnPrint(f"      ⚠️  No {orientation} lines {direction} marker")
            return None
    else:
        candidates = [(l, pos) for l, pos in line_positions if pos >= marker_pos]
        if not candidates:
            myOwnPrint(f"      ⚠️  No {orientation} lines {direction} marker")
            return None
    
    candidates = sorted(candidates, key=lambda x: abs(x[1] - marker_pos))
    
    myOwnPrint(f"      🔍 Validating {len(candidates)} {orientation} {direction} candidates")
    
    for candidate_line, candidate_pos in candidates:
        if direction == 'before':
            expected_neighbor_pos = candidate_pos + expected_spacing
        else:
            expected_neighbor_pos = candidate_pos - expected_spacing
        
        tolerance = 50
        
        has_valid_neighbor = False
        for other_line, other_pos in line_positions:
            if abs(other_pos - expected_neighbor_pos) < tolerance:
                has_valid_neighbor = True
                spacing_error = abs(other_pos - expected_neighbor_pos)
                actual_spacing = abs(other_pos - candidate_pos)
                myOwnPrint(f"      ✓ Found valid neighbor: spacing={actual_spacing:.0f}px (error: {spacing_error:.0f}px)")
                break
        
        min_edge_distance = 20
        if candidate_pos < min_edge_distance or candidate_pos > image_dimension - min_edge_distance:
            myOwnPrint(f"      ⚠️  Line at {candidate_pos} too close to edge")
            continue
        
        if has_valid_neighbor or len(line_positions) < 3:
            myOwnPrint(f"      ✅ Selected {orientation} {direction} line at {candidate_pos}")
            return candidate_line
    
    myOwnPrint(f"      ⚠️  No validated line found, using closest")
    return candidates[0][0] if candidates else None


def merge_close_lines(lines, orientation, threshold=10):
    """Merge lines that are close together"""
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
    """Average a group of lines"""
    if orientation == 'horizontal':
        avg_y = int(np.mean([l[1] for l in lines]))
        return (lines[0][0], avg_y, lines[0][2], avg_y)
    else:
        avg_x = int(np.mean([l[0] for l in lines]))
        return (avg_x, lines[0][1], avg_x, lines[0][3])


def crop_to_100m_cell(image, cell_lines, marker_coords, padding=5, debug=True):
    """Crop to 100m cell boundaries"""
    try:
        top = cell_lines['top'][1]
        bottom = cell_lines['bottom'][1]
        left = cell_lines['left'][0]
        right = cell_lines['right'][0]
        
        marker_x, marker_y = marker_coords
        
        top = max(0, top + padding)
        bottom = min(image.shape[0], bottom - padding)
        left = max(0, left + padding)
        right = min(image.shape[1], right - padding)
        
        myOwnPrint(f"    ✂️  Crop 100m cell:")
        myOwnPrint(f"       X: {left} → {right} (width: {right-left})")
        myOwnPrint(f"       Y: {top} → {bottom} (height: {bottom-top})")
        
        cropped = image[top:bottom, left:right]
        
        new_marker_x = marker_x - left
        new_marker_y = marker_y - top
        
        myOwnPrint(f"    📍 New marker position: ({new_marker_x}, {new_marker_y})")
        
        if debug:
            debug_img = image.copy()
            cv2.rectangle(debug_img, (left, top), (right, bottom), (0, 255, 255), 3)
            cv2.circle(debug_img, (marker_x, marker_y), 10, (0, 0, 255), -1)
            cv2.imwrite("debug_100m_crop_region.png", debug_img)
            cv2.imwrite("debug_100m_cropped_cell.png", cropped)
        
        return cropped, (new_marker_x, new_marker_y)
    
    except Exception as e:
        myOwnPrint(f"❌ Crop error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def find_33m_subgrid_position(image, marker_coords, target_rgb, tolerance, icon_name=""):
    """Divide 100m cell into 3x3 grid (33m each) - for AUTO mode"""
    try:
        h, w = image.shape[:2]
        marker_x, marker_y = marker_coords
        
        sub_width = w // 3
        sub_height = h // 3
        
        myOwnPrint(f"  [33m subgrid] Analyzing 3x3 grid ({w}x{h} pixels)...")
        myOwnPrint(f"  [33m subgrid] Each cell: {sub_width}x{sub_height} pixels")
        
        max_percentage = 0
        selected_cell = -1
        selected_sub_img = None
        selected_coords = None
        
        for i in range(3):
            for j in range(3):
                x_start = j * sub_width
                y_start = i * sub_height
                sub_img = image[y_start:y_start + sub_height, x_start:x_start + sub_width]
                
                mask = cv2.inRange(
                    sub_img,
                    np.array([target_rgb[2] - tolerance, target_rgb[1] - tolerance, target_rgb[0] - tolerance]),
                    np.array([target_rgb[2] + tolerance, target_rgb[1] + tolerance, target_rgb[0] + tolerance])
                )
                
                percentage = (cv2.countNonZero(mask) / (sub_width * sub_height)) * 100
                
                cell_number = 7 + j - i * 3
                
                myOwnPrint(f"    Cell {cell_number}: {percentage:.2f}% color match")
                
                if percentage > max_percentage:
                    max_percentage = percentage
                    selected_cell = cell_number
                    selected_sub_img = sub_img
                    selected_coords = (marker_x - x_start, marker_y - y_start)
        
        debug_img = image.copy()
        for i in range(1, 3):
            cv2.line(debug_img, (i * sub_width, 0), (i * sub_width, h), (255, 0, 0), 2)
            cv2.line(debug_img, (0, i * sub_height), (w, i * sub_height), (255, 0, 0), 2)
        cv2.circle(debug_img, (marker_x, marker_y), 8, (0, 0, 255), -1)
        cv2.imwrite(f"debug_33m_subgrid_step1_{icon_name}.png", debug_img)
        
        myOwnPrint(f"  [33m subgrid] Selected cell: {selected_cell} ({max_percentage:.2f}%)")
        
        return selected_cell, selected_sub_img, selected_coords
    
    except Exception as e:
        myOwnPrint(f"33m subgrid error: {e}")
        return None, None, None


def find_11m_subgrid_position(image, marker_coords, target_rgb, tolerance, icon_name=""):
    """Divide 33m cell into 3x3 grid (11m each) - for AUTO mode"""
    try:
        h, w = image.shape[:2]
        marker_x, marker_y = marker_coords
        
        sub_width = w // 3
        sub_height = h // 3
        
        myOwnPrint(f"  [11m subgrid] Analyzing 3x3 grid ({w}x{h} pixels)...")
        myOwnPrint(f"  [11m subgrid] Each cell: {sub_width}x{sub_height} pixels")
        
        max_percentage = 0
        selected_cell = -1
        
        for i in range(3):
            for j in range(3):
                x_start = j * sub_width
                y_start = i * sub_height
                sub_img = image[y_start:y_start + sub_height, x_start:x_start + sub_width]
                
                mask = cv2.inRange(
                    sub_img,
                    np.array([target_rgb[2] - tolerance, target_rgb[1] - tolerance, target_rgb[0] - tolerance]),
                    np.array([target_rgb[2] + tolerance, target_rgb[1] + tolerance, target_rgb[0] + tolerance])
                )
                
                percentage = (cv2.countNonZero(mask) / (sub_width * sub_height)) * 100
                
                cell_number = 7 + j - i * 3
                
                myOwnPrint(f"    Cell {cell_number}: {percentage:.2f}% color match")
                
                if percentage > max_percentage:
                    max_percentage = percentage
                    selected_cell = cell_number
        
        debug_img = image.copy()
        for i in range(1, 3):
            cv2.line(debug_img, (i * sub_width, 0), (i * sub_width, h), (0, 255, 0), 2)
            cv2.line(debug_img, (0, i * sub_height), (w, i * sub_height), (0, 255, 0), 2)
        cv2.circle(debug_img, (marker_x, marker_y), 5, (0, 0, 255), -1)
        cv2.imwrite(f"debug_11m_subgrid_step2_{icon_name}.png", debug_img)
        
        myOwnPrint(f"  [11m subgrid] Selected cell: {selected_cell} ({max_percentage:.2f}%)")
        
        return selected_cell
    
    except Exception as e:
        myOwnPrint(f"11m subgrid error: {e}")
        return None


#####################################
# COORDINATE CALCULATION FUNCTIONS
#####################################
def get_full_coordinates(base_coord, screen_img, color_rgb, tolerance, icon_name):
    """Get full coordinates using AUTO MODE (shape detection)"""
    
    myOwnPrint(f"\n[{icon_name}] Starting AUTO coordinate detection...")
    myOwnPrint(f"  Base coordinate: {base_coord}")
    
    if not base_coord:
        myOwnPrint(f"  ❌ No base coordinate")
        return None
    
    if "Marker" in icon_name:
        myOwnPrint(f"  🔍 Using MARKER shape detection (green arrow)")
        icon_pos = detect_marker_shape(screen_img, color_rgb, tolerance=tolerance, debug_name=icon_name.lower())
    else:
        myOwnPrint(f"  🔍 Using PLAYER shape detection (yellow mortar, rotation-invariant)")
        icon_pos = detect_player_shape(screen_img, color_rgb, tolerance=tolerance, debug_name=icon_name.lower())
    
    if not icon_pos:
        myOwnPrint(f"  ❌ Icon shape not found on map")
        return base_coord
    
    x, y = icon_pos
    myOwnPrint(f"  ✓ Icon shape found at ({x}, {y})")
    
    crop_size = 400
    h, w, _ = screen_img.shape
    x_start = max(0, x - crop_size)
    x_end = min(w, x + crop_size)
    y_start = max(0, y - crop_size)
    y_end = min(h, y + crop_size)
    
    cropped = screen_img[y_start:y_end, x_start:x_end]
    cv2.imwrite(f"debug_{icon_name.lower()}_initial_crop.png", cropped)
    
    cropped_marker_x = x - x_start
    cropped_marker_y = y - y_start
    
    myOwnPrint(f"  ✓ Cropped {cropped.shape[1]}x{cropped.shape[0]} around icon")
    
    cell_lines = detect_100m_grid_lines(cropped, (cropped_marker_x, cropped_marker_y), debug=True)
    
    if cell_lines is None:
        myOwnPrint(f"  ❌ Could not detect 100m grid")
        return base_coord
    
    myOwnPrint(f"  ✅ 100m grid detected")
    
    cell_100m, new_marker_coords = crop_to_100m_cell(
        cropped,
        cell_lines,
        (cropped_marker_x, cropped_marker_y),
        padding=5,
        debug=True
    )
    
    if cell_100m is None:
        myOwnPrint(f"  ❌ Could not crop to 100m cell")
        return base_coord
    
    myOwnPrint(f"  ✅ 100m cell cropped")
    
    subgrid_33m, cell_33m_img, coords_33m = find_33m_subgrid_position(
        cell_100m,
        new_marker_coords,
        color_rgb,
        tolerance,
        icon_name
    )
    
    if not subgrid_33m or cell_33m_img is None:
        myOwnPrint(f"  ❌ Could not find 33m subgrid")
        return base_coord
    
    myOwnPrint(f"  ✅ 33m subgrid: {subgrid_33m}")
    
    subgrid_11m = find_11m_subgrid_position(
        cell_33m_img,
        coords_33m,
        color_rgb,
        tolerance,
        icon_name
    )
    
    if not subgrid_11m:
        myOwnPrint(f"  ⚠️ Could not find 11m subgrid, returning base coordinate")
        return base_coord
    
    myOwnPrint(f"  ✅ 11m subgrid: {subgrid_11m}")
    
    full_coord = f"{base_coord}-{subgrid_11m}"
    myOwnPrint(f"  ✅ Full coordinate: {full_coord}")
    return full_coord


def get_full_coordinates_manual(base_coord, screen_img, click_pos, icon_name):
    """Get full coordinates using MANUAL MODE (click position)"""
    
    myOwnPrint(f"\n[{icon_name}] Starting MANUAL coordinate detection...")
    myOwnPrint(f"  Base coordinate: {base_coord}")
    myOwnPrint(f"  Manual click position: {click_pos}")
    
    if not base_coord:
        myOwnPrint(f"  ❌ No base coordinate")
        return None
    
    if not click_pos:
        myOwnPrint(f"  ❌ No manual click position")
        return None
    
    x = click_pos[0] - SCENE_LEFT
    y = click_pos[1] - SCENE_TOP
    
    if x < 0 or x >= screen_img.shape[1] or y < 0 or y >= screen_img.shape[0]:
        myOwnPrint(f"  ❌ Click position outside map bounds")
        return None
    
    myOwnPrint(f"  ✓ Map position: ({x}, {y})")
    
    crop_size = 400
    h, w, _ = screen_img.shape
    x_start = max(0, x - crop_size)
    x_end = min(w, x + crop_size)
    y_start = max(0, y - crop_size)
    y_end = min(h, y + crop_size)
    
    cropped = screen_img[y_start:y_end, x_start:x_end]
    cv2.imwrite(f"debug_{icon_name.lower()}_manual_crop.png", cropped)
    
    cropped_marker_x = x - x_start
    cropped_marker_y = y - y_start
    
    myOwnPrint(f"  ✓ Cropped {cropped.shape[1]}x{cropped.shape[0]} around click")
    
    cell_lines = detect_100m_grid_lines(cropped, (cropped_marker_x, cropped_marker_y), debug=True)
    
    if cell_lines is None:
        myOwnPrint(f"  ❌ Could not detect 100m grid")
        return base_coord
    
    myOwnPrint(f"  ✅ 100m grid detected")
    
    cell_100m, new_marker_coords = crop_to_100m_cell(
        cropped,
        cell_lines,
        (cropped_marker_x, cropped_marker_y),
        padding=5,
        debug=True
    )
    
    if cell_100m is None:
        myOwnPrint(f"  ❌ Could not crop to 100m cell")
        return base_coord
    
    myOwnPrint(f"  ✅ 100m cell cropped")
    
    h_cell, w_cell = cell_100m.shape[:2]
    sub_width = w_cell // 3
    sub_height = h_cell // 3
    
    marker_x, marker_y = new_marker_coords
    
    col = min(2, marker_x // sub_width)
    row = min(2, marker_y // sub_height)
    
    subgrid_33m = 7 + col - row * 3
    
    myOwnPrint(f"  ✓ 33m subgrid: {subgrid_33m} (row={row}, col={col})")
    
    x_start_33 = col * sub_width
    y_start_33 = row * sub_height
    cell_33m_img = cell_100m[y_start_33:y_start_33 + sub_height, x_start_33:x_start_33 + sub_width]
    
    coords_33m = (marker_x - x_start_33, marker_y - y_start_33)
    
    debug_img = cell_100m.copy()
    for i in range(1, 3):
        cv2.line(debug_img, (i * sub_width, 0), (i * sub_width, h_cell), (255, 0, 0), 2)
        cv2.line(debug_img, (0, i * sub_height), (w_cell, i * sub_height), (255, 0, 0), 2)
    cv2.circle(debug_img, (marker_x, marker_y), 8, (0, 0, 255), -1)
    cv2.imwrite(f"debug_33m_manual_subgrid_{icon_name}.png", debug_img)
    
    h_33, w_33 = cell_33m_img.shape[:2]
    sub_width_11 = w_33 // 3
    sub_height_11 = h_33 // 3
    
    marker_x_33, marker_y_33 = coords_33m
    
    col_11 = min(2, marker_x_33 // sub_width_11)
    row_11 = min(2, marker_y_33 // sub_height_11)
    
    subgrid_11m = 7 + col_11 - row_11 * 3
    
    myOwnPrint(f"  ✓ 11m subgrid: {subgrid_11m} (row={row_11}, col={col_11})")
    
    debug_img_11 = cell_33m_img.copy()
    for i in range(1, 3):
        cv2.line(debug_img_11, (i * sub_width_11, 0), (i * sub_width_11, h_33), (0, 255, 0), 2)
        cv2.line(debug_img_11, (0, i * sub_height_11), (w_33, i * sub_height_11), (0, 255, 0), 2)
    cv2.circle(debug_img_11, (marker_x_33, marker_y_33), 5, (0, 0, 255), -1)
    cv2.imwrite(f"debug_11m_manual_subgrid_{icon_name}.png", debug_img_11)
    
    full_coord = f"{base_coord}-{subgrid_11m}"
    myOwnPrint(f"  ✅ Full coordinate: {full_coord}")
    return full_coord


playerCordinateReader=CoordinateReader(config.PLAYER_CORDINATES[0], config.PLAYER_CORDINATES[1], config.PLAYER_CORDINATES[2], config.PLAYER_CORDINATES[3])
markerCordinateReader=CoordinateReader(config.MARKER_CORDINATES[0], config.MARKER_CORDINATES[1], config.MARKER_CORDINATES[2], config.MARKER_CORDINATES[3])

#####################################
# Main Reader Loop
#####################################
def read_coordinates():
    """Read coordinates from screen and return dictionary"""
    global last_known_coords, player_locked, locked_player_coord, marker_locked, locked_marker_coord
    global manual_player_pos, manual_marker_pos
    
    if player_locked and locked_player_coord:
        myOwnPrint(f"\n🔒 PLAYER LOCKED: {locked_player_coord}")
        player_coord = locked_player_coord
        player_base = '-'.join(locked_player_coord.split('-')[:3])
    else:
        player_base = playerCordinateReader.read_coordinate()
    
    if marker_locked and locked_marker_coord:
        myOwnPrint(f"🔒 MARKER LOCKED: {locked_marker_coord}")
        marker_coord = locked_marker_coord
        marker_base = '-'.join(locked_marker_coord.split('-')[:3])
    else:
        marker_base = markerCordinateReader.read_coordinate()
    
    if not player_locked:
        if player_base is None:
            player_base = last_known_coords["player_base"]
            myOwnPrint(f"  Using cached player base: {player_base}")
        else:
            last_known_coords["player_base"] = player_base
    
    if not marker_locked:
        if marker_base is None:
            marker_base = last_known_coords["marker_base"]
            myOwnPrint(f"  Using cached marker base: {marker_base}")
        else:
            last_known_coords["marker_base"] = marker_base
    
    myOwnPrint(f"\nOCR Results:")
    if not player_locked:
        myOwnPrint(f"  Player Base: {player_base}")
    if not marker_locked:
        myOwnPrint(f"  Marker Base: {marker_base}")
    
    if DETECTION_MODE == 2:
        myOwnPrint(f"\n🎯 MANUAL MODE - Waiting for Ctrl+Click positions")
        myOwnPrint(f"  Player manual pos: {manual_player_pos}")
        myOwnPrint(f"  Marker manual pos: {manual_marker_pos}")
    
    screen_img = capture_screen_region(SCENE_LEFT, SCENE_TOP, SCENE_WIDTH, SCENE_HEIGHT)
    
    if screen_img is None:
        myOwnPrint("Failed to capture screen")
        return None
    
    if not player_locked:
        if DETECTION_MODE == 2:
            # MANUEL MOD - Sadece mouse click kullan
            if manual_player_pos:
                myOwnPrint(f"\n🎯 Using MANUAL player position")
                player_coord = get_full_coordinates_manual(
                    player_base,
                    screen_img,
                    manual_player_pos,
                    "Player"
                )
            else:
                myOwnPrint(f"\n⏳ MANUAL MODE - Waiting for Ctrl+Middle Click on player position")
                player_coord = None
        else:
            # AUTO MOD - Shape detection kullan
            myOwnPrint(f"\n🤖 Using AUTO player detection")
            player_coord = get_full_coordinates(
                player_base, 
                screen_img, 
                PLAYER_COLOR_RGB, 
                PLAYER_TOLERANCE,
                "Player"
            )
        
        if player_coord and len(player_coord.split('-')) >= 4:
            player_locked = True
            locked_player_coord = player_coord
            myOwnPrint(f"🔒 PLAYER LOCKED at {player_coord}")
            myOwnPrint(f"   Press Ctrl+' to unlock")
    
    if not marker_locked:
        if DETECTION_MODE == 2:
            # MANUEL MOD - Sadece mouse click kullan
            if manual_marker_pos:
                myOwnPrint(f"\n🎯 Using MANUAL marker position")
                marker_coord = get_full_coordinates_manual(
                    marker_base,
                    screen_img,
                    manual_marker_pos,
                    "Marker"
                )
            else:
                myOwnPrint(f"\n⏳ MANUAL MODE - Waiting for Ctrl+Left Click on marker position")
                marker_coord = None
        else:
            # AUTO MOD - Shape detection kullan
            myOwnPrint(f"\n🤖 Using AUTO marker detection")
            marker_coord = get_full_coordinates(
                marker_base,
                screen_img,
                MARKER_COLOR_RGB,
                MARKER_TOLERANCE,
                "Marker"
            )
        
        if marker_coord and len(marker_coord.split('-')) >= 4:
            marker_locked = True
            locked_marker_coord = marker_coord
            myOwnPrint(f"🔒 MARKER LOCKED at {marker_coord}")
            myOwnPrint(f"   Press Ctrl+; to unlock")
    
    if player_coord is not None:
        last_known_coords["player_full"] = player_coord
    else:
        player_coord = last_known_coords["player_full"]
        myOwnPrint(f"  Using cached player full: {player_coord}")
    
    if marker_coord is not None:
        last_known_coords["marker_full"] = marker_coord
    else:
        marker_coord = last_known_coords["marker_full"]
        myOwnPrint(f"  Using cached marker full: {marker_coord}")
    
    myOwnPrint(f"\nFull Coordinates:")
    myOwnPrint(f"  Player: {player_coord}")
    myOwnPrint(f"  Marker: {marker_coord}")
    
    if player_coord is None and marker_coord is None:
        myOwnPrint("No valid coordinates available")
        return None
    
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
        myOwnPrint(f"\n✓ Saved to {filename}")
    except Exception as e:
        myOwnPrint(f"Error saving to JSON: {e}")


def read_firing_solution():
    """Read firing solution from JSON file"""
    try:
        with open(FIRING_SOLUTION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        myOwnPrint(f"Error reading firing solution: {e}")
        return None


#####################################
# Overlay Window
#####################################
class FiringSolutionOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Firing Solution")
        
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        self.root.overrideredirect(True)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = 500
        window_height = 250
        x = screen_width - window_width - 50
        y = 20
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.configure(bg='black')
        
        self.frame = tk.Frame(self.root, bg='#1a1a1a', highlightbackground='#00ff00', 
                             highlightthickness=2)
        self.frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        bold_font = tkfont.Font(family='Consolas', size=16, weight='bold')
        normal_font = tkfont.Font(family='Consolas', size=14)
        small_font = tkfont.Font(family='Consolas', size=11)
        
        # Mode display
        mode_text = "🤖 AUTO MODE" if DETECTION_MODE == 1 else "🎯 MANUAL MODE"
        self.mode_label = tk.Label(
            self.frame,
            text=mode_text,
            font=normal_font,
            fg='#00ffff',
            bg='#1a1a1a'
        )
        self.mode_label.pack(pady=(5, 0))
        
        # Weapon display
        self.weapon_label = tk.Label(
            self.frame,
            text="WEAPON: ---",
            font=normal_font,
            fg='#FFA500',
            bg='#1a1a1a'
        )
        self.weapon_label.pack(pady=(5, 0))
        
        self.elevation_label = tk.Label(
            self.frame,
            text="ELEVATION: ---",
            font=bold_font,
            fg='#00ff00',
            bg='#1a1a1a'
        )
        self.elevation_label.pack(pady=(10, 5))
        
        self.bearing_label = tk.Label(
            self.frame,
            text="BEARING: ---",
            font=bold_font,
            fg='#00ff00',
            bg='#1a1a1a'
        )
        self.bearing_label.pack(pady=5)
        
        self.status_label = tk.Label(
            self.frame,
            text="Waiting for data...",
            font=normal_font,
            fg='#ffff00',
            bg='#1a1a1a'
        )
        self.status_label.pack(pady=(5, 10))
        
        self.lock_label = tk.Label(
            self.frame,
            text="",
            font=small_font,
            fg='#00ffff',
            bg='#1a1a1a',
            justify='left'
        )
        self.lock_label.pack(pady=(0, 5))
        
        self.last_update_time = 0
        
    def update_display(self, firing_solution, coord_status, player_locked=False, marker_locked=False, locked_player_coord=None, locked_marker_coord=None):
        """Update overlay display"""
        current_time = time.time()
        
        lock_text = []
        if player_locked and locked_player_coord:
            lock_text.append(f"🔒 PLAYER: {locked_player_coord}")
        else:
            lock_text.append("🔓 PLAYER UNLOCKED")
        
        if marker_locked and locked_marker_coord:
            lock_text.append(f"🔒 MARKER: {locked_marker_coord}")
        else:
            lock_text.append("🔓 MARKER UNLOCKED")
        
        self.lock_label.config(text="\n".join(lock_text), fg='#00ffff')
        
        if firing_solution:
            elevation = firing_solution.get('elevation', '---')
            unit = firing_solution.get('elevationUnit', 'mil')
            bearing = firing_solution.get('bearing', '---')
            weapon = firing_solution.get('weapon', '---')
            
            self.weapon_label.config(text=f"🎯 {weapon}", fg='#FFA500')
            self.elevation_label.config(text=f"ELEVATION: {elevation} {unit}", fg='#00ff00')
            self.bearing_label.config(text=f"BEARING: {bearing}°", fg='#00ff00')
            
            if current_time - self.last_update_time > 5:
                self.status_label.config(text="⚠️ Data may be outdated", fg='#ff8800')
            else:
                self.status_label.config(text="✓ Ready", fg='#00ff00')
        else:
            self.elevation_label.config(text="ELEVATION: ---", fg='#666666')
            self.bearing_label.config(text="BEARING: ---", fg='#666666')
        
        if coord_status:
            errors = []
            
            if not coord_status.get('player_detected', False):
                errors.append("PLAYER not detected")
            if not coord_status.get('marker_detected', False):
                errors.append("MARKER not detected")
            if not coord_status.get('player_full', False) and coord_status.get('player_detected', False):
                errors.append("PLAYER incomplete")
            if not coord_status.get('marker_full', False) and coord_status.get('marker_detected', False):
                errors.append("MARKER incomplete")
            
            if errors:
                color = '#ff0000' if any("not detected" in err for err in errors) else '#ff8800'
                error_text = " | ".join(errors)
                self.status_label.config(text=f"⚠️ {error_text}", fg=color)
            elif firing_solution:
                self.status_label.config(text="✓ Ready", fg='#00ff00')
                self.last_update_time = current_time
        
        self.root.update()
    
    def run(self):
        self.root.mainloop()


#####################################
# Main Program
#####################################
def on_player_unlock():
    global player_locked, locked_player_coord, manual_player_pos
    player_locked = False
    locked_player_coord = None
    manual_player_pos = None  # Manuel pozisyonu da sıfırla
    last_known_coords["player_full"] = None  # Önceki koordinatı da temizle
    last_known_coords["player_base"] = None  # Önceki taban koordinatını da temizle
    myOwnPrint("\n🔓 PLAYER UNLOCKED - Manual position cleared")


def on_marker_unlock():
    global marker_locked, locked_marker_coord, manual_marker_pos
    marker_locked = False
    locked_marker_coord = None
    manual_marker_pos = None  # Manuel pozisyonu da sıfırla
    last_known_coords["marker_full"] = None  # Önceki koordinatı da temizle
    last_known_coords["marker_base"] = None  # Önceki taban koordinatını da temizle
    myOwnPrint("\n🔓 MARKER UNLOCKED - Manual position cleared")


def on_abort():
    autoTargeting.abortDegrees()
    myOwnPrint("\n🛑 AUTO TARGETING ABORTED")
    autoTargeting.abortRadian()
    myOwnPrint("🛑 AUTO TARGETING ABORTED")


def on_auto_target():
    """END tuşuna basıldığında firing solution'ı oku ve auto targeting ile ayarla - PARALEL"""
    myOwnPrint("\n🎯 AUTO TARGETING ACTIVATED (END key pressed)")
    try:
        # firing_solution.json dosyasını oku
        firing_solution = read_firing_solution()
        
        if firing_solution is None:
            myOwnPrint("❌ Firing solution bulunamadı!")
            return
        
        elevation = firing_solution.get('elevation')
        bearing = firing_solution.get('bearing')
        
        if elevation is None or bearing is None:
            myOwnPrint("❌ Elevation veya bearing değeri bulunamadı!")
            return
        
        myOwnPrint(f"📊 Firing Solution:")
        myOwnPrint(f"   Elevation: {elevation:.2f} mil")
        myOwnPrint(f"   Bearing: {bearing:.2f}°")
        
        if(not autoTargeting.playersAreSetted):
            if(firing_solution.get('weapon')=="Mortar"):
                autoTargeting.initMortar()
            elif(firing_solution.get('weapon')=="BM-21Grad-UKRANIA"):
                autoTargeting.initUKRANIABm21Grad()
        
        
        
        # Thread fonksiyonları
        def set_elevation():
            if(firing_solution.get('weapon')=='Mortar'):
                elevation_int = int(round(elevation))
                if 800 <= elevation_int <= 1580:
                    myOwnPrint(f"\n🔧 [Thread-Elevation] Setting elevation to {elevation_int} mil...")
                    autoTargeting.calibrateRadian(elevation_int)
                    myOwnPrint(f"✅ [Thread-Elevation] Completed!")
                else:
                    myOwnPrint(f"⚠️ [Thread-Elevation] Elevation {elevation_int} aralık dışında (800-1580)!")
            elif(firing_solution.get('weapon')=='BM-21Grad-UKRANIA'):
                elevation_float = float(elevation)
                if 13.9 <= elevation_float <= 54.7:
                    myOwnPrint(f"\n🔧 [Thread-Elevation] Setting elevation to {elevation_float} mil...")
                    autoTargeting.calibrateBmDegree(elevation_float)
                    myOwnPrint(f"✅ [Thread-Elevation] Completed!")
                else:
                    myOwnPrint(f"⚠️ [Thread-Elevation] Elevation {elevation_float} aralık dışında (0.0-20.0)!")
        
        def set_bearing():
            if 0 <= bearing <= 360:
                myOwnPrint(f"\n🔧 [Thread-Bearing] Setting bearing to {bearing}°...")
                autoTargeting.calibrateDegrees(bearing)
                myOwnPrint(f"✅ [Thread-Bearing] Completed!")
            else:
                myOwnPrint(f"⚠️ [Thread-Bearing] Bearing {bearing} aralık dışında (0-360)!")
        
        # Thread'leri oluştur ve başlat
        elevation_thread = threading.Thread(target=set_elevation, name="ElevationThread")
        bearing_thread = threading.Thread(target=set_bearing, name="BearingThread")
        
        myOwnPrint("\n⚡ Starting parallel targeting...")
        elevation_thread.start()
        bearing_thread.start()
        
        # Her iki thread'in de bitmesini bekle
        elevation_thread.join()
        bearing_thread.join()
        
        myOwnPrint("\n✅ AUTO TARGETING COMPLETED (Both threads finished)!\n")
        
    except Exception as e:
        myOwnPrint(f"❌ Auto targeting hatası: {e}")
        import traceback
        traceback.print_exc()


def coordinate_reader_loop(overlay):
    """Main coordinate reading loop"""
    global manual_player_pos, manual_marker_pos
    
    myOwnPrint("=" * 60)
    myOwnPrint("SQUAD Coordinate Reader v11 - 100m GRID DETECTION")
    myOwnPrint("=" * 60)
    mode_text = "🤖 AUTO MODE (Shape Detection)" if DETECTION_MODE == 1 else "🎯 MANUAL MODE (Ctrl+Click)"
    myOwnPrint(f"\nCurrent Mode: {mode_text}")
    myOwnPrint("\n🎮 CONTROLS:")
    myOwnPrint("  Ctrl+' → Unlock PLAYER coordinate")
    myOwnPrint("  Ctrl+; → Unlock MARKER coordinate")
    if DETECTION_MODE == 2:
        myOwnPrint("  Ctrl+Middle Click → Mark PLAYER position")
        myOwnPrint("  Ctrl+Left Click → Mark MARKER position")
    myOwnPrint("  END → Auto Target (Set elevation & bearing from firing_solution.json)")
    myOwnPrint("  Ctrl+F4 → EXIT & CLOSE ALL")
    myOwnPrint("  Press Ctrl+C in terminal to stop\n")
    
    ctrl_pressed = False
    
    def for_canonical(f):
        return lambda k: f(keyboard_listener.canonical(k))
    
    # Exit hotkey (Ctrl+F4)
    def on_exit_hotkey():
        myOwnPrint("\n\n🛑 SHUTDOWN REQUESTED (Ctrl+F4)")
        myOwnPrint("   Closing overlay...")
        try:
            overlay.root.quit()
            overlay.root.destroy()
        except:
            pass
        import os
        os._exit(0)
    
    exit_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse('<ctrl>+<f4>'),
        on_exit_hotkey
    )
    
    player_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse("<ctrl>+'"),
        on_player_unlock
    )
    
    marker_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse('<ctrl>+;'),
        on_marker_unlock
    )
    
    # END tuşu için hotkey
    auto_target_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse('<end>'),
        on_auto_target
    )

    abort_hotkey = keyboard.HotKey(
        keyboard.HotKey.parse('x'),
        on_abort
    )
    
    def on_press(key):
        nonlocal ctrl_pressed
        exit_hotkey.press(keyboard_listener.canonical(key))
        player_hotkey.press(keyboard_listener.canonical(key))
        marker_hotkey.press(keyboard_listener.canonical(key))
        auto_target_hotkey.press(keyboard_listener.canonical(key))
        abort_hotkey.press(keyboard_listener.canonical(key))
        
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            ctrl_pressed = True
    
    def on_release(key):
        nonlocal ctrl_pressed
        exit_hotkey.release(keyboard_listener.canonical(key))
        player_hotkey.release(keyboard_listener.canonical(key))
        marker_hotkey.release(keyboard_listener.canonical(key))
        auto_target_hotkey.release(keyboard_listener.canonical(key))
        abort_hotkey.release(keyboard_listener.canonical(key))
        
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            ctrl_pressed = False
    
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    keyboard_listener.start()
    
    mouse_listener = None
    if DETECTION_MODE == 2:
        def on_mouse_click(x, y, button, pressed):
            global manual_player_pos, manual_marker_pos
            
            if pressed and ctrl_pressed:
                if button == mouse.Button.middle:
                    manual_player_pos = (x, y)
                    myOwnPrint(f"\n🎯 PLAYER manual position marked")
                    myOwnPrint(f"   Screen: ({x}, {y})")
                    myOwnPrint(f"   Map: ({x - SCENE_LEFT}, {y - SCENE_TOP})")
                
                elif button == mouse.Button.left:
                    manual_marker_pos = (x, y)
                    myOwnPrint(f"\n🎯 MARKER manual position marked")
                    myOwnPrint(f"   Screen: ({x}, {y})")
                    myOwnPrint(f"   Map: ({x - SCENE_LEFT}, {y - SCENE_TOP})")
        
        mouse_listener = mouse.Listener(on_click=on_mouse_click)
        mouse_listener.start()
    
    try:
        while True:
            myOwnPrint("-" * 60)
            
            coords = read_coordinates()
            
            coord_status = {
                'player_detected': False,
                'marker_detected': False,
                'player_full': False,
                'marker_full': False
            }
            
            if coords:
                save_to_json(coords)
                
                player_coord = coords.get('player', {}).get('full')
                marker_coord = coords.get('marker', {}).get('full')
                
                if player_coord:
                    coord_status['player_detected'] = True
                    if player_coord and len(player_coord.split('-')) >= 4:
                        coord_status['player_full'] = True
                
                if marker_coord:
                    coord_status['marker_detected'] = True
                    if marker_coord and len(marker_coord.split('-')) >= 4:
                        coord_status['marker_full'] = True
            else:
                myOwnPrint("Failed to read coordinates")
            
            firing_solution = read_firing_solution()
            
            try:
                overlay.update_display(firing_solution, coord_status, player_locked, marker_locked, locked_player_coord, locked_marker_coord)
            except:
                pass
            
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        myOwnPrint("\n\nStopped by user")
        keyboard_listener.stop()
        if mouse_listener:
            mouse_listener.stop()
    except Exception as e:
        myOwnPrint(f"\nError: {e}")
        keyboard_listener.stop()
        if mouse_listener:
            mouse_listener.stop()


if __name__ == "__main__":
    overlay = FiringSolutionOverlay()
    reader_thread = threading.Thread(target=coordinate_reader_loop, args=(overlay,), daemon=True)
    reader_thread.start()
    overlay.run()