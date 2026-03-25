from __future__ import annotations

from app.services.json_from_llm import iter_decode_root_dicts, iter_candidate_dicts_from_llm
from app.services.practice_json_recovery import pick_best_practice_set_dict


def test_iter_decode_multiple_roots():
    s = '{"a":1}{"b":2}'
    ds = iter_decode_root_dicts(s)
    assert len(ds) == 2
    assert ds[0] == {"a": 1}
    assert ds[1] == {"b": 2}


def test_iter_candidate_prefers_fenced():
    text = 'noise\n```json\n{"x":1}\n```\n{"y":2}'
    keys = [list(d.keys())[0] for d in iter_candidate_dicts_from_llm(text)]
    assert "x" in keys
    assert "y" in keys


def test_pick_best_skips_corrupt_stem():
    bad = (
        '{"knowledge_point_key":"b","knowledge_point_name":"坏",'
        '"questions":[{"order_index":1,"qtype":"判","stem":"出题失败：x","options":[],"answer_outline":"a"}]}'
    )
    good = (
        '{"knowledge_point_key":"g","knowledge_point_name":"好",'
        '"questions":['
        '{"order_index":1,"qtype":"选","stem":"短题干","options":["A"],"answer_outline":"略"}]}'
    )
    picked = pick_best_practice_set_dict(bad + "\n\n" + good)
    assert picked is not None
    assert picked["knowledge_point_key"] == "g"


def test_pick_best_prefers_more_questions_when_clean():
    small = (
        '{"knowledge_point_key":"s","knowledge_point_name":"少",'
        '"questions":['
        '{"order_index":1,"qtype":"选","stem":"a","options":[],"answer_outline":"b"}]}'
    )
    big = (
        '{"knowledge_point_key":"s","knowledge_point_name":"多",'
        '"questions":['
        '{"order_index":1,"qtype":"选","stem":"a","options":[],"answer_outline":"b"},'
        '{"order_index":2,"qtype":"填","stem":"c","options":[],"answer_outline":"d"},'
        '{"order_index":3,"qtype":"判","stem":"e","options":[],"answer_outline":"f"}]}'
    )
    picked = pick_best_practice_set_dict(small + "\n" + big)
    assert picked is not None
    assert len(picked["questions"]) >= 2
