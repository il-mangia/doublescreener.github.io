# ruff: noqa: E402 - Qt richiede QT_QPA_PLATFORM prima degli import
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from doublescreener.config import Paths, Settings, SettingsManager  # noqa: E402
from doublescreener.core.models import Element, ElementContent  # noqa: E402
from doublescreener.pdf.renderer import PdfRenderer  # noqa: E402
from doublescreener.server.runtime import ServerRuntime  # noqa: E402
from doublescreener.ui import webengine  # noqa: E402, F401
from doublescreener.ui.i18n import LOCALES_DIR, Translator  # noqa: E402
from doublescreener.ui.pdf_dialog import PdfImportDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp(tmp_path_factory):
    settings_dir = tmp_path_factory.mktemp("qsettings")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(settings_dir),
    )
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("DoubleScreenerTest")
    app.setApplicationName("DoubleScreenerTest")
    return app


def test_locales_have_same_keys() -> None:
    it = json.loads((LOCALES_DIR / "it.json").read_text(encoding="utf-8"))
    en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    assert set(it) == set(en)
    assert all(isinstance(value, str) and value for value in it.values())
    assert all(isinstance(value, str) and value for value in en.values())


def test_translator_formats_and_falls_back(qapp) -> None:
    translator = Translator("en")
    assert translator.t("common.cancel") == "Cancel"
    assert translator.t("slides.new_name", n=3) == "Slide 3"
    assert translator.t("chiave.inesistente") == "chiave.inesistente"

    translator.set_language("it")
    assert translator.t("common.cancel") == "Annulla"
    assert translator.t("status.slide", index=2, total=9) == "Slide 2/9"


def test_pdf_dialog_validates_pages(qapp, paths: Paths, assets) -> None:
    meta = assets.save_bytes(_pdf_bytes(), "doc.pdf")
    dialog = PdfImportDialog(meta, PdfRenderer(paths, assets), Translator("it"))

    dialog.pages_edit.setText("9")
    dialog.accept()
    assert dialog.pages() == [1, 2, 3]

    dialog.pages_edit.setText("2-3")
    dialog.name_edit.setText("Pagina {page}")
    dialog.accept()
    assert dialog.pages() == [2, 3]


def _pdf_bytes() -> bytes:
    import pymupdf

    document = pymupdf.open()
    for _ in range(3):
        page = document.new_page()
        page.insert_text((72, 72), "Demo", fontsize=24)
    data = document.tobytes()
    document.close()
    return data


def test_main_window_smoke(qapp, tmp_path) -> None:
    from doublescreener.ui.main_window import MainWindow

    paths = Paths(tmp_path / "data").ensure()
    runtime = ServerRuntime(paths, host="127.0.0.1", port=0)
    runtime.start()
    try:
        window = MainWindow(
            paths,
            runtime,
            SettingsManager(paths),
            Settings(lang="it"),
            enable_canvas=False,
        )
        store = runtime.app.state.ds.store
        controller = runtime.app.state.ds.controller

        project = store.create("Demo")
        window.open_project(project.id)
        assert window.project is not None
        assert window.project.id == project.id

        window.add_html_slide()
        assert window.project is not None
        assert len(window.project.slides) == 2

        # Modifica di un elemento via intent del canvas, senza QtWebEngine.
        element = Element(type="text", content=ElementContent(text="Ciao"))
        window.project.slides[0].elements.append(element)
        window.slides_panel.set_current_index(0)
        window._on_canvas_intent(
            {
                "action": "element.update",
                "payload": {"id": element.id, "changes": {"rect": {"x": 40, "y": 50}}},
            }
        )
        assert window.project.slides[0].elements[0].rect.x == 40
        assert window.history.can_undo

        window._undo()
        assert window.project.slides[0].elements[0].rect.x == 0

        window.slides_panel.set_current_index(0)
        window.start_presentation()
        assert controller.snapshot().project_id == project.id
        assert controller.snapshot().index == 0

        window.next_action.trigger()
        assert controller.snapshot().index == 1

        window.black_action.setChecked(True)
        assert controller.snapshot().black is True
        window.black_action.setChecked(False)
        assert controller.snapshot().black is False

        ids = [slide.id for slide in window.project.slides]
        window.reorder_slides([ids[1], ids[0]])
        assert [slide.id for slide in window.project.slides] == [ids[1], ids[0]]

        # Palette, inspector, template e temi (M8).
        window.palette_panel._buttons["text"].click()
        current_slide = window._current_slide()
        assert current_slide is not None
        created_id = window._selection[0]
        assert any(el.id == created_id for el in current_slide.elements)
        window._refresh_inspector()
        assert window.inspector_panel._element is not None
        assert window.inspector_panel._element.id == created_id

        window.inspector_panel.size_spin.setValue(64.0)
        assert current_slide.element(created_id).style.font_size == 64.0

        slide_count_before = len(window.project.slides)
        window.add_template_slide("two_columns")
        assert len(window.project.slides) == slide_count_before + 1

        window.apply_theme("ocean")
        assert window.project.theme == "ocean"

        window.stop_presentation()
        assert controller.snapshot().project_id is None
        window.close()
    finally:
        runtime.stop()
