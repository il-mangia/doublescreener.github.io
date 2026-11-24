"""Modelli di dominio (Pydantic v2) e migrazione dello schema.

Il modello è la fonte di verità: Qt, canvas e player sono tutte viste.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .errors import SchemaError
from .ids import new_id

SCHEMA_VERSION = 1
ID_PATTERN = r"^[a-z]{2,5}_[0-9A-Za-z]{1,32}$"

ElementType = Literal["text", "image", "button", "box", "line"]
SlideKind = Literal["html", "pdf_page"]
TransitionType = Literal["none", "fade", "slide", "zoom"]
TextAlign = Literal["left", "center", "right", "justify"]
ObjectFit = Literal["cover", "contain", "fill"]
AnimationName = Literal[
    "none",
    "fadeIn",
    "slideUp",
    "slideDown",
    "slideLeft",
    "slideRight",
    "zoomIn",
    "bounce",
]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    """Base comune: campi sconosciuti vietati, assegnamenti validati."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Rect(Model):
    x: float = 0.0
    y: float = 0.0
    w: float = Field(default=100.0, ge=0, le=16384)
    h: float = Field(default=100.0, ge=0, le=16384)


class Canvas(Model):
    width: int = Field(default=1920, ge=64, le=16384)
    height: int = Field(default=1080, ge=64, le=16384)
    background: str = "#101014"


class Transition(Model):
    type: TransitionType = "fade"
    duration_ms: int = Field(default=300, ge=0, le=10000)


class Animation(Model):
    enter: AnimationName = "none"
    duration_ms: int = Field(default=400, ge=0, le=60000)
    delay_ms: int = Field(default=0, ge=0, le=60000)
    easing: str = "ease-out"


class ElementContent(Model):
    text: str = ""
    href: str | None = None
    src: str | None = None
    alt: str = ""
    asset_id: str | None = Field(default=None, pattern=ID_PATTERN)


class ElementStyle(Model):
    font_family: str = "Inter"
    font_size: float = Field(default=32, ge=1, le=1000)
    font_weight: int = Field(default=400, ge=100, le=1000)
    line_height: float = Field(default=1.2, ge=0.1, le=10)
    letter_spacing: float = Field(default=0, ge=-50, le=200)
    color: str = "#ffffff"
    background: str = "transparent"
    padding: float = Field(default=0, ge=0, le=1000)
    border_radius: float = Field(default=0, ge=0, le=2000)
    border_width: float = Field(default=0, ge=0, le=100)
    border_color: str = "#000000"
    shadow: str | None = None
    text_align: TextAlign = "left"
    object_fit: ObjectFit = "cover"


class Element(Model):
    id: str = Field(default_factory=lambda: new_id("element"), pattern=ID_PATTERN)
    type: ElementType
    name: str = ""
    rect: Rect = Field(default_factory=Rect)
    rotation: float = 0.0
    opacity: float = Field(default=1.0, ge=0, le=1)
    z: int = 0
    locked: bool = False
    hidden: bool = False
    content: ElementContent = Field(default_factory=ElementContent)
    style: ElementStyle = Field(default_factory=ElementStyle)
    animation: Animation = Field(default_factory=Animation)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()


class PdfRef(Model):
    asset_id: str = Field(pattern=ID_PATTERN)
    page: int = Field(ge=1)
    source_name: str = ""


class Slide(Model):
    id: str = Field(default_factory=lambda: new_id("slide"), pattern=ID_PATTERN)
    kind: SlideKind = "html"
    name: str = "Slide"
    background: str | None = None
    elements: list[Element] = Field(default_factory=list)
    pdf: PdfRef | None = None
    notes: str = ""
    transition: Transition | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("il nome della slide non può essere vuoto")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> Slide:
        if self.kind == "pdf_page" and self.pdf is None:
            raise ValueError("una slide pdf_page richiede il riferimento pdf")
        if self.kind == "html" and self.pdf is not None:
            raise ValueError("una slide html non può avere un riferimento pdf")
        seen: set[str] = set()
        for element in self.elements:
            if element.id in seen:
                raise ValueError(f"id elemento duplicato: {element.id}")
            seen.add(element.id)
        return self

    def element(self, element_id: str) -> Element:
        for element in self.elements:
            if element.id == element_id:
                return element
        raise KeyError(f"elemento non trovato: {element_id}")


def _default_slides() -> list[Slide]:
    return [Slide(name="Slide 1")]


class Project(Model):
    schema_version: int = SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("project"), pattern=ID_PATTERN)
    name: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    canvas: Canvas = Field(default_factory=Canvas)
    default_transition: Transition = Field(default_factory=Transition)
    theme: str = "dark"
    slides: list[Slide] = Field(default_factory=_default_slides)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("il nome del progetto non può essere vuoto")
        if len(value) > 200:
            raise ValueError("il nome del progetto supera 200 caratteri")
        return value

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    @model_validator(mode="after")
    def _check_slides(self) -> Project:
        if not self.slides:
            raise ValueError("un progetto deve contenere almeno una slide")
        seen: set[str] = set()
        for slide in self.slides:
            if slide.id in seen:
                raise ValueError(f"id slide duplicato: {slide.id}")
            seen.add(slide.id)
        return self

    def slide_index(self, slide_id: str) -> int:
        for index, slide in enumerate(self.slides):
            if slide.id == slide_id:
                return index
        raise KeyError(f"slide non trovata: {slide_id}")

    def slide(self, slide_id: str) -> Slide:
        return self.slides[self.slide_index(slide_id)]

    def touch(self) -> None:
        self.updated_at = utcnow()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        return cls.model_validate(migrate(data))


class ProjectSummary(Model):
    id: str
    name: str
    slide_count: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Porta un dizionario al formato corrente.

    Le migrazioni reali verranno aggiunte qui man mano che lo schema evolve.
    """
    if not isinstance(data, dict):
        raise SchemaError("il progetto deve essere un oggetto JSON")
    version = data.get("schema_version", SCHEMA_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        raise SchemaError("schema_version non valido")
    if version < 1:
        raise SchemaError(f"schema_version non supportato: {version}")
    if version > SCHEMA_VERSION:
        raise SchemaError(
            f"progetto creato con una versione più recente (schema {version}, "
            f"supportato fino a {SCHEMA_VERSION})"
        )
    migrated = dict(data)
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated
