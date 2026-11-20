"""Modern dark-theme desktop UI for the Auto Clicker."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QStyle,
    QMenu,
)

from clicker import Clicker
from hotkey import HotkeyListener, key_to_label, parse_key
from settings import load_settings, save_settings


# --------------------------------------------------------------------------- palette
BG_COLOR = "#0f172a"
CARD_COLOR = "#1e293b"
ACCENT_COLOR = "#38bdf8"
ACCENT_HOVER = "#7dd3fc"
TEXT_COLOR = "#f1f5f9"
TEXT_MUTED = "#94a3b8"
DANGER_COLOR = "#ef4444"
DANGER_HOVER = "#f87171"
SUCCESS_COLOR = "#22c55e"
BORDER_COLOR = "#334155"


class ClickButton(QPushButton):
    """Animated Start / Stop toggle button."""

    def __init__(self, text: str = "Start") -> None:
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(56)
        self._apply_style(running=False)

    def set_running(self, running: bool) -> None:
        self._apply_style(running)
        self.setText("Стоп" if running else "Старт")

    def _apply_style(self, running: bool) -> None:
        color = DANGER_COLOR if running else SUCCESS_COLOR
        hover = DANGER_HOVER if running else "#4ade80"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color};
                color: #ffffff;
                border: none;
                border-radius: 14px;
                font-size: 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{
                background-color: {color};
                padding-top: 2px;
                padding-bottom: 0px;
            }}
            """
        )


