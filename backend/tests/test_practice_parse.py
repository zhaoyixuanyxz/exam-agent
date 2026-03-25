from __future__ import annotations

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
