"""
SQUAD Mortar System Launcher with Map Selection
Starts both Python coordinate reader and Node.js mortar calculator together
"""

import subprocess
import sys
import os
import time
import json
import tkinter as tk
from tkinter import ttk, font as tkfont, filedialog, messagebox
from pynput import keyboard
import config

# Config'den değişkenleri al
MAPS = config.MAPS
DEBUG_MODE = config.DEBUG_MODE

# Settings dosyası
SETTINGS_FILE = "user_settings.json"

def myOwnPrint(message):
    """Custom myOwnPrint function for debugging"""
    if DEBUG_MODE:
        print(message)

def load_user_settings():
    """Load user settings from JSON file"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            myOwnPrint(f"⚠️ Settings yüklenemedi: {e}")
    return None

def save_user_settings(settings):
    """Save user settings to JSON file"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        myOwnPrint(f"✅ Settings kaydedildi: {SETTINGS_FILE}")
        return True
    except Exception as e:
        myOwnPrint(f"❌ Settings kaydedilemedi: {e}")
        return False

def apply_settings_to_config(settings):
    """Apply loaded settings to config module"""
    if settings:
        config.SENSITIVITY = settings.get('sensitivity', 1.0)
        config.DPI_SCALE = settings.get('dpi_scale', 1.25)
        config.DETECTION_MODE = settings.get('detection_mode', 2)
        config.TESSERACT_PATH = settings.get('tesseract_path', r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        config.GAME_RESOLUTION = settings.get('resolution', "1920x1080")
        myOwnPrint("✅ Settings config'e uygulandı")

class SettingsGUI:
    def __init__(self, existing_settings=None):
        self.settings = None
        self.root = tk.Tk()
        self.root.title("SQUAD Mortar Calculator - Settings [Step 1/2]")
        self.root.geometry("700x650")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Colors
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        accent_color = "#4CAF50"
        
        self.root.configure(bg=bg_color)
        
        # Title
        title_font = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        title_label = tk.Label(
            self.root,
            text="⚙️ System Settings",
            font=title_font,
            bg=bg_color,
            fg=accent_color
        )
        title_label.pack(pady=(20, 10))
        
        subtitle_label = tk.Label(
            self.root,
            text="Configure your game settings",
            font=tkfont.Font(family="Segoe UI", size=10),
            bg=bg_color,
            fg="#888888"
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Main frame
        main_frame = tk.Frame(self.root, bg=bg_color)
        main_frame.pack(padx=40, pady=10, fill=tk.BOTH, expand=True)
        
        label_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        entry_font = tkfont.Font(family="Segoe UI", size=10)
        
        # Sensitivity
        self.create_label(main_frame, "🎯 Mouse Sensitivity (in-game):", label_font, bg_color, fg_color, 0)
        self.sensitivity_var = tk.StringVar(value=str(existing_settings.get('sensitivity', 1.0) if existing_settings else 1.0))
        self.create_entry(main_frame, self.sensitivity_var, entry_font, bg_color, fg_color, 1)
        
        # DPI Scale
        self.create_label(main_frame, "🖱️ DPI Scale:", label_font, bg_color, fg_color, 2)
        self.dpi_var = tk.StringVar(value=str(existing_settings.get('dpi_scale', 1.25) if existing_settings else 1.25))
        self.create_entry(main_frame, self.dpi_var, entry_font, bg_color, fg_color, 3)
        
        # Resolution
        self.create_label(main_frame, "🖥️ Game Resolution:", label_font, bg_color, fg_color, 4)
        resolution_frame = tk.Frame(main_frame, bg=bg_color)
        resolution_frame.grid(row=5, column=0, sticky=tk.W, pady=(5, 15))
        
        resolutions = ["1920x1080", "2560x1440", "3840x2160", "1280x720"]
        current_res = existing_settings.get('resolution', "1920x1080") if existing_settings else "1920x1080"
        self.resolution_var = tk.StringVar(value=current_res)
        
        for res in resolutions:
            rb = tk.Radiobutton(
                resolution_frame,
                text=res,
                variable=self.resolution_var,
                value=res,
                font=entry_font,
                bg=bg_color,
                fg=fg_color,
                selectcolor="#3d3d3d",
                activebackground=bg_color,
                activeforeground=fg_color
            )
            rb.pack(side=tk.LEFT, padx=10)
        
        # Detection Mode
        self.create_label(main_frame, "🔍 Detection Mode:", label_font, bg_color, fg_color, 6)
        mode_frame = tk.Frame(main_frame, bg=bg_color)
        mode_frame.grid(row=7, column=0, sticky=tk.W, pady=(5, 15))
        
        current_mode = existing_settings.get('detection_mode', 2) if existing_settings else 2
        self.mode_var = tk.IntVar(value=current_mode)
        
        tk.Radiobutton(
            mode_frame,
            text="1 - AUTO (Shape detection)",
            variable=self.mode_var,
            value=1,
            font=entry_font,
            bg=bg_color,
            fg=fg_color,
            selectcolor="#3d3d3d",
            activebackground=bg_color,
            activeforeground=fg_color
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Radiobutton(
            mode_frame,
            text="2 - MANUAL (Ctrl+Click)",
            variable=self.mode_var,
            value=2,
            font=entry_font,
            bg=bg_color,
            fg=fg_color,
            selectcolor="#3d3d3d",
            activebackground=bg_color,
            activeforeground=fg_color
        ).pack(side=tk.LEFT, padx=10)
        
        # Tesseract Path
        self.create_label(main_frame, "📂 Tesseract OCR Path:", label_font, bg_color, fg_color, 8)
        path_frame = tk.Frame(main_frame, bg=bg_color)
        path_frame.grid(row=9, column=0, sticky=tk.EW, pady=(5, 15))
        
        main_frame.columnconfigure(0, weight=1)  # Make column expandable
        
        current_path = existing_settings.get('tesseract_path', r"C:\Program Files\Tesseract-OCR\tesseract.exe") if existing_settings else r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        self.tesseract_var = tk.StringVar(value=current_path)
        
        tesseract_entry = tk.Entry(
            path_frame,
            textvariable=self.tesseract_var,
            font=entry_font,
            bg="#3d3d3d",
            fg=fg_color,
            insertbackground=fg_color,
            relief=tk.FLAT,
            width=50
        )
        tesseract_entry.pack(side=tk.LEFT, ipady=5, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_btn = tk.Button(
            path_frame,
            text="📁",
            font=tkfont.Font(family="Segoe UI", size=12),
            bg="#3d3d3d",
            fg=fg_color,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.browse_tesseract,
            width=3
        )
        browse_btn.pack(side=tk.LEFT)
        
        # Save button (moved to bottom with proper spacing)
        button_frame = tk.Frame(self.root, bg=bg_color)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=40, pady=20)
        
        save_button = tk.Button(
            button_frame,
            text="💾 SAVE & RETURN",
            font=tkfont.Font(family="Segoe UI", size=12, weight="bold"),
            bg=accent_color,
            fg="#ffffff",
            activebackground="#45a049",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.on_save,
            height=2
        )
        save_button.pack(fill=tk.X)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_label(self, parent, text, font, bg, fg, row):
        label = tk.Label(parent, text=text, font=font, bg=bg, fg=fg, anchor=tk.W)
        label.grid(row=row, column=0, sticky=tk.W, pady=(10, 5))
    
    def create_entry(self, parent, var, font, bg, fg, row):
        entry = tk.Entry(
            parent,
            textvariable=var,
            font=font,
            bg="#3d3d3d",
            fg=fg,
            insertbackground=fg,
            relief=tk.FLAT,
            width=20
        )
        entry.grid(row=row, column=0, sticky=tk.W, pady=(5, 15), ipady=5)
    
    def browse_tesseract(self):
        filename = filedialog.askopenfilename(
            title="Select Tesseract Executable",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if filename:
            self.tesseract_var.set(filename)
    
    def on_save(self):
        try:
            # Validate inputs
            sensitivity = float(self.sensitivity_var.get())
            dpi_scale = float(self.dpi_var.get())
            
            if sensitivity <= 0 or dpi_scale <= 0:
                messagebox.showerror("Error", "Sensitivity ve DPI Scale pozitif olmalı!")
                return
            
            self.settings = {
                'sensitivity': sensitivity,
                'dpi_scale': dpi_scale,
                'detection_mode': self.mode_var.get(),
                'tesseract_path': self.tesseract_var.get(),
                'resolution': self.resolution_var.get()
            }
            
            self.root.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Lütfen geçerli sayısal değerler girin!")
    
    def on_close(self):
        self.settings = None
        try:
            self.root.destroy()
        except:
            pass
    
    def show(self):
        try:
            self.root.mainloop()
        except:
            pass
        return self.settings

# Global variable to store selected map (for EXE compatibility)
_selected_map = None

class MapSelectorGUI:
    def __init__(self, show_settings_button=True):
        self.selected_map = None
        self.selected_weapon = None
        self.open_settings = False
        self.show_settings_button = show_settings_button
        self.root = tk.Tk()
        self.root.title("SQUAD Mortar Calculator - Map Selection")
        self.root.geometry("500x680")
        self.root.resizable(False, False)
        
        # Use StringVar to store selection (more reliable in EXE)
        self.map_var = tk.StringVar(value="")
        
        # Center window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Configure colors
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        accent_color = "#4CAF50"
        
        self.root.configure(bg=bg_color)
        
        # Title
        title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        title_label = tk.Label(
            self.root,
            text="🎯 SQUAD Mortar Calculator",
            font=title_font,
            bg=bg_color,
            fg=accent_color
        )
        title_label.pack(pady=(20, 10))
        
        # Subtitle
        subtitle_font = tkfont.Font(family="Segoe UI", size=11)
        subtitle_label = tk.Label(
            self.root,
            text="Select Your Map & Weapon to Start",
            font=subtitle_font,
            bg=bg_color,
            fg=fg_color
        )
        subtitle_label.pack(pady=(0, 15))
        
        # Weapon Selection
        weapon_frame = tk.Frame(self.root, bg=bg_color)
        weapon_frame.pack(pady=(0, 15), padx=20, fill=tk.X)
        
        weapon_label = tk.Label(
            weapon_frame,
            text="🎯 Weapon Type:",
            font=tkfont.Font(family="Segoe UI", size=11, weight="bold"),
            bg=bg_color,
            fg=accent_color
        )
        weapon_label.pack(side=tk.LEFT, padx=(0, 15))
        
        self.weapon_var = tk.StringVar(value=config.DEFAULT_WEAPON)
        weapon_combo = ttk.Combobox(
            weapon_frame,
            textvariable=self.weapon_var,
            values=config.AVAILABLE_WEAPONS,
            font=tkfont.Font(family="Segoe UI", size=10),
            state="readonly",
            width=25
        )
        weapon_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        weapon_combo.current(0)  # Select first weapon by default
        
        # Settings button (if enabled)
        if self.show_settings_button:
            settings_btn = tk.Button(
                self.root,
                text="⚙️ System Settings",
                font=tkfont.Font(family="Segoe UI", size=10),
                bg="#3d3d3d",
                fg=fg_color,
                activebackground="#4d4d4d",
                activeforeground=fg_color,
                relief=tk.FLAT,
                cursor="hand2",
                command=self.on_settings_click,
                width=20
            )
            settings_btn.pack(pady=(0, 10))
        
        # Search frame
        search_frame = tk.Frame(self.root, bg=bg_color)
        search_frame.pack(pady=(0, 10), padx=20, fill=tk.X)
        
        search_label = tk.Label(
            search_frame,
            text="🔍 Search:",
            font=subtitle_font,
            bg=bg_color,
            fg=fg_color
        )
        search_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_maps)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=subtitle_font,
            bg="#3d3d3d",
            fg=fg_color,
            insertbackground=fg_color,
            relief=tk.FLAT,
            width=30
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        
        # Listbox frame with scrollbar
        list_frame = tk.Frame(self.root, bg=bg_color)
        list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        list_font = tkfont.Font(family="Consolas", size=11)
        self.listbox = tk.Listbox(
            list_frame,
            font=list_font,
            bg="#3d3d3d",
            fg=fg_color,
            selectbackground=accent_color,
            selectforeground="#ffffff",
            relief=tk.FLAT,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
            activestyle='none'
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate listbox
        for map_name in MAPS:
            self.listbox.insert(tk.END, f"  📍 {map_name}")
        
        # Select default (Jensen - index 9)
        self.listbox.select_set(9)
        self.listbox.see(9)
        
        # Double-click to start
        self.listbox.bind('<Double-Button-1>', lambda e: self.on_start())
        
        # Button frame
        button_frame = tk.Frame(self.root, bg=bg_color)
        button_frame.pack(pady=20, padx=20, fill=tk.X)
        
        # Start button
        start_button = tk.Button(
            button_frame,
            text="🚀 START SYSTEM",
            font=tkfont.Font(family="Segoe UI", size=12, weight="bold"),
            bg=accent_color,
            fg="#ffffff",
            activebackground="#45a049",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.on_start,
            height=2
        )
        start_button.pack(fill=tk.X)
        
        # Info label
        info_font = tkfont.Font(family="Segoe UI", size=9)
        info_label = tk.Label(
            self.root,
            text="Double-click on a map or press START button",
            font=info_font,
            bg=bg_color,
            fg="#888888"
        )
        info_label.pack(pady=(0, 10))
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def filter_maps(self, *args):
        """Filter maps based on search input"""
        search_text = self.search_var.get().lower()
        self.listbox.delete(0, tk.END)
        
        for map_name in MAPS:
            if search_text in map_name.lower():
                self.listbox.insert(tk.END, f"  📍 {map_name}")
        
        if self.listbox.size() > 0:
            self.listbox.select_set(0)
    
    def on_settings_click(self):
        """Handle settings button click"""
        self.open_settings = True
        self.selected_map = None
        try:
            self.root.destroy()
        except:
            pass
    
    def on_start(self):
        """Handle start button click"""
        global _selected_map
        selection = self.listbox.curselection()
        if selection:
            selected_text = self.listbox.get(selection[0])
            # Remove icon and spaces
            map_name = selected_text.replace("📍", "").strip()
            
            # Store in multiple places for reliability
            self.selected_map = map_name
            self.map_var.set(map_name)
            _selected_map = map_name
            self.selected_weapon = self.weapon_var.get()
            self.open_settings = False
            
            myOwnPrint(f"   Selected Map: {map_name}")
            myOwnPrint(f"   Selected Weapon: {self.selected_weapon}")
            myOwnPrint(f"   DEBUG: Instance var: {self.selected_map}")
            myOwnPrint(f"   DEBUG: StringVar: {self.map_var.get()}")
            myOwnPrint(f"   DEBUG: Global: {_selected_map}")
            
            # Destroy root immediately - don't use quit
            self.root.destroy()
    
    def on_close(self):
        """Handle window close"""
        global _selected_map
        _selected_map = None
        self.selected_map = None
        self.map_var.set("")
        self.open_settings = False
        try:
            self.root.destroy()
        except:
            pass
    
    def show(self):
        """Show the GUI and return (selected_map, selected_weapon, open_settings_flag)"""
        global _selected_map
        
        try:
            self.root.mainloop()
        except:
            pass
        
        # Check if settings button was clicked
        if self.open_settings:
            return None, None, True
        
        # Try to get the selected map from multiple sources
        result = None
        
        # Try global first
        if _selected_map:
            result = _selected_map
            myOwnPrint(f"   DEBUG: Got from global: {result}")
        # Then StringVar
        elif self.map_var.get():
            result = self.map_var.get()
            myOwnPrint(f"   DEBUG: Got from StringVar: {result}")
        # Finally instance var
        elif self.selected_map:
            result = self.selected_map
            myOwnPrint(f"   DEBUG: Got from instance: {result}")
        
        myOwnPrint(f"   DEBUG: Final result: {result}")
        
        # Get weapon selection
        weapon = self.selected_weapon or self.weapon_var.get() or config.DEFAULT_WEAPON
        
        return result, weapon, False

def get_map_selection(show_settings_button=True):
    """Get map and weapon selection from user using GUI"""
    gui = MapSelectorGUI(show_settings_button=show_settings_button)
    selected_map, selected_weapon, open_settings = gui.show()
    
    myOwnPrint(f"DEBUG: Returned map = {selected_map}, weapon = {selected_weapon}, open_settings = {open_settings}")
    
    if open_settings:
        return None, None, True
    
    if not selected_map:
        myOwnPrint("❌ No map selected. Exiting...")
        sys.exit(0)
    
    return selected_map, selected_weapon, False

def main():
    # Load existing settings if available
    myOwnPrint("\n" + "=" * 70)
    myOwnPrint("SQUAD Mortar Calculator - Initialization")
    myOwnPrint("=" * 70)
    
    settings = load_user_settings()
    
    if settings:
        myOwnPrint(f"\n✅ Kaydedilmiş ayarlar yüklendi:")
        myOwnPrint(f"   • Sensitivity: {settings.get('sensitivity')}")
        myOwnPrint(f"   • DPI Scale: {settings.get('dpi_scale')}")
        myOwnPrint(f"   • Detection Mode: {settings.get('detection_mode')}")
        myOwnPrint(f"   • Resolution: {settings.get('resolution')}")
        apply_settings_to_config(settings)
    else:
        myOwnPrint("\n⚠️ İlk çalıştırma - varsayılan ayarlar kullanılıyor")
    
    # Main loop: Show map selection first, optionally open settings
    while True:
        myOwnPrint("\n" + "=" * 70)
        myOwnPrint("Map & Weapon Selection")
        myOwnPrint("=" * 70 + "\n")
        
        # Show map selector (with settings button)
        selected_map, selected_weapon, open_settings = get_map_selection(show_settings_button=True)
        
        # If settings button clicked, show settings GUI
        if open_settings:
            myOwnPrint("\n" + "=" * 70)
            myOwnPrint("System Settings")
            myOwnPrint("=" * 70 + "\n")
            
            # Load current settings
            settings = load_user_settings()
            
            # Show settings GUI
            settings_gui = SettingsGUI(existing_settings=settings)
            new_settings = settings_gui.show()
            
            if new_settings:
                settings = new_settings
                save_user_settings(settings)
                apply_settings_to_config(settings)
                myOwnPrint("\n✅ Ayarlar güncellendi!")
            else:
                myOwnPrint("\n⚠️ Ayarlar iptal edildi, mevcut ayarlar korundu")
            
            # Return to map selection
            continue
        
        # Map selected, proceed to start
        break
    
    myOwnPrint("=" * 70)
    myOwnPrint("SQUAD Mortar Calculator System")
    myOwnPrint("=" * 70)
    myOwnPrint(f"\n✅ Selected Map: {selected_map}")
    myOwnPrint(f"✅ Selected Weapon: {selected_weapon}")
    
    # Save weapon to config
    config.DEFAULT_WEAPON = selected_weapon
    myOwnPrint(f"✅ Weapon saved to config: {config.DEFAULT_WEAPON}")
    
    myOwnPrint("=" * 70)
    myOwnPrint("\n")
    
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if running as EXE or script
    if getattr(sys, 'frozen', False):
        # Running as EXE - get the directory where EXE is located
        current_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        current_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # Start Node.js mortar calculator in background with selected map (NO CONSOLE WINDOW)
        myOwnPrint(f"🚀 Starting Node.js mortar calculator for {selected_map}...")
        
        # CREATE_NO_WINDOW flag to hide console (Windows only)
        CREATE_NO_WINDOW = 0x08000000
        
        # Check if Node.js is available
        try:
            node_check = subprocess.run(["node", "--version"], capture_output=True, text=True)
            myOwnPrint(f"   Node.js version: {node_check.stdout.strip()}")
        except Exception as e:
            myOwnPrint(f"   ⚠️ Warning: Could not detect Node.js: {e}")
        
        node_script_path = os.path.join(current_dir, "useLegacyMode.js")
        myOwnPrint(f"   Script path: {node_script_path}")
        myOwnPrint(f"   Working dir: {current_dir}")
        
        # Use weapon from map selection
        weapon = selected_weapon
        myOwnPrint(f"   Using weapon: {weapon}")
        
        node_process = subprocess.Popen(
            ["node", node_script_path, selected_map, weapon],
            cwd=current_dir,
            creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        myOwnPrint(f"✅ Node.js calculator started in background (PID: {node_process.pid})")
        myOwnPrint(f"   Map: {selected_map}")
        myOwnPrint(f"   Weapon: {weapon}")
        myOwnPrint("\n")
        
        time.sleep(2)  # Wait a bit for Node.js to initialize
        
        # Start Python coordinate reader (this will be the main process)
        myOwnPrint("🚀 Starting coordinate reader with overlay...")
        myOwnPrint("=" * 70)
        myOwnPrint("\n")
        
        if getattr(sys, 'frozen', False):
            # Running as EXE - import and run directly (no subprocess)
            myOwnPrint("Running in EXE mode - importing SmartCordinateMouseOverride directly...")
            
            # Add current directory to path if not already there
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            try:
                # Import the coordinate reader module
                import SmartCordinateMouseOverride
                import threading
                
                myOwnPrint("✅ Coordinate reader module imported successfully")
                myOwnPrint("\n")
                
                # Setup Ctrl+F4 exit hotkey - GLOBAL listener (works regardless of focus)
                def on_exit_hotkey():
                    myOwnPrint("\n\n🛑 SHUTDOWN REQUESTED (Ctrl+F4)")
                    myOwnPrint("   Closing system...")
                    try:
                        node_process.terminate()
                        myOwnPrint("   ✅ Node.js stopped")
                    except:
                        pass
                    try:
                        # Close overlay window
                        overlay.root.quit()
                        overlay.root.destroy()
                    except:
                        pass
                    try:
                        sys.exit(0)
                    except:
                        os._exit(0)
                
                exit_hotkey = keyboard.HotKey(
                    keyboard.HotKey.parse('<ctrl>+<f4>'),
                    on_exit_hotkey
                )
                
                def on_press(key):
                    exit_hotkey.press(key)
                
                def on_release(key):
                    exit_hotkey.release(key)
                
                # Start GLOBAL keyboard listener (daemon thread)
                keyboard_listener = keyboard.Listener(
                    on_press=on_press,
                    on_release=on_release
                )
                keyboard_listener.daemon = True
                keyboard_listener.start()
                
                myOwnPrint("\n🎮 Press Ctrl+F4 ANYWHERE to EXIT & CLOSE ALL\n")
                
                # Create overlay window (from SmartCordinateMouseOverride)
                overlay = SmartCordinateMouseOverride.FiringSolutionOverlay()
                
                # Start coordinate reading in background thread
                reader_thread = threading.Thread(
                    target=SmartCordinateMouseOverride.coordinate_reader_loop,
                    args=(overlay,),
                    daemon=True
                )
                reader_thread.start()
                
                # Run overlay window (this blocks until window is closed)
                overlay.run()
                
            except ImportError as e:
                myOwnPrint(f"❌ Could not import SmartCordinateMouseOverride: {e}")
                myOwnPrint("   Make sure the file is included in the EXE build")
                raise
            except Exception as e:
                myOwnPrint(f"❌ Error running coordinate reader: {e}")
                import traceback
                traceback.print_exc()
                raise
        else:
            # Running as script - use subprocess as before
            python_exe = sys.executable
            coordinate_script = os.path.join(current_dir, "SmartCordinateMouseOverride.py")
            
            myOwnPrint(f"Running: {python_exe} {coordinate_script}")
            
            # Run in foreground so we can see output
            result = subprocess.run(
                [python_exe, coordinate_script],
                cwd=current_dir
            )
        
        # When coordinate reader exits, stop Node.js
        myOwnPrint("\n\n⚠️ Coordinate reader stopped. Shutting down Node.js...")
        if 'node_process' in locals():
            node_process.terminate()
            myOwnPrint("✅ Node.js process stopped")
        
    except KeyboardInterrupt:
        myOwnPrint("\n\n⚠️ Shutting down...")
        if 'node_process' in locals():
            node_process.terminate()
            myOwnPrint("✅ Node.js process stopped")
    except Exception as e:
        myOwnPrint(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if 'node_process' in locals():
            node_process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    main()
