from app.services.anthology_ranges import (
    ANTHOLOGY_PARENT_DONE_TOOLS,
    EMPTY_SUGGEST_MESSAGE,
    CONFIRM_BLOCKED_NEEDED,
    CONFIRM_BLOCKED_DONE,
    suggest_ranges_from_page_texts,
    confirm_blocked_message,
    refuse_if_anthology_parent_done,
)


def test_suggest_splits_on_year_markers():
    pages = [
        "2021年广州市中考数学",
        "第1题 …",
        "2022年广州市中考数学",
        "第1题 …",
        "2023年广州市中考数学",
        "尾页",
    ]
    ranges, labels, msg = suggest_ranges_from_page_texts(pages)
    assert ranges == [[1, 2], [3, 4], [5, 6]]
    assert labels[0].startswith("2021")
    assert labels[1].startswith("2022")
    assert labels[2].startswith("2023")
    assert msg == ""


def test_suggest_empty_when_fewer_than_two_markers():
    ranges, labels, msg = suggest_ranges_from_page_texts(["普通单套卷 第1题", "第2题"])
    assert ranges == []
    assert labels == []
    assert msg == EMPTY_SUGGEST_MESSAGE


def test_suggest_never_equal_splits_total_pages():
    # 10 页无年份：必须空，禁止 [[1,2],[3,4],…] 均分
    pages = [f"内容{i}" for i in range(10)]
    ranges, labels, msg = suggest_ranges_from_page_texts(pages)
    assert ranges == []
    assert labels == []
    assert msg == EMPTY_SUGGEST_MESSAGE


def test_confirm_blocked_message():
    assert confirm_blocked_message("needed") == CONFIRM_BLOCKED_NEEDED
    assert confirm_blocked_message("done") == CONFIRM_BLOCKED_DONE
    assert confirm_blocked_message("none") is None
    assert confirm_blocked_message("single_ok") is None


def test_refuse_if_anthology_parent_done():
    assert refuse_if_anthology_parent_done("done") == ANTHOLOGY_PARENT_DONE_TOOLS
    assert refuse_if_anthology_parent_done("needed") is None
    assert refuse_if_anthology_parent_done("none") is None
    assert refuse_if_anthology_parent_done("single_ok") is None
    assert refuse_if_anthology_parent_done(None) is None
    assert "子材料" in ANTHOLOGY_PARENT_DONE_TOOLS
