from app.services.practice_fill import needs_figure


def test_needs_figure_matches_diagram_topics_not_the_bare_word_function():
    assert needs_figure("几何", ["求阴影部分面积"]) is True
    assert needs_figure("二次函数", ["画出函数图像"]) is True
    assert needs_figure("欧姆定律", ["画出电路"]) is True
    assert needs_figure("实验室制氧", ["画出化学装置"]) is True
    assert needs_figure("一次函数", ["求解析式"]) is False
    assert needs_figure("牛顿第一定律", ["用文字说明惯性"]) is False