class StatCard(QFrame):
    """Small stat card: title + value."""

    def __init__(self, title: str, value: str = "—") -> None:
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(
            f"""
            QFrame#statCard {{
                background-color: {CARD_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600;"
        )
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 20px; font-weight: 700;"
        )

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(str(value))


class SettingsPanel(QWidget):
    """Settings: interval, mouse button, hotkey, random chance."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        title = QLabel("Настройки")
        title.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 18px; font-weight: 700;"
        )
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(14)

        # Interval
        self.interval_label = QLabel("Интервал (сек):")
        self.interval_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px;"
        )
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.01, 3600.0)
        self.interval_spin.setDecimals(2)
        self.interval_spin.setSingleStep(0.1)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setFixedWidth(120)
        self.interval_spin.setStyleSheet(self._spin_style())
        grid.addWidget(self.interval_label, 0, 0)
        grid.addWidget(self.interval_spin, 0, 1)

        # Mouse button
        self.button_label = QLabel("Кнопка мыши:")
        self.button_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px;"
        )
        self.button_btn = QPushButton("Левая")
        self.button_btn.setFixedSize(130, 36)
        self.button_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button_btn.setStyleSheet(self._toggle_style("Левая"))
        self.button_btn.clicked.connect(self._cycle_button)
        grid.addWidget(self.button_label, 1, 0)
        grid.addWidget(self.button_btn, 1, 1)

        # Hotkey
        self.hotkey_label = QLabel("Горячая клавиша:")
        self.hotkey_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px;"
        )
        self.hotkey_btn = QPushButton("F6")
        self.hotkey_btn.setFixedSize(130, 36)
        self.hotkey_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hotkey_btn.setStyleSheet(self._toggle_style("F6"))
        self.hotkey_btn.clicked.connect(self._request_capture)
        grid.addWidget(self.hotkey_label, 2, 0)
        grid.addWidget(self.hotkey_btn, 2, 1)

        layout.addLayout(grid)

        # Random chance
        self.random_chk = QCheckBox("Случайный шанс клика")
        self.random_chk.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: 600;"
        )
        self.random_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.random_chk)

        chance_row = QHBoxLayout()
        chance_row.setContentsMargins(24, 0, 0, 0)
        self.chance_label = QLabel("Вероятность (%):")
        self.chance_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px;"
        )
        self.chance_spin = QDoubleSpinBox()
        self.chance_spin.setRange(0.0, 100.0)
        self.chance_spin.setDecimals(0)
        self.chance_spin.setSingleStep(5.0)
        self.chance_spin.setValue(50.0)
        self.chance_spin.setFixedWidth(100)
        self.chance_spin.setStyleSheet(self._spin_style())
        chance_row.addWidget(self.chance_label)
        chance_row.addWidget(self.chance_spin)
        chance_row.addStretch()
        layout.addLayout(chance_row)

        self.random_chk.toggled.connect(self._on_random_toggled)
        self._on_random_toggled(self.random_chk.isChecked())

        layout.addStretch()

        # Capture callback set by parent
        self.on_capture_requested = None

    def _spin_style(self) -> str:
        return (
            f"QDoubleSpinBox {{"
            f"background-color: {BG_COLOR};"
            f"color: {TEXT_COLOR};"
            f"border: 1px solid {BORDER_COLOR};"
            f"border-radius: 8px;"
            f"padding: 4px 8px;"
            f"font-size: 13px;"
            f"}}"
            f"QDoubleSpinBox:focus {{ border: 1px solid {ACCENT_COLOR}; }}"
        )

    def _toggle_style(self, text: str) -> str:
        return (
            f"QPushButton {{"
            f"background-color: {CARD_COLOR};"
            f"color: {TEXT_COLOR};"
            f"border: 1px solid {BORDER_COLOR};"
            f"border-radius: 10px;"
            f"font-size: 13px;"
            f"font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ border: 1px solid {ACCENT_COLOR}; }}"
            f"QPushButton:pressed {{ background-color: {BORDER_COLOR}; }}"
        )

    def _cycle_button(self) -> None:
        current = self.button_btn.text()
        mapping = {"Левая": "Правая", "Правая": "Средняя", "Средняя": "Левая"}
        next_text = mapping.get(current, "Левая")
        self.button_btn.setText(next_text)
        self.button_btn.setStyleSheet(self._toggle_style(next_text))

    def _request_capture(self) -> None:
        if self.on_capture_requested is not None:
            self.on_capture_requested()

    def button_value(self) -> str:
        return {"Левая": "left", "Правая": "right", "Средняя": "middle"}[
            self.button_btn.text()
        ]

    def _on_random_toggled(self, checked: bool) -> None:
        enabled = checked
        self.chance_label.setEnabled(enabled)
        self.chance_spin.setEnabled(enabled)
        opacity = "1" if enabled else "0.5"
        self.chance_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; opacity: {opacity};"
        )
        self.chance_spin.setStyleSheet(self._spin_style())

    # ------------------------------------------------------------------ data
    def load_from_settings(self, settings) -> None:
        self.interval_spin.setValue(settings.interval)
        self.button_btn.setText(
            {"left": "Левая", "right": "Правая", "middle": "Средняя"}.get(
                settings.button, "Левая"
            )
        )
        self.button_btn.setStyleSheet(self._toggle_style(self.button_btn.text()))
        label = key_to_label(parse_key(settings.hotkey)) or settings.hotkey.upper()
        self.hotkey_btn.setText(label.upper())
        self.hotkey_btn.setStyleSheet(self._toggle_style(self.hotkey_btn.text()))
        self.random_chk.setChecked(settings.random_chance)
        self.chance_spin.setValue(settings.random_chance_percent)
        self._on_random_toggled(settings.random_chance)

    def collect(self) -> dict:
        return {
            "interval": self.interval_spin.value(),
            "button": self.button_value(),
            "hotkey": self.hotkey_btn.text().lower(),
            "random_chance": self.random_chk.isChecked(),
            "random_chance_percent": self.chance_spin.value(),
        }


