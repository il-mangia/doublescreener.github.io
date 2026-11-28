"""Foglio di stile scuro della regia."""

from __future__ import annotations

DARK_QSS = """
QWidget {
    background: #12141a;
    color: #e6eaf2;
    font-size: 13px;
}
QMainWindow::separator {
    background: #232733;
    width: 2px;
    height: 2px;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
    background: #171a22;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #2a3142;
}
QToolBar {
    border: none;
    border-bottom: 1px solid #232733;
    padding: 4px;
    spacing: 6px;
}
QToolButton, QPushButton {
    background: #1d2230;
    border: 1px solid #2c3346;
    border-radius: 6px;
    padding: 5px 10px;
}
QToolButton:hover, QPushButton:hover {
    background: #263049;
    border-color: #3d4a68;
}
QToolButton:checked, QPushButton:checked {
    background: #3a2230;
    border-color: #b3455f;
}
QToolButton:disabled, QPushButton:disabled {
    color: #6b7386;
    background: #191c25;
}
QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background: #171a22;
    padding: 6px 8px;
    border-bottom: 1px solid #232733;
}
QListWidget {
    background: #0e1015;
    border: 1px solid #232733;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background: #2a3a5a;
}
QLineEdit, QSpinBox, QComboBox {
    background: #0e1015;
    border: 1px solid #2c3346;
    border-radius: 6px;
    padding: 4px 8px;
}
QLabel#sectionTitle {
    color: #9fb0cc;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 11px;
}
QLabel#canvasHint {
    color: #5d6a82;
    border: 1px dashed #2c3346;
    border-radius: 10px;
    background: #0b0d12;
    font-size: 14px;
}
QLabel#urlLabel {
    color: #8fd3ff;
}
"""

LIGHT_QSS = """
QWidget {
    background: #f4f6fa;
    color: #141821;
    font-size: 13px;
}
QMainWindow::separator {
    background: #d9dfe9;
    width: 2px;
    height: 2px;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
    background: #ffffff;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #e2e8f4;
}
QToolBar {
    border: none;
    border-bottom: 1px solid #d9dfe9;
    padding: 4px;
    spacing: 6px;
}
QToolButton, QPushButton {
    background: #ffffff;
    border: 1px solid #cbd3e1;
    border-radius: 6px;
    padding: 5px 10px;
}
QToolButton:hover, QPushButton:hover {
    background: #eef2f9;
    border-color: #93a3be;
}
QToolButton:checked, QPushButton:checked {
    background: #dbeafe;
    border-color: #2563eb;
}
QToolButton:disabled, QPushButton:disabled {
    color: #94a3b8;
    background: #f1f5f9;
}
QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background: #ffffff;
    padding: 6px 8px;
    border-bottom: 1px solid #d9dfe9;
}
QListWidget {
    background: #ffffff;
    border: 1px solid #d9dfe9;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background: #dbeafe;
    color: #0f172a;
}
QLineEdit, QSpinBox, QComboBox {
    background: #ffffff;
    border: 1px solid #cbd3e1;
    border-radius: 6px;
    padding: 4px 8px;
}
QLabel#sectionTitle {
    color: #475569;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 11px;
}
QLabel#canvasHint {
    color: #64748b;
    border: 1px dashed #cbd3e1;
    border-radius: 10px;
    background: #ffffff;
    font-size: 14px;
}
QLabel#urlLabel {
    color: #1d4ed8;
}
"""


def stylesheet_for(theme: str) -> str:
    return LIGHT_QSS if theme == "light" else DARK_QSS
