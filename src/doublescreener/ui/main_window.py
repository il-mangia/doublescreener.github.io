"""Finestra principale della regia."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import Paths, Settings, SettingsManager
from ..core.commands import add_element, delete_element, update_element
from ..core.history import Command, History
from ..core.ids import new_id
from ..core.models import Project, Slide
from ..core.templates import TEMPLATES, build_slide, element_defaults
from ..core.themes import THEMES, apply_to_project, get_theme
from ..pdf.importer import build_slides
from ..server.runtime import ServerRuntime
from .canvas import CanvasView
from .display import DisplayManager
from .i18n import Translator
from .inspector_panel import InspectorPanel
from .palette import PalettePanel
from .pdf_dialog import PdfImportDialog
from .presenter_panel import PresenterPanel
from .projects_panel import ProjectsPanel
from .settings_dialog import SettingsDialog
from .slides_panel import SlidesPanel

log = logging.getLogger(__name__)


class _ControllerBridge(QObject):
    """Porta gli eventi del controller (thread server) nel thread Qt."""

    event = pyqtSignal(str, object)


class MainWindow(QMainWindow):
    def __init__(
        self,
        paths: Paths,
        runtime: ServerRuntime,
        settings_manager: SettingsManager,
        settings: Settings,
        *,
        enable_canvas: bool = True,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.runtime = runtime
        self.settings_manager = settings_manager
        self.settings = settings
        self._canvas_enabled = enable_canvas
        state = runtime.app.state.ds
        self.store = state.store
        self.assets = state.assets
        self.pdf_renderer = state.pdf
        self.controller = state.controller
        self.hub = state.hub

        self.project: Project | None = None
        self.canvas: CanvasView | None = None
        self.history = History()
        self._selection: list[str] = []
        self._zoom = 1.0
        self._grid = False
        self.translator = Translator(settings.lang)
        self.display_manager = DisplayManager(self)

        self._bridge = _ControllerBridge()
        self._bridge.event.connect(self._on_presentation_event)
        self._unsubscribe = self.controller.subscribe(
            lambda kind, snapshot: self._bridge.event.emit(kind, snapshot)
        )

        self._build_actions()
        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self.translator.language_changed.connect(self.retranslate)
        self.retranslate()
        self._restore_geometry()

        self._clients_timer = QTimer(self)
        self._clients_timer.setInterval(2000)
        self._clients_timer.timeout.connect(self._refresh_state)
        self._clients_timer.start()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_project)

        self.presenter_panel.set_url(self._player_url())
        self._refresh_state()
        self._startup()

    # -- costruzione ------------------------------------------------------

    def _build_actions(self) -> None:
        self.new_action = QAction(self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self._new_project)

        self.open_action = QAction(self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.projects_panel_focus)

        self.settings_action = QAction(self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.triggered.connect(self.open_settings)

        self.quit_action = QAction(self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)

        self.save_action = QAction(self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self._save_project)

        self.undo_action = QAction(self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._undo)

        self.redo_action = QAction(self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self._redo)

        self.duplicate_element_action = QAction(self)
        self.duplicate_element_action.triggered.connect(self._duplicate_selection)

        self.delete_element_action = QAction(self)
        self.delete_element_action.triggered.connect(self._delete_selection)

        self.grid_action = QAction(self)
        self.grid_action.setCheckable(True)
        self.grid_action.setShortcut(QKeySequence("Ctrl+G"))
        self.grid_action.toggled.connect(self._set_grid)

        self.zoom_in_action = QAction(self)
        self.zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        self.zoom_in_action.triggered.connect(lambda: self._zoom_by(1.25))

        self.zoom_out_action = QAction(self)
        self.zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        self.zoom_out_action.triggered.connect(lambda: self._zoom_by(0.8))

        self.zoom_fit_action = QAction(self)
        self.zoom_fit_action.setShortcut(QKeySequence("Ctrl+0"))
        self.zoom_fit_action.triggered.connect(lambda: self._set_zoom(1.0))

        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions: dict[str, QAction] = {}
        for theme in THEMES:
            action = QAction(self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, theme_id=theme.id: self.apply_theme(theme_id)
            )
            self.theme_group.addAction(action)
            self.theme_actions[theme.id] = action

        self.start_action = QAction(self)
        self.start_action.setShortcut(QKeySequence("F5"))
        self.start_action.triggered.connect(self.start_presentation)

        self.stop_action = QAction(self)
        self.stop_action.setShortcut(QKeySequence("Shift+F5"))
        self.stop_action.triggered.connect(self.stop_presentation)

        self.next_action = QAction(self)
        self.next_action.setShortcut(QKeySequence(Qt.Key.Key_PageDown))
        self.next_action.triggered.connect(lambda: self._step(1))

        self.prev_action = QAction(self)
        self.prev_action.setShortcut(QKeySequence(Qt.Key.Key_PageUp))
        self.prev_action.triggered.connect(lambda: self._step(-1))

        self.black_action = QAction(self)
        self.black_action.setCheckable(True)
        self.black_action.setShortcut(QKeySequence("B"))
        self.black_action.toggled.connect(self._set_black)

        self.display_action = QAction(self)
        self.display_action.setShortcut(QKeySequence("F11"))
        self.display_action.triggered.connect(self.open_on_display)

        self.browser_action = QAction(self)
        self.browser_action.triggered.connect(self.open_in_browser)

        self.lang_group = QActionGroup(self)
        self.lang_group.setExclusive(True)
        self.lang_it = QAction(self)
        self.lang_it.setCheckable(True)
        self.lang_it.triggered.connect(lambda: self._switch_language("it"))
        self.lang_en = QAction(self)
        self.lang_en.setCheckable(True)
        self.lang_en.triggered.connect(lambda: self._switch_language("en"))
        self.lang_group.addAction(self.lang_it)
        self.lang_group.addAction(self.lang_en)

        self.about_action = QAction(self)
        self.about_action.triggered.connect(self.show_about)

    def _build_ui(self) -> None:
        self.setMinimumSize(960, 640)
        self.resize(1320, 820)

        self.projects_panel = ProjectsPanel(self.store, self.translator)
        self.slides_panel = SlidesPanel(self.translator)
        self.presenter_panel = PresenterPanel(self.translator)
        self.inspector_panel = InspectorPanel(self.translator)
        self.palette_panel = PalettePanel(self.translator)

        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self.projects_panel)
        left.addWidget(self.slides_panel)
        left.setStretchFactor(0, 1)
        left.setStretchFactor(1, 2)

        self.left_dock = QDockWidget(self)
        self.left_dock.setObjectName("projectsDock")
        self.left_dock.setWidget(left)
        self.left_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.left_dock.setMinimumWidth(250)

        self.right_dock = QDockWidget(self)
        self.right_dock.setObjectName("inspectorDock")
        self.right_dock.setWidget(self.inspector_panel)
        self.right_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.right_dock.setMinimumWidth(300)

        presenter_scroll = QScrollArea()
        presenter_scroll.setWidgetResizable(True)
        presenter_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        presenter_scroll.setWidget(self.presenter_panel)
        self.bottom_dock = QDockWidget(self)
        self.bottom_dock.setObjectName("presenterDock")
        self.bottom_dock.setWidget(presenter_scroll)
        self.bottom_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.bottom_dock.setMinimumHeight(200)

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.palette_panel)
        self.canvas_hint = QLabel()
        self.canvas_hint.setObjectName("canvasHint")
        self.canvas_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_hint.setWordWrap(True)
        self.canvas_stack = QStackedWidget(central)
        self.canvas_stack.addWidget(self.canvas_hint)
        central_layout.addWidget(self.canvas_stack)
        self.setCentralWidget(central)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.bottom_dock)

        self.projects_panel.project_selected.connect(self.open_project)
        self.projects_panel.project_deleted.connect(self._on_project_deleted)
        self.projects_panel.project_renamed.connect(self._on_project_renamed)
        self.slides_panel.current_changed.connect(self._show_slide)
        self.slides_panel.add_html_requested.connect(self.add_html_slide)
        self.slides_panel.add_pdf_requested.connect(self.import_pdf)
        self.slides_panel.duplicate_requested.connect(self.duplicate_slide)
        self.slides_panel.delete_requested.connect(self.delete_slide)
        self.slides_panel.move_requested.connect(self.move_slide)
        self.slides_panel.reorder_requested.connect(self.reorder_slides)
        self.presenter_panel.start_requested.connect(self.start_presentation)
        self.presenter_panel.stop_requested.connect(self.stop_presentation)
        self.presenter_panel.next_requested.connect(lambda: self._step(1))
        self.presenter_panel.prev_requested.connect(lambda: self._step(-1))
        self.presenter_panel.black_toggled.connect(self._set_black)
        self.presenter_panel.display_requested.connect(self.open_on_display)
        self.presenter_panel.browser_requested.connect(self.open_in_browser)
        self.inspector_panel.element_changed.connect(self._on_inspector_change)
        self.inspector_panel.image_requested.connect(self._pick_image)
        self.inspector_panel.preview_requested.connect(self._preview_animation)
        self.palette_panel.element_requested.connect(self._add_element)

    def _build_menus(self) -> None:
        self.file_menu = self.menuBar().addMenu("")
        self.file_menu.addAction(self.new_action)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.save_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.settings_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)

        self.edit_menu = self.menuBar().addMenu("")
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.duplicate_element_action)
        self.edit_menu.addAction(self.delete_element_action)

        self.view_menu = self.menuBar().addMenu("")
        self.view_menu.addAction(self.grid_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.zoom_in_action)
        self.view_menu.addAction(self.zoom_out_action)
        self.view_menu.addAction(self.zoom_fit_action)

        self.slide_menu = self.menuBar().addMenu("")
        self.new_slide_action = self.slide_menu.addAction("")
        self.new_slide_action.triggered.connect(self.add_html_slide)
        self.pdf_slide_action = self.slide_menu.addAction("")
        self.pdf_slide_action.triggered.connect(self.import_pdf)
        self.template_menu = self.slide_menu.addMenu("")
        self.template_actions: list[QAction] = []
        for template in TEMPLATES:
            action = QAction(self)
            action.triggered.connect(
                lambda _checked=False, template_id=template.id: self.add_template_slide(
                    template_id
                )
            )
            action.setData(template.name_key)
            self.template_menu.addAction(action)
            self.template_actions.append(action)

        self.theme_menu = self.menuBar().addMenu("")
        for theme in THEMES:
            self.theme_menu.addAction(self.theme_actions[theme.id])

        self.presentation_menu = self.menuBar().addMenu("")
        self.presentation_menu.addAction(self.start_action)
        self.presentation_menu.addAction(self.stop_action)
        self.presentation_menu.addSeparator()
        self.presentation_menu.addAction(self.prev_action)
        self.presentation_menu.addAction(self.next_action)
        self.presentation_menu.addAction(self.black_action)
        self.presentation_menu.addSeparator()
        self.presentation_menu.addAction(self.display_action)
        self.presentation_menu.addAction(self.browser_action)

        self.language_menu = self.menuBar().addMenu("")
        self.language_menu.addAction(self.lang_it)
        self.language_menu.addAction(self.lang_en)

        self.help_menu = self.menuBar().addMenu("")
        self.help_menu.addAction(self.about_action)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        self.toolbar = toolbar
        for action in (
            self.start_action,
            self.stop_action,
            self.prev_action,
            self.next_action,
            self.black_action,
        ):
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addAction(self.display_action)

        spacer = QWidget(toolbar)
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(spacer)
        self.slide_status = QLabel()
        toolbar.addWidget(self.slide_status)

    def _build_statusbar(self) -> None:
        self.server_label = QLabel()
        self.clients_label = QLabel()
        self.statusBar().addPermanentWidget(self.clients_label)
        self.statusBar().addPermanentWidget(self.server_label)

    # -- testi ------------------------------------------------------------

    def retranslate(self) -> None:
        t = self.translator.t
        self.file_menu.setTitle(t("menu.file"))
        self.edit_menu.setTitle(t("menu.edit"))
        self.view_menu.setTitle(t("menu.view"))
        self.presentation_menu.setTitle(t("menu.presentation"))
        self.language_menu.setTitle(t("menu.language"))
        self.help_menu.setTitle(t("menu.help"))
        self.new_action.setText(t("menu.file.new"))
        self.open_action.setText(t("menu.file.open"))
        self.save_action.setText(t("menu.file.save"))
        self.settings_action.setText(t("menu.file.settings"))
        self.quit_action.setText(t("menu.file.quit"))
        self.undo_action.setText(t("menu.edit.undo"))
        self.redo_action.setText(t("menu.edit.redo"))
        self.duplicate_element_action.setText(t("menu.edit.duplicate"))
        self.delete_element_action.setText(t("menu.edit.delete"))
        self.grid_action.setText(t("menu.view.grid"))
        self.zoom_in_action.setText(t("menu.view.zoom_in"))
        self.zoom_out_action.setText(t("menu.view.zoom_out"))
        self.zoom_fit_action.setText(t("menu.view.zoom_fit"))
        self.slide_menu.setTitle(t("menu.slide"))
        self.new_slide_action.setText(t("menu.slide.new"))
        self.pdf_slide_action.setText(t("menu.slide.pdf"))
        self.template_menu.setTitle(t("menu.slide.templates"))
        for action in self.template_actions:
            action.setText(t(str(action.data())))
        self.theme_menu.setTitle(t("menu.theme"))
        for theme in THEMES:
            self.theme_actions[theme.id].setText(t(theme.name_key))
        self.start_action.setText(t("menu.presentation.start"))
        self.stop_action.setText(t("menu.presentation.stop"))
        self.next_action.setText(t("menu.presentation.next"))
        self.prev_action.setText(t("menu.presentation.prev"))
        self.black_action.setText(t("menu.presentation.black"))
        self.display_action.setText(t("menu.presentation.display"))
        self.browser_action.setText(t("menu.presentation.browser"))
        self.lang_it.setText(t("menu.language.it"))
        self.lang_en.setText(t("menu.language.en"))
        self.about_action.setText(t("menu.help.about"))
        self.left_dock.setWindowTitle(t("dock.projects"))
        self.right_dock.setWindowTitle(t("dock.inspector"))
        self.bottom_dock.setWindowTitle(t("dock.presenter"))
        self.canvas_hint.setText(
            t("canvas.project", name=self.project.name)
            if self.project
            else t("canvas.placeholder")
        )
        self.lang_it.setChecked(self.translator.language == "it")
        self.lang_en.setChecked(self.translator.language == "en")
        self._sync_theme_actions()
        self._update_window_title()
        self._refresh_statusbar()
        if self.canvas is not None:
            self.canvas.send({"type": "lang", "lang": self.translator.language})

    # -- avvio e window state --------------------------------------------

    def _startup(self) -> None:
        project_id = self.settings.last_project_id
        if project_id and self.store.exists(project_id):
            self.open_project(project_id)
        self._refresh_state()

    def _restore_geometry(self) -> None:
        qsettings = QSettings()
        geometry = qsettings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        window_state = qsettings.value("window/state")
        if window_state is not None:
            self.restoreState(window_state)

    def _save_geometry(self) -> None:
        qsettings = QSettings()
        qsettings.setValue("window/geometry", self.saveGeometry())
        qsettings.setValue("window/state", self.saveState())

    def activate(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # -- progetti ---------------------------------------------------------

    def projects_panel_focus(self) -> None:
        self.left_dock.show()
        self.left_dock.raise_()
        self.projects_panel.focus_list()

    def _new_project(self) -> None:
        self.projects_panel.create_project()

    def open_project(self, project_id: str) -> None:
        try:
            project, warning = self.store.load(project_id)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        if warning:
            QMessageBox.information(
                self, self.translator.t("dialog.info"), warning
            )
        snapshot = self.controller.snapshot()
        if snapshot.project_id and snapshot.project_id != project_id:
            self.controller.close()
        self.project = project
        self.projects_panel.set_current(project.id)
        self.slides_panel.set_slides(project)
        self.presenter_panel.set_project(project)
        self.history.clear()
        self._selection = []
        self._update_history_actions()
        self._sync_theme_actions()
        self.settings = self.settings.model_copy(update={"last_project_id": project.id})
        self._save_settings()
        self.retranslate()
        self._show_slide(0)
        self._refresh_state()

    def _on_project_deleted(self, project_id: str) -> None:
        if self.project and self.project.id == project_id:
            snapshot = self.controller.snapshot()
            if snapshot.project_id == project_id:
                self.controller.close()
            self.project = None
            self.slides_panel.set_slides(None)
            self.presenter_panel.set_project(None)
            self.history.clear()
            self._selection = []
            self._update_history_actions()
            self.inspector_panel.set_selection([])
            self._sync_theme_actions()
            self.canvas_stack.setCurrentWidget(self.canvas_hint)
            self.retranslate()
        if self.settings.last_project_id == project_id:
            self.settings = self.settings.model_copy(update={"last_project_id": None})
            self._save_settings()
        self._refresh_state()

    def _on_project_renamed(self, project_id: str) -> None:
        if not self.project or self.project.id != project_id:
            return
        try:
            self.project = self.store.get(project_id)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        self.presenter_panel.set_project(self.project)
        self.retranslate()

    def _save_project(self) -> None:
        if self.project is None:
            return
        self._save_timer.stop()
        try:
            self.project = self.store.save(self.project)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        self.presenter_panel.set_project(self.project)
        self.statusBar().showMessage(self.translator.t("status.saved"), 1500)

    def _schedule_save(self) -> None:
        if self.project is None:
            return
        self._save_timer.start(self.settings.autosave_ms)
        self.statusBar().showMessage(self.translator.t("status.modified"), 2000)

    def _save_settings(self) -> None:
        try:
            self.settings_manager.save(self.settings)
        except Exception:
            log.exception("impossibile salvare le impostazioni")

    # -- canvas -----------------------------------------------------------

    def _canvas_url(self) -> str:
        return f"http://127.0.0.1:{self.runtime.port}/editor-canvas"

    def _ensure_canvas(self) -> CanvasView | None:
        if not self._canvas_enabled:
            return None
        if self.canvas is None:
            self.canvas = CanvasView(
                self._canvas_url(),
                self,
                profile_path=str(self.paths.root / "cache" / "webengine"),
            )
            self.canvas.intent.connect(self._on_canvas_intent)
            self.canvas.ready.connect(self._refresh_canvas)
            self.canvas_stack.addWidget(self.canvas)
        self.canvas_stack.setCurrentWidget(self.canvas)
        return self.canvas

    def _show_slide(self, index: int) -> None:
        if self.project is None:
            return
        index = max(0, min(index, len(self.project.slides) - 1))
        self._selection = []
        self._update_history_actions()
        self._refresh_inspector()
        canvas = self._ensure_canvas()
        if canvas is None:
            return
        canvas.set_slide(
            self.project,
            self.project.slides[index],
            index,
            selection=[],
            zoom=self._zoom,
            grid=self._grid,
            lang=self.translator.language,
            pdf_width=self.settings.pdf_render_width,
        )

    def _refresh_canvas(self) -> None:
        if self.project is None:
            return
        index = max(
            0, min(self.slides_panel.current_index(), len(self.project.slides) - 1)
        )
        canvas = self._ensure_canvas()
        if canvas is None:
            return
        canvas.set_slide(
            self.project,
            self.project.slides[index],
            index,
            selection=self._selection,
            zoom=self._zoom,
            grid=self._grid,
            lang=self.translator.language,
            pdf_width=self.settings.pdf_render_width,
        )

    def _set_grid(self, checked: bool) -> None:
        self._grid = bool(checked)
        if self.canvas is not None:
            self.canvas.set_grid(self._grid)

    def _zoom_by(self, factor: float) -> None:
        self._set_zoom(self._zoom * factor)

    def _set_zoom(self, value: float) -> None:
        self._zoom = max(0.25, min(float(value), 2.0))
        if self.canvas is not None:
            self.canvas.set_zoom(self._zoom)

    def _on_canvas_intent(self, payload: dict) -> None:
        action = payload.get("action")
        data = payload.get("payload")
        if not isinstance(data, dict):
            data = {}

        if action == "selection.change":
            ids = data.get("ids")
            self._selection = [str(item) for item in ids] if isinstance(ids, list) else []
            self._update_history_actions()
            self._refresh_inspector()
            return
        if action == "zoom.change":
            self._zoom = max(0.25, min(float(data.get("zoom") or 1.0), 2.0))
            return
        if self.project is None:
            return

        index = max(
            0, min(self.slides_panel.current_index(), len(self.project.slides) - 1)
        )
        slide = self.project.slides[index]
        commands: list[Command] = []

        if action == "element.update":
            element_id = data.get("id")
            changes = data.get("changes")
            if isinstance(element_id, str) and isinstance(changes, dict):
                commands.append(
                    update_element(
                        slide.id,
                        element_id,
                        changes,
                        merge_key=f"element:{element_id}",
                    )
                )
        elif action == "text.edit":
            element_id = data.get("id")
            content = data.get("content")
            if isinstance(element_id, str) and isinstance(content, dict):
                try:
                    element = slide.element(element_id)
                except KeyError:
                    pass
                else:
                    merged = element.content.model_dump()
                    merged.update(content)
                    commands.append(
                        update_element(
                            slide.id,
                            element_id,
                            {"content": merged},
                            merge_key=f"text:{element_id}",
                        )
                    )
        elif action == "element.delete":
            ids = data.get("ids")
            targets = [str(item) for item in ids] if isinstance(ids, list) else []
            existing = {element.id for element in slide.elements}
            for element_id in targets:
                if element_id in existing:
                    commands.append(delete_element(slide.id, element_id))
            self._selection = [
                item for item in self._selection if item not in set(targets)
            ]
        elif action == "element.duplicate":
            ids = data.get("ids")
            targets = [str(item) for item in ids] if isinstance(ids, list) else []
            for element_id in targets:
                try:
                    original = slide.element(element_id)
                except KeyError:
                    continue
                clone = original.model_copy(deep=True)
                clone.id = new_id("element")
                clone.rect.x += 24
                clone.rect.y += 24
                commands.append(add_element(slide.id, clone))
        elif action == "element.reorder":
            direction = 1 if int(data.get("direction") or 1) >= 0 else -1
            ids = data.get("ids")
            targets = [str(item) for item in ids] if isinstance(ids, list) else []
            for element_id in targets:
                try:
                    element = slide.element(element_id)
                except KeyError:
                    continue
                commands.append(
                    update_element(
                        slide.id,
                        element_id,
                        {"z": element.z + direction},
                        merge_key=f"z:{element_id}",
                    )
                )
        elif action == "slide.request":
            self._refresh_canvas()
            return
        else:
            return

        if commands:
            self._apply(commands)

    def _apply(self, commands: list[Command], *, refresh_inspector: bool = True) -> None:
        if self.project is None:
            return
        try:
            for command in commands:
                self.history.execute(self.project, command)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            self._refresh_canvas()
            return
        self._update_history_actions()
        self._refresh_canvas()
        if refresh_inspector:
            self._refresh_inspector()
        self._schedule_save()

    def _undo(self) -> None:
        if self.project is None or not self.history.can_undo:
            return
        self.history.undo(self.project)
        self._selection = []
        self._update_history_actions()
        self._refresh_canvas()
        self._refresh_inspector()
        self._schedule_save()

    def _redo(self) -> None:
        if self.project is None or not self.history.can_redo:
            return
        self.history.redo(self.project)
        self._selection = []
        self._update_history_actions()
        self._refresh_canvas()
        self._refresh_inspector()
        self._schedule_save()

    def _duplicate_selection(self) -> None:
        if self._selection:
            self._on_canvas_intent(
                {"action": "element.duplicate", "payload": {"ids": list(self._selection)}}
            )

    def _delete_selection(self) -> None:
        if self._selection:
            self._on_canvas_intent(
                {"action": "element.delete", "payload": {"ids": list(self._selection)}}
            )

    def _update_history_actions(self) -> None:
        has_project = self.project is not None
        self.undo_action.setEnabled(has_project and self.history.can_undo)
        self.redo_action.setEnabled(has_project and self.history.can_redo)
        has_selection = has_project and bool(self._selection)
        self.duplicate_element_action.setEnabled(has_selection)
        self.delete_element_action.setEnabled(has_selection)

    # -- inspector, palette, temi ------------------------------------------

    def _current_slide(self) -> Slide | None:
        if self.project is None:
            return None
        index = max(
            0, min(self.slides_panel.current_index(), len(self.project.slides) - 1)
        )
        return self.project.slides[index]

    def _refresh_inspector(self) -> None:
        slide = self._current_slide()
        if slide is None:
            self.inspector_panel.set_selection([])
            return
        by_id = {element.id: element for element in slide.elements}
        self.inspector_panel.set_selection(
            [by_id[element_id] for element_id in self._selection if element_id in by_id]
        )

    def _on_inspector_change(
        self, element_id: str, changes: dict, merge_key: str
    ) -> None:
        slide = self._current_slide()
        if slide is None:
            return
        try:
            slide.element(element_id)
        except KeyError:
            return
        command = update_element(slide.id, element_id, changes, merge_key=merge_key)
        self._apply([command], refresh_inspector=False)

    def _pick_image(self, element_id: str) -> None:
        slide = self._current_slide()
        if slide is None:
            return
        try:
            element = slide.element(element_id)
        except KeyError:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.translator.t("inspector.image.choose"),
            "",
            self.translator.t("inspector.image.filter"),
        )
        if not path:
            return
        try:
            meta = self.assets.save_bytes(Path(path).read_bytes(), Path(path).name)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        content = element.content.model_dump()
        content["asset_id"] = meta.id
        content["src"] = None
        if not content.get("alt"):
            content["alt"] = meta.original_name
        command = update_element(
            slide.id,
            element_id,
            {"content": content},
            merge_key=f"inspector:{element_id}:content.image",
        )
        self._apply([command])

    def _preview_animation(self, element_id: str) -> None:
        slide = self._current_slide()
        if slide is None or self.canvas is None:
            return
        try:
            element = slide.element(element_id)
        except KeyError:
            return
        self.canvas.patch_element(element)
        self.canvas.send({"type": "play_animation", "id": element_id})

    def _add_element(self, kind: str) -> None:
        slide = self._current_slide()
        if self.project is None or slide is None:
            return
        theme = get_theme(self.project.theme)
        try:
            element = element_defaults(kind, self.project.canvas, theme=theme)  # type: ignore[arg-type]
        except ValueError:
            return
        self._selection = [element.id]
        self._apply([add_element(slide.id, element)])

    def add_template_slide(self, template_id: str) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        theme = get_theme(self.project.theme)
        number = len(self.project.slides) + 1
        slide = build_slide(
            template_id,
            self.project.canvas,
            name=self.translator.t("template.slide_name", n=number),
            theme=theme,
        )
        self.project.slides.append(slide)
        self._save_project()
        self.slides_panel.set_slides(self.project, select=len(self.project.slides) - 1)
        self._show_slide(len(self.project.slides) - 1)

    def apply_theme(self, theme_id: str) -> None:
        if self.project is None:
            return
        apply_to_project(self.project, theme_id)
        self._save_project()
        self._sync_theme_actions()
        self._refresh_canvas()
        self._refresh_inspector()
        self.statusBar().showMessage(
            self.translator.t("theme.applied", name=self.translator.t(f"theme.{theme_id}")),
            2000,
        )

    def _sync_theme_actions(self) -> None:
        current = self.project.theme if self.project else "dark"
        for theme_id, action in self.theme_actions.items():
            action.setChecked(theme_id == current)

    # -- slide ------------------------------------------------------------

    def _require_project(self) -> bool:
        if self.project is None:
            QMessageBox.information(
                self, self.translator.t("dialog.info"), self.translator.t("project.none")
            )
            return False
        return True

    def add_html_slide(self) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        number = len(self.project.slides) + 1
        slide = Slide(name=self.translator.t("slides.new_name", n=number))
        self.project.slides.append(slide)
        self._save_project()
        self.slides_panel.set_slides(self.project, select=len(self.project.slides) - 1)
        self._show_slide(len(self.project.slides) - 1)

    def duplicate_slide(self, row: int) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        if not 0 <= row < len(self.project.slides):
            return
        original = self.project.slides[row]
        clone = original.model_copy(deep=True)
        clone.id = new_id("slide")
        clone.name = f"{original.name} {self.translator.t('slides.duplicate_suffix')}"
        for element in clone.elements:
            element.id = new_id("element")
        self.project.slides.insert(row + 1, clone)
        self._save_project()
        self.slides_panel.set_slides(self.project, select=row + 1)
        self._show_slide(row + 1)

    def delete_slide(self, row: int) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        if len(self.project.slides) <= 1 or not 0 <= row < len(self.project.slides):
            return
        del self.project.slides[row]
        self._save_project()
        selected = min(row, len(self.project.slides) - 1)
        self.slides_panel.set_slides(self.project, select=selected)
        self._show_slide(selected)

    def move_slide(self, row: int, target: int) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        slides = self.project.slides
        if not (0 <= row < len(slides) and 0 <= target < len(slides)):
            return
        slides.insert(target, slides.pop(row))
        self._save_project()
        self.slides_panel.set_slides(self.project, select=target)
        self._show_slide(target)

    def reorder_slides(self, order: list[str]) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        by_id = {slide.id: slide for slide in self.project.slides}
        if len(order) != len(by_id) or set(order) != set(by_id):
            self.slides_panel.set_slides(self.project, select=self.slides_panel.current_index())
            return
        selected = self.slides_panel.current_index()
        self.project.slides = [by_id[slide_id] for slide_id in order]
        self._save_project()
        self.slides_panel.set_slides(self.project, select=selected)
        self._show_slide(selected)

    def import_pdf(self) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.translator.t("pdf.file.title"),
            "",
            self.translator.t("pdf.file.filter"),
        )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
            meta = self.assets.save_bytes(data, Path(path).name)
            if meta.kind != "pdf":
                raise ValueError(self.translator.t("pdf.file.invalid"))
            dialog = PdfImportDialog(meta, self.pdf_renderer, self.translator, self)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            slides = build_slides(
                meta, dialog.pages(), name_template=dialog.name_template()
            )
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        start = len(self.project.slides)
        self.project.slides.extend(slides)
        self._save_project()
        self.slides_panel.set_slides(self.project, select=start)
        self._show_slide(start)

    # -- presentazione ----------------------------------------------------

    def _player_url(self) -> str:
        state = self.runtime.app.state.ds
        host = state.lan_ip or "127.0.0.1"
        return f"http://{host}:{self.runtime.port}/p"

    def start_presentation(self) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        if not self.project.slides:
            return
        self._save_project()
        index = self.slides_panel.current_index()
        try:
            self.controller.open(self.project.id, index)
        except Exception as exc:
            QMessageBox.warning(self, self.translator.t("dialog.error"), str(exc))
            return
        self.statusBar().showMessage(
            self.translator.t("presentation.started"), 3000
        )
        self._refresh_state()

    def stop_presentation(self) -> None:
        if self.controller.snapshot().project_id:
            self.controller.close()
            self._refresh_state()

    def _step(self, delta: int) -> None:
        try:
            self.controller.step(delta)
        except ValueError:
            self.statusBar().showMessage(
                self.translator.t("presentation.inactive"), 2500
            )

    def _set_black(self, checked: bool) -> None:
        snapshot = self.controller.snapshot()
        if snapshot.project_id is None:
            if checked:
                self.black_action.blockSignals(True)
                self.black_action.setChecked(False)
                self.black_action.blockSignals(False)
            self.statusBar().showMessage(
                self.translator.t("presentation.inactive"), 2500
            )
            return
        with contextlib.suppress(ValueError):
            self.controller.set_black(checked)

    def _on_presentation_event(self, kind: str, snapshot: object) -> None:
        self.presenter_panel.update_presentation(snapshot)  # type: ignore[arg-type]
        if kind == "slide" and self.project is not None:
            index = getattr(snapshot, "index", 0)
            self.slides_panel.set_current_index(index)
            self._show_slide(index)
        if kind in ("open", "close", "slide", "state"):
            self._refresh_statusbar()
            self._update_window_title()

    def open_on_display(self) -> None:
        screens = DisplayManager.screens()
        if not screens:
            QMessageBox.information(
                self, self.translator.t("dialog.info"), self.translator.t("display.none")
            )
            return
        labels = [
            DisplayManager.screen_label(screen, index)
            for index, screen in enumerate(screens)
        ]
        label, ok = QInputDialog.getItem(
            self,
            self.translator.t("display.choose"),
            self.translator.t("display.screen"),
            labels,
            0,
            False,
        )
        if not ok:
            return
        screen = screens[labels.index(label)]
        self.display_manager.open_on_screen(self._player_url(), screen)

    def open_in_browser(self) -> None:
        self.display_manager.open_in_browser(self._player_url())

    # -- stato ------------------------------------------------------------

    def _refresh_state(self) -> None:
        snapshot = self.controller.snapshot()
        self.presenter_panel.update_presentation(snapshot)
        clients = self.hub.clients()
        self.presenter_panel.set_clients(clients)
        self._refresh_statusbar(len(clients))
        self._update_window_title()
        if snapshot.project_id and snapshot.slide_count:
            self.slide_status.setText(
                self.translator.t(
                    "status.slide",
                    index=snapshot.index + 1,
                    total=snapshot.slide_count,
                )
            )
        elif self.project is not None:
            self.slide_status.setText(
                self.translator.t(
                    "status.slide",
                    index=self.slides_panel.current_index() + 1,
                    total=len(self.project.slides),
                )
            )
        else:
            self.slide_status.setText("")

    def _refresh_statusbar(self, clients: int | None = None) -> None:
        if clients is None:
            clients = self.hub.client_count
        self.clients_label.setText(
            self.translator.t("status.clients", n=clients)
        )
        if self.runtime.running:
            self.server_label.setText(
                self.translator.t("status.server", url=self._player_url())
            )
        else:
            self.server_label.setText(self.translator.t("status.server.off"))

    def _update_window_title(self) -> None:
        base = "DoubleScreener"
        if self.project is not None:
            playing = self.controller.snapshot().project_id == self.project.id
            marker = " ▶" if playing else ""
            self.setWindowTitle(f"{self.project.name}{marker} — {base}")
        else:
            self.setWindowTitle(base)

    # -- lingua e impostazioni -------------------------------------------

    def _switch_language(self, lang: str) -> None:
        self.settings = self.settings.model_copy(update={"lang": lang})
        self._save_settings()
        self.translator.set_language(lang)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.translator, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        old = self.settings
        self.settings = dialog.result_settings()
        self._save_settings()
        state = self.runtime.app.state.ds
        state.settings = self.settings
        self.controller.set_lang(self.settings.lang)
        self.controller.set_pdf_width(self.settings.pdf_render_width)
        self.translator.set_language(self.settings.lang)
        if old.pdf_render_width != self.settings.pdf_render_width:
            self._refresh_canvas()
        if (old.port, old.bind) != (self.settings.port, self.settings.bind):
            QMessageBox.information(
                self,
                self.translator.t("settings.title"),
                self.translator.t("settings.restart_hint"),
            )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            self.translator.t("about.title"),
            self.translator.t("about.text", version=__version__),
        )

    # -- chiusura ---------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - API Qt
        self._clients_timer.stop()
        if self._save_timer.isActive():
            self._save_project()
        try:
            self._unsubscribe()
        except Exception:
            log.exception("errore nella disiscrizione dal controller")
        self.display_manager.close_all()
        try:
            if self.controller.snapshot().project_id:
                self.controller.close()
        except Exception:
            log.exception("errore nella chiusura della presentazione")
        self._save_geometry()
        self.settings = self.settings.model_copy(
            update={
                "last_project_id": self.project.id if self.project else None,
            }
        )
        self._save_settings()
        try:
            self.runtime.stop()
        except Exception:
            log.exception("errore nell'arresto del server")
        event.accept()