class HotkeyCaptureDialog(QWidget):
    """Transparent overlay that captures the next key press for the hotkey."""

    def __init__(self, parent, on_key) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._on_key = on_key
        self._listener = None

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        text = event.text()
        # Build a string like 'f6' or 'a'
        from PyQt6.QtCore import Qt as _Qt
        key_name = _Qt.Key(key).name.lower() if hasattr(_Qt.Key(key), "name") else ""
        # Map Qt key names to our hotkey names
        value = None
        if key_name in ("f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"):
            value = key_name
        elif text and text.isalnum() and len(text) == 1:
            value = text.lower()
        if value is not None:
            self._on_key(value)
        self.close()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Clicker")
        self.setMinimumSize(700, 520)
        self.resize(720, 560)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_COLOR}; }}")

        self._settings = load_settings()
        self._clicker = Clicker(on_status_change=self._on_clicker_status_changed)
        self._hotkey = HotkeyListener(callback=self._clicker.toggle)
        self._hotkey.set_hotkey(self._settings.hotkey)

        self._capture_dialog = None

        self._build_ui()
        self._apply_settings_to_ui()
        self._start_hotkey()

        # Tray
        self._build_tray()

        # Status refresh timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(200)

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # Header
        header = QHBoxLayout()
        app_title = QLabel("Auto Clicker")
        app_title.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;"
        )
        header.addWidget(app_title)
        header.addStretch()
        root.addLayout(header)

        # Divider
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {BORDER_COLOR};")
        root.addWidget(line)

        # Main action card
        action_card = QFrame()
        action_card.setObjectName("actionCard")
        action_card.setStyleSheet(
            f"""
            QFrame#actionCard {{
                background-color: {CARD_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 18px;
            }}
            """
        )
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(30, 26, 30, 26)
        action_layout.setSpacing(18)

        # Status row
        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 16px;")
        self.status_text = QLabel("Остановлен")
        self.status_text.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 16px; font-weight: 700;"
        )
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        action_layout.addLayout(status_row)

        # Big Start/Stop button
        self.start_btn = ClickButton("Старт")
        self.start_btn.clicked.connect(self._toggle_clicker)
        action_layout.addWidget(self.start_btn)

        # Stats grid
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.card_interval = StatCard("Интервал", "1.00 сек")
        self.card_button = StatCard("Кнопка", "Левая")
        self.card_hotkey = StatCard("Горячая клавиша", "F6")
        self.card_count = StatCard("Кликов", "0")
        for card in (self.card_interval, self.card_button, self.card_hotkey, self.card_count):
            stats.addWidget(card)
        action_layout.addLayout(stats)

        root.addWidget(action_card)

        # Settings panel
        self.settings_panel = SettingsPanel()
        self.settings_panel.on_capture_requested = self._start_capture
        root.addWidget(self.settings_panel)

    # ------------------------------------------------------------------ tray
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        # Use a simple built-in icon
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Auto Clicker")

        show_action = QAction("Показать", self)
        show_action.triggered.connect(self._show_from_tray)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self._quit_app)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:  # noqa: N802
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self) -> None:
        self._shutdown()
        QApplication.instance().quit()

    # ------------------------------------------------------------------ logic
    def _apply_settings_to_ui(self) -> None:
        self.settings_panel.load_from_settings(self._settings)
        self.card_interval.set_value(f"{self._settings.interval:.2f} сек")
        self.card_button.set_value(
            {"left": "Левая", "right": "Правая", "middle": "Средняя"}[
                self._settings.button
            ]
        )
        self.card_hotkey.set_value(self._settings.hotkey.upper())
        self.card_count.set_value(str(self._settings.click_count))

    def _start_hotkey(self) -> None:
        if self._hotkey._thread is None:
            self._hotkey._restart()

    def _toggle_clicker(self) -> None:
        if self._clicker.is_running():
            self._clicker.stop()
        else:
            self._clicker.start()

    def _start_capture(self) -> None:
        self._capture_dialog = HotkeyCaptureDialog(self, self._on_captured_key)
        self._capture_dialog.show()
        self.settings_panel.hotkey_btn.setText("Нажмите клавишу…")
        self.settings_panel.hotkey_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT_COLOR}; color: #000; border-radius: 10px; font-weight: 700; }}"
        )

    def _on_captured_key(self, value: str) -> None:
        key = parse_key(value)
        if key is None:
            self.settings_panel.hotkey_btn.setText("F6")
            self.settings_panel.hotkey_btn.setStyleSheet(
                self.settings_panel._toggle_style("F6")
            )
            self._capture_dialog = None
            return
        from hotkey import is_allowed
        if not is_allowed(key):
            QMessageBox.warning(
                self, "Недопустимая клавиша",
                "Эту клавишу нельзя использовать в качестве горячей."
            )
            self.settings_panel.hotkey_btn.setText("F6")
            self.settings_panel.hotkey_btn.setStyleSheet(
                self.settings_panel._toggle_style("F6")
            )
            self._capture_dialog = None
            return
        self.settings_panel.hotkey_btn.setText(value.upper())
        self.settings_panel.hotkey_btn.setStyleSheet(
            self.settings_panel._toggle_style(value.upper())
        )
        # Apply the captured hotkey to the clicker and settings
        self._settings.hotkey = value.lower()
        self._hotkey.set_hotkey(value.lower())
        self.card_hotkey.set_value(value.upper())
        save_settings(self._settings)
        self._capture_dialog = None

    def _on_clicker_status_changed(self, running: bool) -> None:
        self.start_btn.set_running(running)
        if running:
            self.status_dot.setStyleSheet(f"color: {SUCCESS_COLOR}; font-size: 16px;")
            self.status_text.setText("Запущен")
        else:
            self.status_dot.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 16px;")
            self.status_text.setText("Остановлен")

    def _refresh_status(self) -> None:
        state = self._clicker.get_state()
        self.card_count.set_value(str(state.click_count))
        self._settings.click_count = state.click_count

    def _apply_settings(self) -> None:
        data = self.settings_panel.collect()
        key = parse_key(data["hotkey"])
        if key is None or not self._is_hotkey_allowed(key):
            QMessageBox.warning(
                self, "Неверная клавиша",
                "Выбранная клавиша не может быть использована как горячая. Выберите другую."
            )
            return
        self._clicker.configure(
            interval=data["interval"],
            button=data["button"],
            random_chance=data["random_chance"],
            random_chance_percent=data["random_chance_percent"],
        )
        self._hotkey.set_hotkey(data["hotkey"])
        self._settings.interval = data["interval"]
        self._settings.button = data["button"]
        self._settings.hotkey = data["hotkey"]
        self._settings.random_chance = data["random_chance"]
        self._settings.random_chance_percent = data["random_chance_percent"]
        self.card_interval.set_value(f"{data['interval']:.2f} сек")
        self.card_button.set_value(
            {"left": "Левая", "right": "Правая", "middle": "Средняя"}[data["button"]]
        )
        self.card_hotkey.set_value(data["hotkey"].upper())
        save_settings(self._settings)

    def _is_hotkey_allowed(self, key) -> bool:
        from hotkey import is_allowed
        return is_allowed(key)

    # Apply settings whenever a setting control changes
    def _wire_settings_auto_apply(self) -> None:
        sp = self.settings_panel
        sp.interval_spin.valueChanged.connect(lambda *_: self._apply_settings())
        sp.button_btn.clicked.connect(lambda *_: self._apply_settings())
        sp.hotkey_btn.clicked.connect(lambda *_: None)  # capture handled separately
        sp.random_chk.toggled.connect(lambda *_: self._apply_settings())
        sp.chance_spin.valueChanged.connect(lambda *_: self._apply_settings())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._settings.minimize_to_tray:
            event.ignore()
            self.hide()
            return
        self._shutdown()
        event.accept()

    def _shutdown(self) -> None:
        self._clicker.stop()
        self._hotkey.stop()
        save_settings(self._settings)


def main() -> None:
    app = QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window._wire_settings_auto_apply()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
