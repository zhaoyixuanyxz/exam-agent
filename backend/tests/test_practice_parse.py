from __future__ import annotations

from app.models.schemas import PracticeSet
from app.services.practice_parse import (
    normalize_practice_qtype,
    parse_practice_set_from_llm_text,
    repair_practice_dict,
)


def test_repair_string_order_index_and_null_options():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "名",
        "questions": [
            {
                "order_index": "1",
                "qtype": "选",
                "stem": "题干",
                "options": None,
                "answer_outline": "略",
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["order_index"] == 1
    assert r["questions"][0]["options"] == []
    assert r["questions"][0]["qtype"] == "单选"


def test_normalize_practice_qtype_aliases():
    assert normalize_practice_qtype("选择题") == "单选"
    assert normalize_practice_qtype("多选题") == "多选"
    assert normalize_practice_qtype("填空题") == "填空"
    assert normalize_practice_qtype("判断题") == "判断"
    assert normalize_practice_qtype("主观题") == "简答"


def test_repair_figure_kind_unknown_becomes_none():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "题干",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "surface3d",
                "figure_spec": {"series": []},
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["figure_kind"] == "none"
    assert "figure_spec" not in r["questions"][0]


def test_repair_figure_svg_invalid_becomes_none():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "题干",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "svg",
                "figure_spec": {"svg": "not an svg document"},
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["figure_kind"] == "none"
    assert "figure_spec" not in r["questions"][0]


def test_repair_figure_plot_empty_series_becomes_none():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "题干",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "plot",
                "figure_spec": {"series": []},
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["figure_kind"] == "none"
    assert "figure_spec" not in r["questions"][0]


def test_repair_figure_plot_valid_roundtrip():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "根据图像回答。",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "plot",
                "figure_spec": {
                    "title": "示例",
                    "caption": "图1",
                    "series": [{"label": "L1", "x": [0, 1, 2], "y": [0, 1, 4]}],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "plot"
    assert ps.questions[0].figure_spec is not None
    assert len(ps.questions[0].figure_spec.series) == 1
    assert ps.questions[0].figure_spec.series[0].y == [0.0, 1.0, 4.0]


def test_repair_figure_bar_valid_roundtrip():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "根据柱状图回答。",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "bar",
                "figure_spec": {
                    "title": "销量",
                    "categories": ["甲", "乙", "丙"],
                    "values": [10, 20, 15],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "bar"
    assert ps.questions[0].figure_spec is not None
    assert ps.questions[0].figure_spec.categories == ["甲", "乙", "丙"]
    assert ps.questions[0].figure_spec.values == [10.0, 20.0, 15.0]


def test_repair_figure_pie_valid_roundtrip():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "根据扇形图回答。",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "pie",
                "figure_spec": {
                    "labels": ["A", "B", "C"],
                    "values": [30, 50, 20],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "pie"
    assert ps.questions[0].figure_spec is not None
    assert ps.questions[0].figure_spec.labels == ["A", "B", "C"]


def test_repair_figure_plot_single_point_series_becomes_none():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "题干",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "plot",
                "figure_spec": {
                    "series": [{"label": "a", "x": [1], "y": [2]}],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["figure_kind"] == "none"
    assert "figure_spec" not in r["questions"][0]


def test_repair_figure_pie_negative_or_zero_sum_becomes_none():
    for vals in ([0, 0], [-1, 3]):
        d = {
            "knowledge_point_key": "k",
            "knowledge_point_name": "n",
            "questions": [
                {
                    "order_index": 1,
                    "qtype": "填空",
                    "stem": "题干",
                    "options": [],
                    "answer_outline": "略",
                    "figure_kind": "pie",
                    "figure_spec": {"labels": ["a", "b"], "values": vals},
                }
            ],
        }
        r = repair_practice_dict(d)
        assert r["questions"][0]["figure_kind"] == "none"
        assert "figure_spec" not in r["questions"][0]


def test_repair_figure_bar_mismatched_len_becomes_none():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "题干",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "bar",
                "figure_spec": {"categories": ["a"], "values": [1, 2]},
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["figure_kind"] == "none"
    assert "figure_spec" not in r["questions"][0]


def test_repair_figure_grouped_bar_valid_roundtrip():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "分组柱数据见题干。",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "grouped_bar",
                "figure_spec": {
                    "categories": ["Q1", "Q2"],
                    "series": [
                        {"label": "甲", "values": [1.0, 2.0]},
                        {"label": "乙", "values": [3.0, 4.0]},
                    ],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "grouped_bar"
    assert ps.questions[0].figure_spec is not None
    assert len(ps.questions[0].figure_spec.series) == 2


def test_repair_figure_geometry_valid_roundtrip():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "几何题。",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "geometry",
                "figure_spec": {
                    "points": [{"id": "A", "x": 0, "y": 0}],
                    "segments": [{"a": "A", "b": "B"}],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "geometry"


def test_repair_figure_flowchart_valid_roundtrip():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "流程。",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "flowchart",
                "figure_spec": {
                    "nodes": [{"id": "n1", "text": "开始"}],
                    "edges": [],
                },
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "flowchart"


def test_repair_paper_figure_fields():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "题干",
                "options": [],
                "answer_outline": "略",
                "source_question_order": "3",
                "use_paper_figure": "true",
                "paper_image_ref": "uploads/x.png",
            }
        ],
    }
    r = repair_practice_dict(d)
    assert r["questions"][0]["source_question_order"] == 3
    assert r["questions"][0]["use_paper_figure"] is True
    assert r["questions"][0]["paper_image_ref"] == "uploads/x.png"


def test_parse_practice_set_from_loose_json():
    raw = """
```json
{"knowledge_point_key":"a","knowledge_point_name":"测","questions":[
  {"order_index":"2","qtype":"填","stem":"x","options":[],"answer_outline":"y"}
]}
```
"""
    ps = parse_practice_set_from_llm_text(raw)
    assert ps.knowledge_point_key == "a"
    assert ps.questions[0].order_index == 2
    assert ps.questions[0].qtype == "填空"


def test_repair_histogram_kind_not_bar():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "分布",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "histogram",
                "figure_spec": {"edges": [0.0, 1.0, 2.0, 3.0], "counts": [1.0, 2.0, 1.0]},
            }
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "histogram"


def test_parse_practice_set_composite_panels():
    raw = """
{"knowledge_point_key":"k","knowledge_point_name":"n","questions":[
  {"order_index":1,"qtype":"填空","stem":"看图","options":[],"answer_outline":"略",
   "figure_kind":"composite",
   "figure_spec":{"title":"T","ncols":2,"panels":[
     {"kind":"plot","subtitle":"甲","spec":{"series":[{"label":"l","x":[0,1,2],"y":[0,1,0]}]}},
     {"kind":"bar","subtitle":"乙","spec":{"categories":["a","b"],"values":[1,2]}}
   ]}}
]}
"""
    ps = parse_practice_set_from_llm_text(raw)
    assert ps.questions[0].figure_kind == "composite"
    assert len(ps.questions[0].figure_spec.panels) == 2


def test_repair_figure_force_diagram_and_circuit():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "受力",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "force_diagram",
                "figure_spec": {
                    "forces": [{"x0": 0, "y0": 0, "dx": 1, "dy": 0, "label": "F"}],
                },
            },
            {
                "order_index": 2,
                "qtype": "填空",
                "stem": "电路",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "circuit_simple",
                "figure_spec": {
                    "nodes": [
                        {"id": "a", "x": 0, "y": 0},
                        {"id": "b", "x": 1, "y": 0},
                    ],
                    "edges": [{"source": "a", "target": "b", "element": "resistor"}],
                },
            },
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "force_diagram"
    assert ps.questions[1].figure_kind == "circuit_simple"


def test_repair_figure_solid_wireframe_and_field_lines():
    d = {
        "knowledge_point_key": "k",
        "knowledge_point_name": "n",
        "questions": [
            {
                "order_index": 1,
                "qtype": "填空",
                "stem": "线框",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "立体线框",
                "figure_spec": {
                    "projection": "isometric",
                    "vertices": [
                        {"id": "A", "x": 0, "y": 0, "z": 0},
                        {"id": "B", "x": 1, "y": 0, "z": 0},
                    ],
                    "edges": [{"a": "A", "b": "B"}],
                },
            },
            {
                "order_index": 2,
                "qtype": "填空",
                "stem": "场线",
                "options": [],
                "answer_outline": "略",
                "figure_kind": "field_lines",
                "figure_spec": {
                    "lines": [{"x": [0, 1], "y": [0, 0.5]}],
                },
            },
        ],
    }
    r = repair_practice_dict(d)
    ps = PracticeSet.model_validate(r)
    assert ps.questions[0].figure_kind == "solid_wireframe"
    assert ps.questions[1].figure_kind == "field_lines"
