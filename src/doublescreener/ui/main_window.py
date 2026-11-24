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
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import Paths, Settings, SettingsManager
from ..core.ids import new_id
from ..core.models import Project, Slide
from ..pdf.importer import build_slides
from ..server.runtime import ServerRuntime
from .display import DisplayManager
from .i18n import Translator
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
    ) -> None:
        super().__init__()
        self.paths = paths
        self.runtime = runtime
        self.settings_manager = settings_manager
        self.settings = settings
        state = runtime.app.state.ds
        self.store = state.store
        self.assets = state.assets
        self.pdf_renderer = state.pdf
        self.controller = state.controller
        self.hub = state.hub

        self.project: Project | None = None
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
        self.right_dock.setObjectName("presenterDock")
        self.right_dock.setWidget(self.presenter_panel)
        self.right_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.right_dock.setMinimumWidth(280)

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(18, 18, 18, 18)
        self.canvas_hint = QLabel()
        self.canvas_hint.setObjectName("canvasHint")
        self.canvas_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_hint.setWordWrap(True)
        central_layout.addWidget(self.canvas_hint)
        self.setCentralWidget(central)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)

        self.projects_panel.project_selected.connect(self.open_project)
        self.projects_panel.project_deleted.connect(self._on_project_deleted)
        self.projects_panel.project_renamed.connect(self._on_project_renamed)
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

    def _build_menus(self) -> None:
        self.file_menu = self.menuBar().addMenu("")
        self.file_menu.addAction(self.new_action)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.settings_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)

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
        self.presentation_menu.setTitle(t("menu.presentation"))
        self.language_menu.setTitle(t("menu.language"))
        self.help_menu.setTitle(t("menu.help"))
        self.new_action.setText(t("menu.file.new"))
        self.open_action.setText(t("menu.file.open"))
        self.settings_action.setText(t("menu.file.settings"))
        self.quit_action.setText(t("menu.file.quit"))
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
        self.right_dock.setWindowTitle(t("dock.presenter"))
        self.canvas_hint.setText(
            t("canvas.project", name=self.project.name)
            if self.project
            else t("canvas.placeholder")
        )
        self.lang_it.setChecked(self.translator.language == "it")
        self.lang_en.setChecked(self.translator.language == "en")
        self._update_window_title()
        self._refresh_statusbar()

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
        self.settings = self.settings.model_copy(update={"last_project_id": project.id})
        self._save_settings()
        self.retranslate()
        self._refresh_state()

    def _on_project_deleted(self, project_id: str) -> None:
        if self.project and self.project.id == project_id:
            snapshot = self.controller.snapshot()
            if snapshot.project_id == project_id:
                self.controller.close()
            self.project = None
            self.slides_panel.set_slides(None)
            self.presenter_panel.set_project(None)
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
        self.project = self.store.save(self.project)
        self.presenter_panel.set_project(self.project)

    def _save_settings(self) -> None:
        try:
            self.settings_manager.save(self.settings)
        except Exception:
            log.exception("impossibile salvare le impostazioni")

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

    def delete_slide(self, row: int) -> None:
        if not self._require_project():
            return
        assert self.project is not None
        if len(self.project.slides) <= 1 or not 0 <= row < len(self.project.slides):
            return
        del self.project.slides[row]
        self._save_project()
        self.slides_panel.set_slides(
            self.project, select=min(row, len(self.project.slides) - 1)
        )

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
