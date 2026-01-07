#!/usr/bin/env python3
"""
QRGenPro - Professional QR Code Generator
A modern, feature-rich QR code generator with premium UI and robust features.

Features:
- Live debounced preview
- All presets (WiFi, Email, Phone, Website, vCard, SMS, Geo)
- Logo embedding with auto ECC bump
- Transparent background with visual indicator
- Batch generation with progress
- Settings persistence
- Keyboard shortcuts
- SVG/PNG/JPEG export
- Copy to clipboard (text + image)
- Drag & drop logo support
- Premium modern UI with proper spacing/typography
"""

import os
import re
import sys
import json
import io
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urlparse, quote

import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image, ImageQt, ImageColor
import traceback
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QSettings


# =============================================================================
# THEME SYSTEM
# =============================================================================
@dataclass
class Theme:
    name: str
    bg: str
    surface: str
    card: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_hover: str
    success: str
    error: str
    warning: str


THEMES = {
    "dark": Theme(
        name="Dark",
        bg="#1a1a2e",
        surface="#16213e",
        card="#0f0f23",
        border="#2d3561",
        text_primary="#e8e8e8",
        text_secondary="#a0a0b0",
        accent="#4f8cff",
        accent_hover="#6ba3ff",
        success="#4ade80",
        error="#f87171",
        warning="#fbbf24",
    ),
    "light": Theme(
        name="Light",
        bg="#f5f7fa",
        surface="#ffffff",
        card="#ffffff",
        border="#e2e8f0",
        text_primary="#1e293b",
        text_secondary="#64748b",
        accent="#3b82f6",
        accent_hover="#2563eb",
        success="#22c55e",
        error="#ef4444",
        warning="#f59e0b",
    ),
}

ERROR_LEVELS = {
    "L - 7% (Fast)": ERROR_CORRECT_L,
    "M - 15% (Standard)": ERROR_CORRECT_M,
    "Q - 25% (High)": ERROR_CORRECT_Q,
    "H - 30% (Maximum)": ERROR_CORRECT_H,
}


# =============================================================================
# CONFIGURATION
# =============================================================================
@dataclass
class QRConfig:
    content: str = ""
    box_size: int = 10
    error_correction: str = "M - 15% (Standard)"
    qr_color: str = "#000000"
    bg_color: str = "#ffffff"
    transparent_bg: bool = False
    auto_optimize: bool = True
    quiet_zone: bool = True
    logo_path: str = ""


@dataclass
class AppSettings:
    theme: str = "dark"
    output_dir: str = ""
    last_format: str = "PNG"
    naming_template: str = "qr_code_{index}"
    target_size: int = 10
    window_geometry: str = ""
    
    def __post_init__(self):
        if not self.output_dir:
            self.output_dir = str(Path.home() / "Desktop")


# =============================================================================
# QR GENERATOR ENGINE
# =============================================================================
class QREngine:
    """Stateless QR generation engine with all the core logic."""
    
    @staticmethod
    def generate(config: QRConfig) -> Image.Image:
        """Generate QR image with background extraction for transparency."""
        if not config.content.strip():
            raise ValueError("Content cannot be empty")
        
        # 1. Determine Error Correction
        ecc = ERROR_LEVELS.get(config.error_correction, ERROR_CORRECT_M)
        if config.logo_path and os.path.exists(config.logo_path):
            if ecc < ERROR_CORRECT_Q:
                ecc = ERROR_CORRECT_Q
        
        # 2. Generate QR Matrix normally (solid background)
        qr = qrcode.QRCode(
            version=None if config.auto_optimize else 4,
            error_correction=ecc,
            box_size=config.box_size,
            border=4 if config.quiet_zone else 1,
        )
        qr.add_data(config.content)
        qr.make(fit=True)
        
        # Use qrcode's standard renderer first (safest)
        # We always render with a background, then remove it if needed
        img = qr.make_image(
            fill_color=config.qr_color,
            back_color=config.bg_color
        ).convert("RGBA")
        
        # 3. Apply Transparency via Background Extraction
        if config.transparent_bg:
            datas = img.getdata()
            new_data = []
            
            # Determine the target background color (RGB) to remove
            # We use the config's bg_color, parsed by PIL
            bg_rgb = ImageColor.getrgb(config.bg_color)
            
            # Tolerance for removal (exact match usually works for QR, but we allow small delta)
            tolerance = 0
            
            for item in datas:
                # item is (r, g, b, a)
                if (abs(item[0] - bg_rgb[0]) <= tolerance and
                    abs(item[1] - bg_rgb[1]) <= tolerance and
                    abs(item[2] - bg_rgb[2]) <= tolerance):
                    # Replace with full transparency
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            
            img.putdata(new_data)
        
        # 4. Add logo if present
        if config.logo_path and os.path.exists(config.logo_path):
            img = QREngine.add_logo(img, config.logo_path)
        
        return img
    
    @staticmethod
    def add_logo(qr_img: Image.Image, logo_path: str) -> Image.Image:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            w, h = qr_img.size
            max_dim = int(min(w, h) * 0.22)
            logo.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            # Create white background pad for logo
            pad_size = (logo.size[0] + 8, logo.size[1] + 8)
            pad = Image.new("RGBA", pad_size, (255, 255, 255, 255))
            pad.paste(logo, (4, 4), logo)
            
            pos = ((w - pad.size[0]) // 2, (h - pad.size[1]) // 2)
            result = qr_img.copy()
            result.paste(pad, pos, pad)
            return result
        except Exception:
            return qr_img
    
    @staticmethod
    def validate_url(text: str) -> bool:
        try:
            p = urlparse(text)
            return bool(p.scheme and p.netloc)
        except Exception:
            return False


# =============================================================================
# PRESET GENERATORS
# =============================================================================
class Presets:
    @staticmethod
    def wifi(ssid: str, password: str = "", security: str = "WPA", hidden: bool = False) -> str:
        if not ssid:
            raise ValueError("SSID is required")
        sec = security if password else "nopass"
        hidden_str = "true" if hidden else "false"
        return f"WIFI:T:{sec};S:{ssid};P:{password};H:{hidden_str};;"
    
    @staticmethod
    def email(address: str, subject: str = "", body: str = "") -> str:
        if not address:
            raise ValueError("Email address is required")
        params = []
        if subject:
            params.append(f"subject={quote(subject)}")
        if body:
            params.append(f"body={quote(body)}")
        query = ("?" + "&".join(params)) if params else ""
        return f"mailto:{address}{query}"
    
    @staticmethod
    def phone(number: str) -> str:
        if not number:
            raise ValueError("Phone number is required")
        clean = re.sub(r"[^\d+]", "", number)
        return f"tel:{clean}"
    
    @staticmethod
    def sms(number: str, message: str = "") -> str:
        if not number:
            raise ValueError("Phone number is required")
        clean = re.sub(r"[^\d+]", "", number)
        if message:
            return f"sms:{clean}?body={quote(message)}"
        return f"sms:{clean}"
    
    @staticmethod
    def website(url: str) -> str:
        if not url:
            raise ValueError("URL is required")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url
    
    @staticmethod
    def vcard(name: str, phone: str = "", email: str = "", org: str = "", title: str = "") -> str:
        if not name:
            raise ValueError("Name is required")
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"FN:{name}",
        ]
        if phone:
            lines.append(f"TEL:{phone}")
        if email:
            lines.append(f"EMAIL:{email}")
        if org:
            lines.append(f"ORG:{org}")
        if title:
            lines.append(f"TITLE:{title}")
        lines.append("END:VCARD")
        return "\n".join(lines)
    
    @staticmethod
    def geo(latitude: float, longitude: float) -> str:
        return f"geo:{latitude},{longitude}"


