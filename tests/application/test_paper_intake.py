import json

import pytest

from irp.domain.errors import IRPError
from tests.conftest import call
from tests.support.arxiv import TOY_ID, FakeArxiv
from tests.support.pdf import make_pdf


def test_arxiv_latex_first_with_pdf_for_page_images(study_dir):
    fake = FakeArxiv(version="v2")
    result = call("fetch_paper", {"study": str(study_dir), "paper": TOY_ID}, fetcher=fake)
    assert result["paper"]["arxiv_id"] == TOY_ID
    assert result["paper"]["version"] == "v2"
    assert result["paper"]["source_format"] == "latex"
    paths = {f["path"] for f in result["files"]}
    assert {"paper/source-download.tar.gz", "paper/paper.pdf", "paper/source"} <= paths
    assert [u.split("/")[2] for u in fake.requests] == [
        "export.arxiv.org",
        "arxiv.org",
        "arxiv.org",
    ]
    assert any("/e-print/2501.00001v2" in u for u in fake.requests), "unversioned IDs are pinned"


def test_pdf_only_arxiv_paper(study_dir):
    result = call(
        "fetch_paper",
        {"study": str(study_dir), "paper": TOY_ID},
        fetcher=FakeArxiv(with_source=False),
    )
    assert result["paper"]["source_format"] == "pdf"
    section = call("get_section", {"study": str(study_dir), "id": "sec:3"})
    assert "Table 1" in section["text"]


def test_local_pdf(tmp_path, study_dir):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(make_pdf([["My Paper", "1 Introduction", "Hello."]]))
    result = call("fetch_paper", {"study": str(study_dir), "paper": str(pdf)})
    assert result["paper"]["source_format"] == "pdf"
    image = call("get_page_image", {"study": str(study_dir), "page": 1, "dpi": 60})
    assert image["path"].endswith(".png") and image["sha256"].startswith("sha256:")


def test_sections_by_id_label_title_range_and_paging(fetched):
    by_label = call("get_section", {"study": str(fetched), "id": "eq:closed"})
    assert by_label["start"] == {"file": "sections/method.tex", "line": 14}
    assert "\\hat{w}" in by_label["text"]
    by_title = call("get_section", {"study": str(fetched), "id": "Experiments"})
    assert by_title["kind"] == "section"
    paged = call("get_section", {"study": str(fetched), "id": "sec:3", "max_lines": 5})
    assert paged["returned"] == 5 and paged["next_offset"] == 5
    lines = call("get_section", {"study": str(fetched), "id": "lines:1-3"})
    assert lines["lines_total"] == 3
    index = call("get_section", {"study": str(fetched), "id": "index"})["index"]
    assert any(item["labels"] == ["tab:main"] for item in index["items"])


def test_unknown_section_is_a_typed_error(fetched):
    with pytest.raises(IRPError) as error:
        call("get_section", {"study": str(fetched), "id": "sec:99"})
    assert error.value.code.value == "not_found"


def test_one_paper_per_study_and_no_takeover_of_other_directories(fetched, tmp_path):
    with pytest.raises(IRPError):
        call("fetch_paper", {"study": str(fetched), "paper": TOY_ID})
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "notes.txt").write_text("mine")
    with pytest.raises(IRPError):
        call("fetch_paper", {"study": str(occupied), "paper": TOY_ID})


def test_failed_download_leaves_a_retryable_study(study_dir):
    class Broken(FakeArxiv):
        def get(self, url):
            if "/pdf/" in url:
                raise IRPError(
                    __import__(
                        "irp.domain.errors", fromlist=["ErrorCode"]
                    ).ErrorCode.PAPER_UNAVAILABLE,
                    "down",
                )
            return super().get(url)

    with pytest.raises(IRPError):
        call("fetch_paper", {"study": str(study_dir), "paper": TOY_ID}, fetcher=Broken())
    assert list((study_dir / "paper").iterdir()) == []
    assert (
        call("fetch_paper", {"study": str(study_dir), "paper": TOY_ID})["paper"]["version"] == "v2"
    )


def test_study_paths_must_be_absolute():
    with pytest.raises(IRPError) as error:
        call("study_status", {"study": "relative/path"})
    assert error.value.code.value == "invalid_request"


def test_evidence_records_the_fetch(fetched):
    records = [json.loads(line) for line in (fetched / "evidence.jsonl").read_text().splitlines()]
    assert [r["type"] for r in records] == ["study.created", "paper.fetched"]
    assert records[1]["prev"] == records[0]["hash"]
