from __future__ import annotations

from app.models.schemas import ContentBlock, QuestionItem, PaperSection, StructuredPaper
from app.services.practice_paper_figures import collect_order_index_to_image_paths


def test_collect_order_index_to_image_paths():
    sp = StructuredPaper(
        title="t",
        sections=[
            PaperSection(
                title="s",
                questions=[
                    QuestionItem(
                        order_index=2,
                        qtype="选",
                        stem="x",
                        options=[],
                        blocks=[
                            ContentBlock(type="image_ref", ref="uploads/a.png"),
                            ContentBlock(type="image_ref", ref="uploads/b.png"),
                        ],
                    )
                ],
            )
        ],
    )
    m = collect_order_index_to_image_paths(sp)
    assert m[2] == ["uploads/a.png", "uploads/b.png"]