# =============================================================================
# BATCH WORKER
# =============================================================================
class BatchWorker(QThread):
    progress = Signal(int, int, str)  # current, total, item
    finished = Signal(int, int)  # success, failed
    error = Signal(str)
    
    def __init__(self, items: list, config: QRConfig, output_dir: Path, 
                 naming: str, fmt: str):
        super().__init__()
        self.items = items
        self.config = config
        self.output_dir = output_dir
        self.naming = naming
        self.fmt = fmt
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def run(self):
        success = 0
        failed = 0
        total = len(self.items)
        
        for idx, item in enumerate(self.items, 1):
            if self._stop:
                break
            
            try:
                cfg = QRConfig(
                    content=item,
                    box_size=self.config.box_size,
                    error_correction=self.config.error_correction,
                    qr_color=self.config.qr_color,
                    bg_color=self.config.bg_color,
                    transparent_bg=self.config.transparent_bg,
                    auto_optimize=self.config.auto_optimize,
                    quiet_zone=self.config.quiet_zone,
                    logo_path=self.config.logo_path,
                )
                img = QREngine.generate(cfg)
                
                safe_content = re.sub(r"[^\w\-]", "_", item[:20])
                name = self.naming.format(index=idx, content=safe_content)
                ext = ".png" if self.fmt == "PNG" else ".jpg"
                if not name.lower().endswith(ext):
                    name += ext
                
                path = self.output_dir / name
                if self.fmt == "PNG":
                    img.save(str(path), "PNG")
                else:
                    img.convert("RGB").save(str(path), "JPEG", quality=95)
                
                success += 1
            except Exception as e:
                failed += 1
                self.error.emit(f"Failed: {item[:30]}... - {e}")
            
            self.progress.emit(idx, total, item[:40])
        
        self.finished.emit(success, failed)


# =============================================================================
# STYLE MANAGER
# =============================================================================
class StyleManager:
    """Centralized styling for the entire application."""
    
    def __init__(self, theme: Theme):
        self.theme = theme
    
    def get_app_stylesheet(self) -> str:
        t = self.theme
        return f"""
            QMainWindow, QWidget {{
                background-color: {t.bg};
                color: {t.text_primary};
                font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
                font-size: 13px;
            }}
            
            QGroupBox {{
                background-color: {t.card};
                border: 1px solid {t.border};
                border-radius: 10px;
                margin-top: 14px;
                padding: 20px 16px 16px 16px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 4px 10px;
                color: {t.accent};
                font-size: 12px;
                font-weight: 600;
            }}
            
            QLabel {{
                color: {t.text_primary};
                padding: 2px;
            }}
            QLabel[class="secondary"] {{
                color: {t.text_secondary};
                font-size: 12px;
            }}
            
            QLineEdit, QPlainTextEdit, QTextEdit {{
                background-color: {t.surface};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 10px 12px;
                color: {t.text_primary};
                selection-background-color: {t.accent};
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
                border-color: {t.accent};
            }}
            
            QPushButton {{
                background-color: {t.surface};
                border: 1px solid {t.border};
                border-radius: 6px;
                padding: 8px 14px;
                color: {t.text_primary};
                font-weight: 500;
                min-height: 18px;
            }}
            QPushButton:hover {{
                background-color: {t.border};
                border-color: {t.accent};
            }}
            QPushButton:pressed {{
                background-color: {t.accent};
                color: white;
            }}
            QPushButton[class="primary"] {{
                background-color: {t.accent};
                border: none;
                color: white;
                font-weight: 600;
            }}
            QPushButton[class="primary"]:hover {{
                background-color: {t.accent_hover};
            }}
            
            QComboBox {{
                background-color: {t.surface};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 8px 12px;
                color: {t.text_primary};
                min-width: 120px;
            }}
            QComboBox:hover {{
                border-color: {t.accent};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {t.card};
                border: 1px solid {t.border};
                border-radius: 8px;
                selection-background-color: {t.accent};
            }}
            
            QSlider::groove:horizontal {{
                background: {t.border};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {t.accent};
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {t.accent_hover};
            }}
            
            QCheckBox {{
                spacing: 8px;
                color: {t.text_primary};
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid {t.border};
                background: {t.surface};
            }}
            QCheckBox::indicator:checked {{
                background: {t.accent};
                border-color: {t.accent};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {t.border};
                border-radius: 12px;
                background: {t.card};
            }}
            QTabBar::tab {{
                background: {t.surface};
                border: 1px solid {t.border};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                margin-right: 4px;
                color: {t.text_secondary};
            }}
            QTabBar::tab:selected {{
                background: {t.card};
                color: {t.accent};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: {t.border};
            }}
            
            QProgressBar {{
                background: {t.surface};
                border: 1px solid {t.border};
                border-radius: 6px;
                height: 12px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {t.accent};
                border-radius: 5px;
            }}
            
            QScrollBar:vertical {{
                background: {t.surface};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.border};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t.accent};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """


# =============================================================================
# PREVIEW WIDGET WITH CHECKERBOARD FOR TRANSPARENCY
# =============================================================================
class PreviewWidget(QtWidgets.QLabel):
    """Custom preview label with checkerboard background for transparency."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(280, 280)
        self._pixmap = None
        self._show_checker = False
        self._checker_cache = None
    
    def set_qr_pixmap(self, pixmap: QtGui.QPixmap, transparent: bool = False):
        self._pixmap = pixmap
        self._show_checker = transparent
        self.update()
    
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 1. Fill widget with a VERY dark color to prove transparency
        painter.fillRect(rect, QtGui.QColor("#050505")) 
        
        if self._pixmap:
            pw, ph = self._pixmap.width(), self._pixmap.height()
            px = (rect.width() - pw) // 2
            py = (rect.height() - ph) // 2
            target_rect = QtCore.QRect(px, py, pw, ph)
            
            # 2. Draw checkerboard ONLY if transparency is on
            if self._show_checker:
                self._draw_checkerboard(painter, target_rect)
            
            # 3. Draw the pixmap (should have alpha channel)
            painter.drawPixmap(px, py, self._pixmap)
            
            # 4. Subtle border to show bounds
            painter.setPen(QtGui.QColor(255, 255, 255, 40))
            painter.drawRect(target_rect.adjusted(-1, -1, 0, 0))
            
        elif not self._pixmap:
            painter.setPen(QtGui.QColor("#64748b"))
            painter.drawText(rect, Qt.AlignCenter, "Generate to preview")
        
        painter.end()
    
    def _draw_checkerboard(self, painter: QtGui.QPainter, rect):
        size = 12
        # Use very distinct colors: Dark Gray and Slightly Lighter Gray
        c1 = QtGui.QColor(60, 60, 60)
        c2 = QtGui.QColor(90, 90, 90)
        
        painter.save()
        painter.setClipRect(rect)
        for y in range(rect.top(), rect.bottom(), size):
            for x in range(rect.left(), rect.right(), size):
                if ((x - rect.left()) // size + (y - rect.top()) // size) % 2 == 0:
                    painter.fillRect(x, y, size, size, c1)
                else:
                    painter.fillRect(x, y, size, size, c2)
        painter.restore()


# =============================================================================
# MAIN WINDOW
# =============================================================================
class NeoQRPro(QtWidgets.QMainWindow):
    """Main application window with modern UI and all features."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QRGenPro")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        
        # Load settings
        self.qsettings = QSettings("QRGenPro", "QRGenPro")
        self.app_settings = self._load_settings()
        
        # State
        self.config = QRConfig()
        self._last_bg_color = self.config.bg_color
        self.current_qr: Optional[Image.Image] = None
        self.batch_worker: Optional[BatchWorker] = None
        
        # Debounce timer for live preview
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)  # 150ms debounce
        self.preview_timer.timeout.connect(self._do_generate_preview)
        
        # Apply theme
        self.theme = THEMES.get(self.app_settings.theme, THEMES["dark"])
        self.style_mgr = StyleManager(self.theme)
        
        self._build_ui()
        self._setup_shortcuts()
        self._restore_geometry()
        
        # Initial preview
        QTimer.singleShot(100, self._do_generate_preview)
    
    def _load_settings(self) -> AppSettings:
        return AppSettings(
            theme=self.qsettings.value("theme", "dark"),
            output_dir=self.qsettings.value("output_dir", str(Path.home() / "Desktop")),
            last_format=self.qsettings.value("last_format", "PNG"),
            naming_template=self.qsettings.value("naming_template", "qr_code_{index}"),
            target_size=int(self.qsettings.value("target_size", 10)),
            window_geometry=self.qsettings.value("geometry", ""),
        )
    
    def _save_settings(self):
        self.qsettings.setValue("theme", self.app_settings.theme)
        self.qsettings.setValue("output_dir", self.app_settings.output_dir)
        self.qsettings.setValue("last_format", self.app_settings.last_format)
        self.qsettings.setValue("naming_template", self.app_settings.naming_template)
        self.qsettings.setValue("target_size", self.app_settings.target_size)
        self.qsettings.setValue("geometry", self.saveGeometry().toBase64().data().decode())
    
    def _restore_geometry(self):
        if self.app_settings.window_geometry:
            try:
                self.restoreGeometry(QtCore.QByteArray.fromBase64(
                    self.app_settings.window_geometry.encode()))
            except Exception:
                pass
    
    def closeEvent(self, event):
        self._save_settings()
        if self.batch_worker:
            self.batch_worker.stop()
            self.batch_worker.wait()
        super().closeEvent(event)
    
    def _setup_shortcuts(self):
        shortcuts = [
            ("Ctrl+S", self.save_qr),
            ("Ctrl+C", self.copy_image),
            ("Ctrl+G", self._do_generate_preview),
            ("Ctrl+L", self.select_logo),
            ("Ctrl+T", self.test_qr),
        ]
        for key, handler in shortcuts:
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.activated.connect(handler)
    
    def _build_ui(self):
        self.setStyleSheet(self.style_mgr.get_app_stylesheet())
        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Tab widget
        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tab
        self.tabs.addTab(self._build_create_tab(), "✦ Create")
        self.tabs.addTab(self._build_batch_tab(), "⚡ Batch")
        self.tabs.addTab(self._build_settings_tab(), "⚙ Settings")
        
        # Status bar
        self.status_label = QtWidgets.QLabel("Ready")
        self.statusBar().addWidget(self.status_label)
    
    def _build_create_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Left panel - Content, Presets, Log
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(8)
        layout.addLayout(left, 5)
        
        left.addWidget(self._build_content_card())
        left.addWidget(self._build_presets_card())
        left.addWidget(self._build_options_card())
        left.addWidget(self._build_log_card())
        left.addStretch()
        
        # Right panel - Preview + Actions
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)
        layout.addLayout(right, 4)
        
        right.addWidget(self._build_preview_card())
        right.addWidget(self._build_actions_card())
        right.addStretch()
        
        return widget
    
    def _build_content_card(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Content")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setSpacing(8)
        
        self.content_edit = QtWidgets.QPlainTextEdit()
        self.content_edit.setPlaceholderText("Enter URL, text, or use a preset...")
        self.content_edit.setPlainText("https://example.com")
        self.content_edit.setMaximumHeight(70)
        self.content_edit.textChanged.connect(self._schedule_preview)
        self.content_edit.setAcceptDrops(True)
        layout.addWidget(self.content_edit)
        
        return box
    
    def _build_presets_card(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Presets")
        layout = QtWidgets.QHBoxLayout(box)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)
        
        presets = [
            ("Web", self._preset_website),
            ("WiFi", self._preset_wifi),
            ("Email", self._preset_email),
            ("Phone", self._preset_phone),
            ("SMS", self._preset_sms),
            ("vCard", self._preset_vcard),
            ("Geo", self._preset_geo),
        ]
        
        for text, handler in presets:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedHeight(28)
            btn.clicked.connect(handler)
            btn.setCursor(Qt.PointingHandCursor)
            layout.addWidget(btn)
        
        return box
    
    def _build_options_card(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Style & Options")
        layout = QtWidgets.QGridLayout(box)
        layout.setSpacing(10)
        layout.setColumnStretch(1, 1)
        
        row = 0
        
        # Auto-optimize checkbox (moved up so it controls size visibility)
        self.auto_opt_check = QtWidgets.QCheckBox("Auto-optimize version")
        self.auto_opt_check.setChecked(True)
        self.auto_opt_check.stateChanged.connect(self._on_auto_opt_changed)
        layout.addWidget(self.auto_opt_check, row, 0, 1, 3)
        
        row += 1
        
        # Box size (only shown when auto-optimize is OFF)
        self.size_row_label = QtWidgets.QLabel("Size:")
        layout.addWidget(self.size_row_label, row, 0)
        self.size_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.size_slider.setRange(5, 25)
        self.size_slider.setValue(self.config.box_size)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        layout.addWidget(self.size_slider, row, 1)
        self.size_label = QtWidgets.QLabel(f"{self.config.box_size}px")
        self.size_label.setFixedWidth(45)
        layout.addWidget(self.size_label, row, 2)
        # Initially hide size controls (auto-optimize is ON by default)
        self.size_row_label.hide()
        self.size_slider.hide()
        self.size_label.hide()
        
        row += 1
        
        # Error correction
        layout.addWidget(QtWidgets.QLabel("Error Correction:"), row, 0)
        self.ecc_combo = QtWidgets.QComboBox()
        self.ecc_combo.addItems(list(ERROR_LEVELS.keys()))
        self.ecc_combo.setCurrentText(self.config.error_correction)
        self.ecc_combo.currentTextChanged.connect(self._on_ecc_changed)
        layout.addWidget(self.ecc_combo, row, 1, 1, 2)
        
        row += 1
        
        # QR Color
        layout.addWidget(QtWidgets.QLabel("QR Color:"), row, 0)
        self.qr_color_btn = QtWidgets.QPushButton("■ Black")
        self.qr_color_btn.clicked.connect(self._pick_qr_color)
        layout.addWidget(self.qr_color_btn, row, 1, 1, 2)
        
        row += 1
        
        # Background
        layout.addWidget(QtWidgets.QLabel("Background:"), row, 0)
        bg_layout = QtWidgets.QHBoxLayout()
        self.bg_color_btn = QtWidgets.QPushButton("■ White")
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        bg_layout.addWidget(self.bg_color_btn)
        self.transparent_check = QtWidgets.QCheckBox("Transparent")
        self.transparent_check.stateChanged.connect(self._on_transparent_changed)
        bg_layout.addWidget(self.transparent_check)
        self.reset_colors_btn = QtWidgets.QPushButton("Reset Colors")
        self.reset_colors_btn.setFixedHeight(26)
        self.reset_colors_btn.clicked.connect(self._reset_colors)
        bg_layout.addWidget(self.reset_colors_btn)
        layout.addLayout(bg_layout, row, 1, 1, 2)
        
        row += 1
        
        # Logo
        layout.addWidget(QtWidgets.QLabel("Logo:"), row, 0)
        logo_layout = QtWidgets.QHBoxLayout()
        self.logo_btn = QtWidgets.QPushButton("Select Logo...")
        self.logo_btn.clicked.connect(self.select_logo)
        logo_layout.addWidget(self.logo_btn)
        self.clear_logo_btn = QtWidgets.QPushButton("✕")
        self.clear_logo_btn.setFixedWidth(32)
        self.clear_logo_btn.clicked.connect(self._clear_logo)
        self.clear_logo_btn.setEnabled(False)
        logo_layout.addWidget(self.clear_logo_btn)
        layout.addLayout(logo_layout, row, 1, 1, 2)
        
        row += 1
        
        # Quiet zone checkbox
        self.quiet_check = QtWidgets.QCheckBox("Quiet zone (border)")
        self.quiet_check.setChecked(True)
        self.quiet_check.stateChanged.connect(self._schedule_preview)
        layout.addWidget(self.quiet_check, row, 0, 1, 3)
        
        return box
    
    def _build_actions_card(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Actions")
        layout = QtWidgets.QHBoxLayout(box)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setFixedHeight(30)
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self.save_qr)
        layout.addWidget(save_btn)
        
        copy_btn = QtWidgets.QPushButton("Copy")
        copy_btn.setFixedHeight(30)
        copy_btn.setProperty("class", "primary")
        copy_btn.clicked.connect(self.copy_image)
        layout.addWidget(copy_btn)
        
        test_btn = QtWidgets.QPushButton("Test")
        test_btn.setFixedHeight(30)
        test_btn.clicked.connect(self.test_qr)
        layout.addWidget(test_btn)
        
        return box
    
    def _build_preview_card(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Preview")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        
        self.preview_widget = PreviewWidget()
        self.preview_widget.setMinimumSize(280, 280)
        self.preview_widget.setMaximumSize(350, 350)
        self.preview_widget.setStyleSheet(
            f"background: {self.theme.surface}; border: 1px solid {self.theme.border}; border-radius: 6px;"
        )
        layout.addWidget(self.preview_widget, alignment=Qt.AlignCenter)
        
        return box
    
    def _build_log_card(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Log")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(80)
        self.log_view.setPlaceholderText("Activity log...")
        layout.addWidget(self.log_view)
        
        return box
    
    def _build_batch_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setSpacing(16)
        
        # Left - Input
        left = QtWidgets.QVBoxLayout()
        layout.addLayout(left, 3)
        
        input_box = QtWidgets.QGroupBox("Batch Items")
        input_layout = QtWidgets.QVBoxLayout(input_box)
        
        self.batch_text = QtWidgets.QPlainTextEdit()
        self.batch_text.setPlaceholderText("One item per line (URL, text, etc.)")
        input_layout.addWidget(self.batch_text)
        
        btn_row = QtWidgets.QHBoxLayout()
        load_btn = QtWidgets.QPushButton("📂 Load File")
        load_btn.clicked.connect(self._batch_load_file)
        btn_row.addWidget(load_btn)
        
        save_btn = QtWidgets.QPushButton("💾 Save List")
        save_btn.clicked.connect(self._batch_save_file)
        btn_row.addWidget(save_btn)
        
        clear_btn = QtWidgets.QPushButton("🗑 Clear")
        clear_btn.clicked.connect(lambda: self.batch_text.clear())
        btn_row.addWidget(clear_btn)
        
        input_layout.addLayout(btn_row)
        left.addWidget(input_box)
        
        # Right - Settings & Progress
        right = QtWidgets.QVBoxLayout()
        layout.addLayout(right, 2)
        
        settings_box = QtWidgets.QGroupBox("Batch Settings")
        settings_layout = QtWidgets.QFormLayout(settings_box)
        
        self.batch_naming = QtWidgets.QLineEdit("qr_{index}")
        self.batch_naming.setPlaceholderText("Use {index} and {content}")
        settings_layout.addRow("Naming:", self.batch_naming)
        
        self.batch_format = QtWidgets.QComboBox()
        self.batch_format.addItems(["PNG", "JPEG"])
        settings_layout.addRow("Format:", self.batch_format)
        
        right.addWidget(settings_box)
        
        # Progress
        progress_box = QtWidgets.QGroupBox("Progress")
        progress_layout = QtWidgets.QVBoxLayout(progress_box)
        
        self.batch_status = QtWidgets.QLabel("Ready")
        progress_layout.addWidget(self.batch_status)
        
        self.batch_progress = QtWidgets.QProgressBar()
        self.batch_progress.setValue(0)
        progress_layout.addWidget(self.batch_progress)
        
        batch_btn_row = QtWidgets.QHBoxLayout()
        self.batch_start_btn = QtWidgets.QPushButton("▶ Start Batch")
        self.batch_start_btn.setProperty("class", "primary")
        self.batch_start_btn.clicked.connect(self._batch_start)
        batch_btn_row.addWidget(self.batch_start_btn)
        
        self.batch_stop_btn = QtWidgets.QPushButton("⏹ Stop")
        self.batch_stop_btn.clicked.connect(self._batch_stop)
        self.batch_stop_btn.setEnabled(False)
        batch_btn_row.addWidget(self.batch_stop_btn)
        
        progress_layout.addLayout(batch_btn_row)
        right.addWidget(progress_box)
        right.addStretch()
        
        return widget
    
    def _build_settings_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(16)
        
        # Theme
        theme_box = QtWidgets.QGroupBox("Appearance")
        theme_layout = QtWidgets.QFormLayout(theme_box)
        
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.app_settings.theme)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addRow("Theme:", self.theme_combo)
        
        layout.addWidget(theme_box)
        
        # Defaults
        defaults_box = QtWidgets.QGroupBox("Defaults")
        defaults_layout = QtWidgets.QFormLayout(defaults_box)
        defaults_layout.setSpacing(12)
        
        # Save folder
        folder_row = QtWidgets.QHBoxLayout()
        self.folder_label = QtWidgets.QLabel(self.app_settings.output_dir)
        self.folder_label.setWordWrap(True)
        folder_row.addWidget(self.folder_label, 1)
        folder_btn = QtWidgets.QPushButton("Browse...")
        folder_btn.clicked.connect(self._pick_output_dir)
        folder_row.addWidget(folder_btn)
        defaults_layout.addRow("Save Folder:", folder_row)
        
        # Naming convention
        self.settings_naming = QtWidgets.QLineEdit(self.app_settings.naming_template)
        self.settings_naming.setPlaceholderText("Use {index} and {content}")
        self.settings_naming.textChanged.connect(self._on_naming_changed)
        defaults_layout.addRow("File Naming:", self.settings_naming)
        
        naming_hint = QtWidgets.QLabel("Variables: {index}, {content}")
        naming_hint.setProperty("class", "secondary")
        defaults_layout.addRow("", naming_hint)
        
        # Default file format
        self.settings_format = QtWidgets.QComboBox()
        self.settings_format.addItems(["PNG", "JPEG"])
        self.settings_format.setCurrentText(self.app_settings.last_format)
        self.settings_format.currentTextChanged.connect(self._on_format_changed)
        defaults_layout.addRow("File Format:", self.settings_format)
        
        # Target image size
        size_row = QtWidgets.QHBoxLayout()
        self.settings_size = QtWidgets.QSlider(Qt.Horizontal)
        self.settings_size.setRange(5, 25)
        self.settings_size.setValue(self.app_settings.target_size)
        self.settings_size.valueChanged.connect(self._on_target_size_changed)
        size_row.addWidget(self.settings_size)
        self.settings_size_label = QtWidgets.QLabel(f"{self.app_settings.target_size}px")
        self.settings_size_label.setFixedWidth(45)
        size_row.addWidget(self.settings_size_label)
        defaults_layout.addRow("Default Size:", size_row)
        
        layout.addWidget(defaults_box)
        
        # About
        about_box = QtWidgets.QGroupBox("About")
        about_layout = QtWidgets.QVBoxLayout(about_box)
        about_text = QtWidgets.QLabel(
            "<b>QRGenPro</b> v2.0<br>"
            "Professional QR Code Generator<br><br>"
            "<b>Shortcuts:</b><br>"
            "Ctrl+S: Save | Ctrl+C: Copy Image<br>"
            "Ctrl+G: Generate | Ctrl+L: Add Logo<br>"
            "Ctrl+T: Test & Inspect"
        )
        about_text.setWordWrap(True)
        about_layout.addWidget(about_text)
        layout.addWidget(about_box)
        
        layout.addStretch()
        return widget
    
    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    def _schedule_preview(self):
        """Debounced preview update."""
        self.preview_timer.start()
    
    def _on_size_changed(self, value: int):
        self.config.box_size = value
        self.size_label.setText(f"{value}px")
        self._schedule_preview()
    
    def _on_ecc_changed(self, value: str):
        self.config.error_correction = value
        self._schedule_preview()
    
    def _on_auto_opt_changed(self, state):
        """Show/hide size slider based on auto-optimize state."""
        # state is 2 for Checked, 0 for Unchecked
        is_auto = state != 0
        self.size_row_label.setVisible(not is_auto)
        self.size_slider.setVisible(not is_auto)
        self.size_label.setVisible(not is_auto)
        self._schedule_preview()
    
    def _on_transparent_changed(self, state):
        # state is 2 for Checked, 0 for Unchecked
        is_checked = self.transparent_check.isChecked()
        self.config.transparent_bg = is_checked
        
        if is_checked:
            # Reset background color display when transparent
            self._last_bg_color = self.config.bg_color
            self.bg_color_btn.setText("■ (transparent)")
            self.bg_color_btn.setEnabled(False)
        else:
            # Restore last selected color when turning transparency off
            if self._last_bg_color:
                self.config.bg_color = self._last_bg_color
            self.bg_color_btn.setText(f"■ {self.config.bg_color}")
            self.bg_color_btn.setEnabled(True)
        self._schedule_preview()
    
    def _on_theme_changed(self, theme_name: str):
        self.app_settings.theme = theme_name
        self.theme = THEMES.get(theme_name, THEMES["dark"])
        self.style_mgr = StyleManager(self.theme)
        self.setStyleSheet(self.style_mgr.get_app_stylesheet())
        self.preview_widget.setStyleSheet(
            f"background: {self.theme.surface}; border: 1px solid {self.theme.border}; border-radius: 8px;"
        )
        self._log(f"✨ Switched to {theme_name} theme")
    
    def _on_naming_changed(self, text: str):
        self.app_settings.naming_template = text
    
    def _on_format_changed(self, fmt: str):
        self.app_settings.last_format = fmt
    
    def _on_target_size_changed(self, value: int):
        self.app_settings.target_size = value
        self.settings_size_label.setText(f"{value}px")
        # Also update the main config
        self.config.box_size = value
        self.size_slider.setValue(value)
        self._schedule_preview()

    def _reset_colors(self):
        """Reset QR/BG colors to black on white and clear transparency."""
        self.config.qr_color = "#000000"
        self.config.bg_color = "#ffffff"
        self._last_bg_color = self.config.bg_color
        self.transparent_check.setChecked(False)
        self.qr_color_btn.setText("■ #000000")
        self.bg_color_btn.setText("■ #ffffff")
        self.bg_color_btn.setEnabled(True)
        self._schedule_preview()
    
    def _pick_qr_color(self):
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.config.qr_color), self, "Pick QR Color"
        )
        if color.isValid():
            self.config.qr_color = color.name()
            self.qr_color_btn.setText(f"■ {color.name()}")
            self._schedule_preview()
    
    def _pick_bg_color(self):
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.config.bg_color), self, "Pick Background Color"
        )
        if color.isValid():
            self.config.bg_color = color.name()
            self.bg_color_btn.setText(f"■ {color.name()}")
            self.transparent_check.setChecked(False)
            self._schedule_preview()
    
    def _pick_output_dir(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Save Folder", self.app_settings.output_dir
        )
        if folder:
            self.app_settings.output_dir = folder
            self.folder_label.setText(folder)
            self._log(f"📁 Output folder set to: {folder}")
    
    def select_logo(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Logo",
            self.app_settings.output_dir,
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.svg);;All files (*.*)"
        )
        if path:
            self.config.logo_path = path
            self.logo_btn.setText(f"✓ {os.path.basename(path)}")
            self.clear_logo_btn.setEnabled(True)
            self._log(f"🖼️ Logo added: {os.path.basename(path)}")
            self._schedule_preview()
    
    def _clear_logo(self):
        self.config.logo_path = ""
        self.logo_btn.setText("Select Logo...")
        self.clear_logo_btn.setEnabled(False)
        self._log("🖼️ Logo removed")
        self._schedule_preview()
    
    # =========================================================================
    # PRESET HANDLERS
    # =========================================================================
    def _preset_website(self):
        url, ok = QtWidgets.QInputDialog.getText(
            self, "Website", "Enter URL (e.g., example.com):"
        )
        if ok and url:
            self.content_edit.setPlainText(Presets.website(url))
    
    def _preset_wifi(self):
        ssid, ok = QtWidgets.QInputDialog.getText(self, "WiFi", "Network name (SSID):")
        if not ok or not ssid:
            return
        password, _ = QtWidgets.QInputDialog.getText(
            self, "WiFi", "Password (leave empty for open network):"
        )
        try:
            self.content_edit.setPlainText(Presets.wifi(ssid, password))
        except ValueError as e:
            self._log(f"⚠️ {e}")
    
    def _preset_email(self):
        email, ok = QtWidgets.QInputDialog.getText(self, "Email", "Email address:")
        if not ok or not email:
            return
        subject, _ = QtWidgets.QInputDialog.getText(self, "Email", "Subject (optional):")
        body, _ = QtWidgets.QInputDialog.getText(self, "Email", "Body (optional):")
        try:
            self.content_edit.setPlainText(Presets.email(email, subject, body))
        except ValueError as e:
            self._log(f"⚠️ {e}")
    
    def _preset_phone(self):
        phone, ok = QtWidgets.QInputDialog.getText(self, "Phone", "Phone number:")
        if ok and phone:
            try:
                self.content_edit.setPlainText(Presets.phone(phone))
            except ValueError as e:
                self._log(f"⚠️ {e}")
    
    def _preset_sms(self):
        phone, ok = QtWidgets.QInputDialog.getText(self, "SMS", "Phone number:")
        if not ok or not phone:
            return
        message, _ = QtWidgets.QInputDialog.getText(self, "SMS", "Message (optional):")
        try:
            self.content_edit.setPlainText(Presets.sms(phone, message))
        except ValueError as e:
            self._log(f"⚠️ {e}")
    
    def _preset_vcard(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "vCard", "Full name:")
        if not ok or not name:
            return
        phone, _ = QtWidgets.QInputDialog.getText(self, "vCard", "Phone (optional):")
        email, _ = QtWidgets.QInputDialog.getText(self, "vCard", "Email (optional):")
        org, _ = QtWidgets.QInputDialog.getText(self, "vCard", "Organization (optional):")
        try:
            self.content_edit.setPlainText(Presets.vcard(name, phone, email, org))
        except ValueError as e:
            self._log(f"⚠️ {e}")
    
    def _preset_geo(self):
        lat, ok = QtWidgets.QInputDialog.getDouble(
            self, "Location", "Latitude:", 0, -90, 90, 6
        )
        if not ok:
            return
        lon, ok = QtWidgets.QInputDialog.getDouble(
            self, "Location", "Longitude:", 0, -180, 180, 6
        )
        if ok:
            self.content_edit.setPlainText(Presets.geo(lat, lon))
    
    # =========================================================================
    # CORE ACTIONS
    # =========================================================================
    def _log(self, message: str):
        """Add message to activity log."""
        self.log_view.append(message)
        self.status_label.setText(message)
    
    def _do_generate_preview(self):
        """Generate QR code and update preview with robust alpha preservation."""
        content = self.content_edit.toPlainText().strip()
        if not content:
            self.preview_widget.set_qr_pixmap(None, False)
            self.current_qr = None
            return
        
        # Explicitly sync UI -> Config
        self.config.content = content
        self.config.auto_optimize = self.auto_opt_check.isChecked()
        self.config.quiet_zone = self.quiet_check.isChecked()
        self.config.transparent_bg = self.transparent_check.isChecked()
        
        try:
            # 1. Generate in PIL
            img = QREngine.generate(self.config)
            self.current_qr = img
            
            # 2. CONVERSION: PIL RGBA -> PNG BYTES -> QIMAGE
            # This is the most bulletproof way to preserve alpha.
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            
            qim = QtGui.QImage.fromData(buffer.getvalue())
            if qim.isNull():
                raise ValueError("QImage failed to load from PNG buffer")
                
            # Convert to pixmap
            pix = QtGui.QPixmap.fromImage(qim)
            
            # 3. Scale for preview
            scaled = pix.scaled(
                300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            
            # 4. Update widget
            self.preview_widget.set_qr_pixmap(scaled, self.config.transparent_bg)
            
            # Log pixel info for debugging transparency
            p = img.getpixel((0,0))
            trans_status = "transparent" if self.config.transparent_bg else "solid"
            self._log(f"✅ QR code ready ({trans_status} background)")
            
        except Exception as e:
            self._log(f"⚠️ Could not generate preview: {e}")
            traceback.print_exc()
            self.preview_widget.set_qr_pixmap(None, False)
    
    def save_qr(self):
        """Save QR code to file."""
        if not self.current_qr:
            self._log("⚠️ Please generate a QR code first before saving")
            return
        
        filters = "PNG (*.png);;JPEG (*.jpg *.jpeg);;All files (*.*)"
        default_name = "qr_code.png"
        
        path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save QR Code",
            str(Path(self.app_settings.output_dir) / default_name),
            filters
        )
        
        if not path:
            return
        
        try:
            if path.lower().endswith(('.jpg', '.jpeg')):
                self.current_qr.convert("RGB").save(path, "JPEG", quality=95)
            else:
                self.current_qr.save(path, "PNG")
            
            self.app_settings.output_dir = str(Path(path).parent)
            self._log(f"💾 Saved successfully: {os.path.basename(path)}")
        except Exception as e:
            self._log(f"⚠️ Could not save file: {e}")
    
    def copy_image(self):
        """Copy QR code image to clipboard."""
        if not self.current_qr:
            self._log("⚠️ Please generate a QR code first before copying")
            return
        
        try:
            qim = ImageQt.ImageQt(self.current_qr)
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setImage(qim)
            self._log("📋 QR code image copied to clipboard")
        except Exception as e:
            self._log(f"⚠️ Could not copy to clipboard: {e}")
    
    def _copy_content_text(self):
        """Copy content text to clipboard."""
        text = self.content_edit.toPlainText().strip()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(text)
            self._log("📋 Content text copied to clipboard")
    
    def test_qr(self):
        """Open test & inspect dialog."""
        if not self.current_qr:
            self._log("⚠️ Please generate a QR code first before testing")
            return
        
        content = self.content_edit.toPlainText().strip()
        
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Test & Inspect")
        dlg.setMinimumSize(500, 550)
        dlg.setStyleSheet(self.style_mgr.get_app_stylesheet())
        
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setSpacing(16)
        
        # Preview image
        img_label = QtWidgets.QLabel()
        qim = ImageQt.ImageQt(self.current_qr)
        pix = QtGui.QPixmap.fromImage(qim).scaled(
            300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        img_label.setPixmap(pix)
        img_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(img_label)
        
        # Content display
        content_box = QtWidgets.QGroupBox("Encoded Content")
        content_layout = QtWidgets.QVBoxLayout(content_box)
        content_text = QtWidgets.QTextEdit()
        content_text.setPlainText(content)
        content_text.setReadOnly(True)
        content_text.setMaximumHeight(100)
        content_layout.addWidget(content_text)
        layout.addWidget(content_box)
        
        # Actions
        btn_layout = QtWidgets.QHBoxLayout()
        
        copy_text_btn = QtWidgets.QPushButton("📝 Copy Text")
        copy_text_btn.clicked.connect(lambda: self._dialog_copy_text(content))
        btn_layout.addWidget(copy_text_btn)
        
        copy_img_btn = QtWidgets.QPushButton("📋 Copy Image")
        copy_img_btn.clicked.connect(self.copy_image)
        btn_layout.addWidget(copy_img_btn)
        
        save_btn = QtWidgets.QPushButton("💾 Save")
        save_btn.clicked.connect(self.save_qr)
        btn_layout.addWidget(save_btn)
        
        if QREngine.validate_url(content):
            open_btn = QtWidgets.QPushButton("🌐 Open URL")
            open_btn.clicked.connect(
                lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(content))
            )
            btn_layout.addWidget(open_btn)
        
        layout.addLayout(btn_layout)
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn)
        
        dlg.exec()
    
    def _dialog_copy_text(self, text: str):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        self._log("📋 Text copied to clipboard")
    
    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================
    def _batch_load_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Batch File",
            self.app_settings.output_dir,
            "Text/CSV (*.txt *.csv);;All files (*.*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.batch_text.setPlainText(f.read())
                self._log(f"📂 Loaded file: {os.path.basename(path)}")
            except Exception as e:
                self._log(f"⚠️ Could not load file: {e}")
    
    def _batch_save_file(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Batch List",
            str(Path(self.app_settings.output_dir) / "batch_items.txt"),
            "Text (*.txt);;All files (*.*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.batch_text.toPlainText())
                self._log(f"💾 Batch list saved: {os.path.basename(path)}")
            except Exception as e:
                self._log(f"⚠️ Could not save batch list: {e}")
    
    def _batch_start(self):
        lines = [ln.strip() for ln in self.batch_text.toPlainText().splitlines() if ln.strip()]
        if not lines:
            self._log("⚠️ Please add items to process (one per line)")
            return
        
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.app_settings.output_dir
        )
        if not out_dir:
            return
        
        self.app_settings.output_dir = out_dir
        
        # Stop any existing worker
        self._batch_stop()
        
        # Create worker with current config
        self.batch_worker = BatchWorker(
            items=lines,
            config=self.config,
            output_dir=Path(out_dir),
            naming=self.batch_naming.text() or "qr_{index}",
            fmt=self.batch_format.currentText()
        )
        
        self.batch_worker.progress.connect(self._on_batch_progress)
        self.batch_worker.finished.connect(self._on_batch_finished)
        self.batch_worker.error.connect(self._log)
        
        self.batch_start_btn.setEnabled(False)
        self.batch_stop_btn.setEnabled(True)
        self.batch_progress.setMaximum(len(lines))
        self.batch_progress.setValue(0)
        
        self.batch_worker.start()
        self._log(f"🚀 Batch processing started: {len(lines)} items")
    
    def _batch_stop(self):
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.batch_worker.wait()
            self._log("⏹️ Batch processing stopped")
        self.batch_worker = None
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)
    
    def _on_batch_progress(self, current: int, total: int, item: str):
        self.batch_progress.setValue(current)
        self.batch_status.setText(f"{current}/{total}: {item[:40]}...")
    
    def _on_batch_finished(self, success: int, failed: int):
        total = success + failed
        self.batch_status.setText(f"Done! Success: {success}, Failed: {failed}")
        self.batch_progress.setValue(self.batch_progress.maximum())
        self._log(f"🎉 Batch complete: {success} saved, {failed} failed")
        self._batch_stop()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    # Enable high DPI scaling
    QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("QRGenPro")
    app.setOrganizationName("QRGenPro")
    
    # Set default font
    font = app.font()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    
    window = NeoQRPro()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
