from irp.providers.intake import images, pdf
from tests.support.pdf import make_pdf


def test_pdf_text_sections_and_captions(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(
        make_pdf(
            [
                ["A Paper", "Abstract", "We study things.", "1 Introduction", "Text."],
                ["2 Method", "x = y + z        (1)", "Table 2: Main results.", "Ours 94.1"],
            ]
        )
    )
    lines, pages, outline = pdf.read_pdf_lines(path)
    assert pages == 2 and outline == []
    assert lines[0].file == "paper.pdf#page=1"
    index = pdf.index_pdf_lines(lines, pages, outline)
    titles = [s["title"] for s in index["sections"]]
    assert titles == ["Abstract", "Introduction", "Method"]
    ids = {item["id"] for item in index["items"]}
    assert {"tab:2", "eq:1"} <= ids


def test_page_rendering(tmp_path):
    path = tmp_path / "paper.pdf"
    path.write_bytes(make_pdf([["page one"], ["page two"]]))
    assert images.page_count(path) == 2
    width, height = images.render_page(path, 2, 72, tmp_path / "p2.png")
    assert (width, height) == (612, 792)
    assert (tmp_path / "p2.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
