"""练习卷内联 SVG：大小限制、危险构造拒绝、标签白名单（供 clamp / PDF / composite 栅格化）。"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# 与 practice_clamp 中 _MAX_SVG_BYTES 对齐（由 clamp 传入）
_DEFAULT_MAX_SVG_BYTES = 100_000

# 常见绘图子集；未列出的标签整节点移除
_ALLOWED_LOCAL_TAGS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "clippath",
        "mask",
        "lineargradient",
        "radialgradient",
        "stop",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "title",
        "desc",
        "use",
        "metadata",
    }
)

_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>", re.IGNORECASE | re.DOTALL)


def _local_name(tag: str) -> str:
    if not tag:
        return ""
    if tag[0] == "{":
        return tag.split("}", 1)[-1].lower()
    return tag.lower()


def _is_forbidden_snippet(s: str) -> bool:
    low = s.lower()
    if "<!doctype" in low or "<!entity" in low:
        return True
    if "<script" in low or "</script>" in low:
        return True
    if "javascript:" in low.replace(" ", ""):
        return True
    if "<iframe" in low:
        return True
    if "foreignobject" in low.replace(" ", "").replace("\n", ""):
        return True
    if "data:text/html" in low:
        return True
    return False


def _attr_safe(name: str, value: str) -> bool:
    nl = name.lower().strip()
    if nl.startswith("on") and len(nl) > 2:
        return False
    if nl in ("href", "xlink:href", "xlink:arcrole"):
        v = (value or "").strip().lower()
        if v.startswith("http:") or v.startswith("https:") or v.startswith("//"):
            return False
        if v.startswith("javascript:") or v.startswith("data:"):
            return False
    return True


def _prune_element(el: ET.Element) -> None:
    """就地删除不允许的子节点与危险属性。"""
    local = _local_name(el.tag)
    if local == "use":
        href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href")
        if href and not str(href).strip().startswith("#"):
            el.clear()

    keep: dict[str, str] = {}
    for k, v in list(el.attrib.items()):
        if not isinstance(v, str):
            v = str(v)
        if len(v) > 4000:
            v = v[:4000]
        if _attr_safe(k, v):
            keep[k] = v
    el.attrib.clear()
    el.attrib.update(keep)

    for child in list(el):
        cl = _local_name(child.tag)
        if cl not in _ALLOWED_LOCAL_TAGS:
            el.remove(child)
        else:
            _prune_element(child)


def sanitize_practice_svg(raw: str, *, max_bytes: int = _DEFAULT_MAX_SVG_BYTES) -> str | None:
    """返回 UTF-8 安全的 SVG 字符串；不合法则 None。"""
    s = (raw or "").strip()
    if not s:
        return None
    try:
        b = s.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(b) > max_bytes:
        return None
    if _is_forbidden_snippet(s):
        return None
    s2 = _DOCTYPE_RE.sub("", s)
    if _is_forbidden_snippet(s2):
        return None
    try:
        root = ET.fromstring(s2)
    except ET.ParseError as e:
        logger.debug("sanitize_practice_svg: parse error %s", e)
        return None
    if _local_name(root.tag) != "svg":
        return None
    try:
        _prune_element(root)
        out = ET.tostring(root, encoding="unicode", default_namespace=None)
    except Exception as e:
        logger.debug("sanitize_practice_svg: prune/tostring failed %s", e)
        return None
    if not out or "<svg" not in out.lower():
        return None
    try:
        bout = out.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(bout) > max_bytes:
        return None
    return out


def rasterize_svg_to_png(svg_utf8: str, *, dpi: float = 168.0) -> bytes | None:
    """composite 子图用：可选依赖 cairosvg + 系统 cairo。未安装/无 DLL/渲染失败则 None。"""
    try:
        import cairosvg  # type: ignore[import-not-found]
    except (ImportError, OSError):
        return None
    try:
        return cairosvg.svg2png(bytestring=svg_utf8.encode("utf-8"), dpi=dpi)
    except Exception as e:
        logger.debug("rasterize_svg_to_png: cairosvg failed %s", e)
        return None
