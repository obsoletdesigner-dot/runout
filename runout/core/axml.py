"""Chunk ``axml`` (EBU Tech 3352): ISRC dentro de XML EBUCore."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..i18n import tr


EBUCORE_NS = "urn:ebu:metadata-schema:ebuCore_2012"
DC_NS = "http://purl.org/dc/elements/1.1/"
ISRC_FORMAT_LINK = "http://www.ebu.ch/metadata/cs/ebu_IdentifierTypeCodeCS.xml#3.7"

_ISRC_IN_TEXT = re.compile(r"ISRC[:\s]*([A-Z]{2}[A-Z0-9]{3}[0-9]{7})", re.I)
_BARE_ISRC = re.compile(r"^\s*([A-Z]{2}[A-Z0-9]{3}[0-9]{7})\s*$", re.I)


class AxmlNotEditable(Exception):
    """El axml existente no es EBUCore válido: no se modifica."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ns(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _clean(raw: bytes) -> bytes:
    # algunos programas rellenan con NUL o espacios
    return raw.rstrip(b"\x00 \r\n\t")


def build_new(isrc: str) -> bytes:
    """axml nuevo, igual que el ejemplo de EBU Tech 3352."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ebucore:ebuCoreMain xmlns:dc="%s" xmlns:ebucore="%s">\n'
        '  <ebucore:coreMetadata>\n'
        '    <ebucore:identifier typeLabel="GUID" typeDefinition="Globally Unique Identifier" '
        'formatLabel="ISRC" formatDefinition="International Standard Recording Code" '
        'formatLink="%s">\n'
        '      <dc:identifier>ISRC:%s</dc:identifier>\n'
        '    </ebucore:identifier>\n'
        '  </ebucore:coreMetadata>\n'
        '</ebucore:ebuCoreMain>\n'
    ) % (DC_NS, EBUCORE_NS, ISRC_FORMAT_LINK, isrc)
    return xml.encode("utf-8")


def _isrc_identifier_nodes(root: ET.Element) -> list[ET.Element]:
    """dc:identifier que contienen un ISRC."""
    found = []
    for ident in root.iter():
        if _local(ident.tag) != "identifier" or _ns(ident.tag) == DC_NS:
            continue
        is_isrc = (ident.get("formatLabel", "").upper() == "ISRC")
        for dc in ident:
            if _local(dc.tag) == "identifier" and _ns(dc.tag) == DC_NS:
                text = dc.text or ""
                if is_isrc or _ISRC_IN_TEXT.search(text):
                    found.append(dc)
    return found


def read_isrc(raw: bytes | None) -> str:
    """Devuelve el ISRC del axml, o '' si no hay."""
    if not raw:
        return ""
    data = _clean(raw)
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        root = None
    if root is not None:
        for dc in _isrc_identifier_nodes(root):
            text = (dc.text or "").strip()
            m = _ISRC_IN_TEXT.search(text) or _BARE_ISRC.match(text)
            if m:
                return m.group(1).upper()
    m = _ISRC_IN_TEXT.search(data.decode("utf-8", "replace"))
    return m.group(1).upper() if m else ""


def _identifier_block(ebu_prefix: str, dc_prefix: str, declare_dc: bool, isrc: str) -> str:
    decl = ' xmlns:%s="%s"' % (dc_prefix, DC_NS) if declare_dc else ""
    return ('<{e}identifier typeLabel="GUID" typeDefinition="Globally Unique Identifier" '
            'formatLabel="ISRC" formatDefinition="International Standard Recording Code" '
            'formatLink="{link}"><{d}:identifier{decl}>ISRC:{isrc}</{d}:identifier>'
            '</{e}identifier>').format(e=ebu_prefix, d=dc_prefix, decl=decl,
                                       link=ISRC_FORMAT_LINK, isrc=isrc)


def update(raw: bytes | None, isrc: str) -> bytes:
    """Devuelve el axml con el ISRC indicado.

    Si no había axml, crea uno nuevo. Si había EBUCore, edita el texto original
    de forma quirúrgica (cambia o añade solo el nodo del ISRC) y conserva todo lo
    demás tal cual: prefijos (también ns0, ns1...), comentarios y formato. Si el
    axml existente no es EBUCore legible, lanza AxmlNotEditable para no
    destruir datos ajenos.
    """
    if not raw or not _clean(raw):
        return build_new(isrc)
    data = raw.rstrip(b"\x00")   # solo se quita el relleno NUL; el resto se respeta
    try:
        root = ET.fromstring(data)
        text = data.decode("utf-8")
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise AxmlNotEditable(tr("The existing axml is not valid UTF-8 XML (%s).") % exc) from exc
    if _local(root.tag) != "ebuCoreMain":
        raise AxmlNotEditable(tr("The existing axml is not EBUCore (root <%s>).") % _local(root.tag))

    # 1) sustituir el valor de los dc:identifier que ya contienen un ISRC
    replaced = 0
    for old in {(dc.text or "").strip() for dc in _isrc_identifier_nodes(root)}:
        if not old:
            continue
        pattern = re.compile(r">(\s*)" + re.escape(old) + r"(\s*)<")
        text, n = pattern.subn(lambda m: ">%sISRC:%s%s<" % (m.group(1), isrc, m.group(2)), text)
        replaced += n

    # 2) si no había ISRC, insertar el nodo dentro de coreMetadata
    if not replaced:
        m = re.search(r"<([\w.-]+:)?ebuCoreMain\b", text)
        ebu_prefix = (m.group(1) or "") if m else ""
        m = re.search(r'xmlns:([\w.-]+)\s*=\s*["\']' + re.escape(DC_NS) + r'["\']', text)
        dc_prefix, declare_dc = (m.group(1), False) if m else ("dc", True)
        block = _identifier_block(ebu_prefix, dc_prefix, declare_dc, isrc)
        close_core = "</%scoreMetadata>" % ebu_prefix
        empty_core = re.search(r"<%scoreMetadata\s*/>" % re.escape(ebu_prefix), text)
        if close_core in text:
            i = text.rindex(close_core)
            text = text[:i] + block + text[i:]
        elif empty_core:
            text = (text[:empty_core.start()] + "<%scoreMetadata>%s%s" % (ebu_prefix, block, close_core)
                    + text[empty_core.end():])
        else:
            close_root = "</%sebuCoreMain>" % ebu_prefix
            if close_root not in text:
                raise AxmlNotEditable(tr("Could not find where to insert the ISRC in the existing axml."))
            i = text.rindex(close_root)
            text = text[:i] + "<%scoreMetadata>%s%s" % (ebu_prefix, block, close_core) + text[i:]

    out = text.encode("utf-8")
    # comprobación: sigue siendo XML válido y el ISRC se relee correctamente
    try:
        ET.fromstring(out)
    except ET.ParseError as exc:
        raise AxmlNotEditable(tr("Editing the axml would produce invalid XML; it is left unchanged.")) from exc
    if read_isrc(out) != isrc:
        raise AxmlNotEditable(tr("Could not place the ISRC in the existing axml; it is left unchanged."))
    return out


# ---------------------------------------------------------------------------------
# axml completo (título, artista, sello, fecha, identificadores, idioma, derechos)
# ---------------------------------------------------------------------------------
_MANAGED_CHILDREN = {"title", "creator", "publisher", "date", "identifier", "language", "rights"}
# campo -> etiqueta formatLabel del identificador
_IDENTIFIERS = (("isrc", "ISRC"), ("iswc", "ISWC"), ("barcode", None), ("catalog", "CATALOGNUMBER"))


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def has_values(meta) -> bool:
    return any(meta.get(k) for k in ("title", "artist", "label", "date", "isrc", "iswc",
                                     "barcode", "catalog", "language", "copyright"))


def build_full(meta) -> bytes:
    """axml EBUCore 2012 con los campos gestionados, en el orden del esquema."""
    g = meta.get
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<ebucore:ebuCoreMain xmlns:dc="%s" xmlns:ebucore="%s">' % (DC_NS, EBUCORE_NS),
             '  <ebucore:coreMetadata>']
    if g("title"):
        lines.append('    <ebucore:title><dc:title>%s</dc:title></ebucore:title>' % _esc(g("title")))
    if g("artist"):
        lines.append('    <ebucore:creator><ebucore:contactDetails><ebucore:name>%s</ebucore:name>'
                     '</ebucore:contactDetails><ebucore:role typeLabel="Performer"/></ebucore:creator>'
                     % _esc(g("artist")))
    if g("label"):
        lines.append('    <ebucore:publisher><ebucore:organisationDetails><ebucore:organisationName>%s'
                     '</ebucore:organisationName></ebucore:organisationDetails></ebucore:publisher>'
                     % _esc(g("label")))
    if g("date"):
        lines.append('    <ebucore:date><dc:date>%s</dc:date></ebucore:date>' % _esc(g("date")))
    for key, label in _IDENTIFIERS:
        value = g(key)
        if not value:
            continue
        if key == "isrc":
            # exactamente la forma del ejemplo de EBU Tech 3352 (la que leen radios y BMAT)
            lines.append('    <ebucore:identifier typeLabel="GUID" typeDefinition="Globally Unique '
                         'Identifier" formatLabel="ISRC" formatDefinition="International Standard '
                         'Recording Code" formatLink="%s">' % ISRC_FORMAT_LINK)
            lines.append('      <dc:identifier>ISRC:%s</dc:identifier>' % _esc(value))
            lines.append('    </ebucore:identifier>')
            continue
        if label is None:
            label = "UPC" if len(value) == 12 else "EAN"
        lines.append('    <ebucore:identifier formatLabel="%s"><dc:identifier>%s:%s</dc:identifier>'
                     '</ebucore:identifier>' % (label, label, _esc(value)))
    if g("language"):
        lines.append('    <ebucore:language><dc:language>%s</dc:language></ebucore:language>'
                     % _esc(g("language")))
    if g("copyright"):
        lines.append('    <ebucore:rights><dc:rights>%s</dc:rights></ebucore:rights>'
                     % _esc(g("copyright")))
    lines += ['  </ebucore:coreMetadata>', '</ebucore:ebuCoreMain>', '']
    return "\n".join(lines).encode("utf-8")


def is_managed(raw: bytes | None) -> bool:
    """True si el axml solo contiene elementos que la app gestiona (se puede regenerar)."""
    if not raw or not _clean(raw):
        return True
    try:
        root = ET.fromstring(raw.rstrip(b"\x00"))
    except ET.ParseError:
        return False
    if _local(root.tag) != "ebuCoreMain":
        return False
    children = list(root)
    if any(_local(c.tag) != "coreMetadata" for c in children) or len(children) > 1:
        return False
    for core in children:
        for c in core:
            if _local(c.tag) not in _MANAGED_CHILDREN:
                return False
            if _local(c.tag) == "identifier":
                texts = [(d.text or "").strip() for d in c if _local(d.tag) == "identifier"]
                label = (c.get("formatLabel") or "").upper()
                known = label in ("ISRC", "ISWC", "UPC", "EAN", "CATALOGNUMBER") or any(
                    t.upper().startswith(("ISRC:", "ISWC:", "UPC:", "EAN:", "CATALOGNUMBER:"))
                    for t in texts)
                if not known:
                    return False
    return True


def plan(raw: bytes | None, meta) -> tuple[bytes | None, bool, str | None]:
    """Decide qué hacer con el axml.

    Devuelve (bytes_nuevos, eliminar, aviso). bytes_nuevos=None y eliminar=False
    significa «dejar el axml existente como está».
    """
    if is_managed(raw):
        if has_values(meta):
            return build_full(meta), False, None
        return None, bool(raw), None          # todo vacío: se quita el axml propio
    # axml de terceros: solo se toca el ISRC, el resto se respeta
    if not meta.get("isrc"):
        return None, False, None
    try:
        return update(raw, meta.get("isrc")), False, \
            tr("The existing axml holds data from another tool: only the ISRC is updated.")
    except AxmlNotEditable as exc:
        return None, False, str(exc) + tr(" It is kept as is; the ISRC will only go in ID3.")


def read_fields(raw: bytes | None) -> dict[str, str]:
    """Valores legibles del axml (para completar lo que no haya en ID3)."""
    out: dict[str, str] = {}
    if not raw:
        return out
    isrc = read_isrc(raw)
    if isrc:
        out["isrc"] = isrc
    try:
        root = ET.fromstring(raw.rstrip(b"\x00"))
    except ET.ParseError:
        return out
    for el in root.iter():
        name, ns = _local(el.tag), _ns(el.tag)
        text = (el.text or "").strip()
        if not text:
            continue
        if ns == DC_NS and name == "title":
            out.setdefault("title", text)
        elif name == "name":
            out.setdefault("artist", text)
        elif name == "organisationName":
            out.setdefault("label", text)
        elif ns == DC_NS and name == "date":
            out.setdefault("date", text)
        elif ns == DC_NS and name == "language":
            out.setdefault("language", text)
        elif ns == DC_NS and name == "rights":
            out.setdefault("copyright", text)
        elif ns == DC_NS and name == "identifier":
            label, _, value = text.partition(":")
            key = {"ISWC": "iswc", "UPC": "barcode", "EAN": "barcode",
                   "CATALOGNUMBER": "catalog"}.get(label.upper())
            if key and value:
                out.setdefault(key, value.strip())
    return out
