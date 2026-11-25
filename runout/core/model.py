"""Modelo de datos de una pista."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Picture:
    data: bytes
    mime: str = "image/jpeg"
    desc: str = ""


@dataclass
class TrackMetadata:
    """Todos los valores como texto, con las claves de core/fields.py.

    Un valor vacío o ausente significa «sin este dato» (al guardar se borra).
    """
    values: dict[str, str] = field(default_factory=dict)
    pictures: dict[int, Picture] = field(default_factory=dict)   # tipo APIC -> imagen

    def get(self, key: str) -> str:
        return self.values.get(key, "") or ""

    def set(self, key: str, value: str | int | None) -> None:
        text = "" if value is None else str(value)
        if text:
            self.values[key] = text
        else:
            self.values.pop(key, None)

    def int(self, key: str) -> int | None:
        v = self.get(key)
        return int(v) if v.isdigit() else None

    # atajos usados por la tabla y el CSV
    @property
    def title(self) -> str:
        return self.get("title")

    @property
    def isrc(self) -> str:
        return self.get("isrc")

    @property
    def track(self) -> int | None:
        return self.int("track")

    @property
    def cover(self) -> Picture | None:
        return self.pictures.get(3)

    def copy(self) -> "TrackMetadata":
        return TrackMetadata(dict(self.values),
                             {k: Picture(p.data, p.mime, p.desc) for k, p in self.pictures.items()})

    def _norm(self):
        return ({k: v for k, v in self.values.items() if v},
                {k: (p.data, p.mime) for k, p in self.pictures.items()})

    def differs_from(self, other: "TrackMetadata") -> bool:
        return self._norm() != other._norm()


@dataclass
class FileStatus:
    """Lo que el archivo contiene realmente en disco."""
    format: str = "WAV"
    has_tags: bool = False   # alguna etiqueta (ID3, Vorbis Comments, átomos MP4)
    has_id3: bool = False
    has_cover: bool = False
    has_axml_isrc: bool = False
    has_info: bool = False
    has_bext: bool = False
    chunk_labels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""          # si no es apto para editar
