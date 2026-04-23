"""将 field_lines 的物理 presets 展开为 PracticeFieldLine（仅服务层内部）。"""

from __future__ import annotations

import math

from app.models.schemas import (
    PracticeFieldLine,
    PracticeFieldPresetLongStraightWire,
    PracticeFieldPresetPointCharge,
    PracticeFieldPresetSolenoid,
)


def expand_field_line_presets(presets: list) -> list[PracticeFieldLine]:
    out: list[PracticeFieldLine] = []
    for p in presets:
        if isinstance(p, PracticeFieldPresetPointCharge):
            out.extend(_point_charge_lines(p))
        elif isinstance(p, PracticeFieldPresetSolenoid):
            out.extend(_solenoid_lines(p))
        elif isinstance(p, PracticeFieldPresetLongStraightWire):
            out.extend(_long_wire_lines(p))
    return out


def _point_charge_lines(p: PracticeFieldPresetPointCharge) -> list[PracticeFieldLine]:
    col = (p.color or "").strip()
    n = int(p.n_lines)
    r0 = float(p.r_min)
    r1 = float(p.r_max)
    if r1 <= r0 or n < 3:
        return []
    lines: list[PracticeFieldLine] = []
    for k in range(n):
        th = 2.0 * math.pi * k / n
        npts = 16
        xs: list[float] = []
        ys: list[float] = []
        bend = 0.055 if (k % 2 == 0) else -0.055
        for i in range(npts + 1):
            rr = r0 + (r1 - r0) * (i / npts)
            frac = (rr - r0) / max(r1 - r0, 1e-6)
            tt = th + bend * frac
            xs.append(p.cx + rr * math.cos(tt))
            ys.append(p.cy + rr * math.sin(tt))
        if p.sign != 1:
            xs.reverse()
            ys.reverse()
        arrow = "end"
        lines.append(PracticeFieldLine(x=xs, y=ys, color=col, arrow=arrow))
    return lines


def _solenoid_lines(p: PracticeFieldPresetSolenoid) -> list[PracticeFieldLine]:
    col = (p.color or "").strip()
    x0, y0, w, h = float(p.x0), float(p.y0), float(p.w), float(p.h)
    lines: list[PracticeFieldLine] = []
    if p.draw_frame:
        lines.append(
            PracticeFieldLine(
                x=[x0, x0 + w, x0 + w, x0, x0],
                y=[y0, y0, y0 + h, y0 + h, y0],
                color=col or "",
                arrow="none",
            )
        )
    margin = 0.12 * min(w, h) + 0.05
    ixn = max(1, int(p.nx))
    iyn = max(1, int(p.ny))
    span_x = w - 2 * margin
    span_y = h - 2 * margin
    if span_x <= 0 or span_y <= 0:
        return lines
    dx, dy = _dir_vec(p.b_direction)
    ah = 0.22 * min(span_x / ixn, span_y / iyn, 0.45)
    for i in range(ixn):
        for j in range(iyn):
            px = x0 + margin + span_x * (i + 0.5) / ixn
            py = y0 + margin + span_y * (j + 0.5) / iyn
            lines.append(
                PracticeFieldLine(
                    x=[px - dx * ah, px + dx * ah],
                    y=[py - dy * ah, py + dy * ah],
                    color=col,
                    arrow="end",
                )
            )
    return lines


def _dir_vec(d: str) -> tuple[float, float]:
    if d == "up":
        return 0.0, 1.0
    if d == "down":
        return 0.0, -1.0
    if d == "left":
        return -1.0, 0.0
    return 1.0, 0.0


def _long_wire_lines(p: PracticeFieldPresetLongStraightWire) -> list[PracticeFieldLine]:
    col = (p.color or "").strip()
    nc = max(2, int(p.n_circles))
    r1 = float(p.r_max)
    frac = float(p.arc_fraction)
    lines: list[PracticeFieldLine] = []
    sign = 1.0 if p.current_out_of_page else -1.0
    for k in range(1, nc + 1):
        r = r1 * k / (nc + 0.5)
        npts = max(28, int(36 * frac))
        th1 = sign * (-math.pi * 0.15)
        th2 = sign * (2 * math.pi * frac - math.pi * 0.15)
        if th2 < th1:
            th1, th2 = th2, th1
        xs: list[float] = []
        ys: list[float] = []
        for i in range(npts + 1):
            t = th1 + (th2 - th1) * (i / npts)
            xs.append(p.cx + r * math.cos(t))
            ys.append(p.cy + r * math.sin(t))
        lines.append(PracticeFieldLine(x=xs, y=ys, color=col, arrow="end"))
    return lines
