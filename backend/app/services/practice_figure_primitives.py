"""配图渲染共用：3D→2D 投影、箭头几何（仅服务层内部使用）。"""

from __future__ import annotations

import math


def project_vertex_isometric(x: float, y: float, z: float) -> tuple[float, float]:
    """正等轴测：x 右、y 深、z 高。"""
    x2 = (x - y) * math.sqrt(3) / 2.0
    y2 = (x + y) / 2.0 - z
    return x2, y2


def project_vertex_cabinet(x: float, y: float, z: float) -> tuple[float, float]:
    """斜二测风格：y 为深度轴，向前下方偏。"""
    shear = 0.5
    x2 = x + shear * y
    y2 = z + shear * y
    return x2, y2


def project_vertex_oblique_pep(x: float, y: float, z: float) -> tuple[float, float]:
    """人教版立体几何常用斜二测：x、z 方向 1:1，深度 y 与 x 轴成 45° 且长度取半。"""
    c = math.sqrt(2) / 2.0
    x2 = x + 0.5 * y * c
    y2 = z + 0.5 * y * c
    return x2, y2


def polygon_centroid_2d(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return xs[0], ys[0]
    a = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        j = (i + 1) % n
        cross = xs[i] * ys[j] - xs[j] * ys[i]
        a += cross
        cx += (xs[i] + xs[j]) * cross
        cy += (ys[i] + ys[j]) * cross
    if abs(a) < 1e-12:
        return sum(xs) / n, sum(ys) / n
    a *= 0.5
    return cx / (6.0 * a), cy / (6.0 * a)


def segment_arrow_tangent(
    xs: list[float],
    ys: list[float],
    *,
    at_end: bool,
) -> tuple[float, float, float, float]:
    """返回 (x_tip, y_tip, ux, uy) 单位切向（指向末端或起端）。"""
    if len(xs) < 2:
        return xs[0], ys[0], 1.0, 0.0
    if at_end:
        x0, y0 = xs[-2], ys[-2]
        x1, y1 = xs[-1], ys[-1]
    else:
        x0, y0 = xs[0], ys[0]
        x1, y1 = xs[1], ys[1]
    dx = x1 - x0
    dy = y1 - y0
    ln = math.hypot(dx, dy)
    if ln < 1e-12:
        return x1, y1, 1.0, 0.0
    if at_end:
        return x1, y1, dx / ln, dy / ln
    return x0, y0, -dx / ln, -dy / ln
