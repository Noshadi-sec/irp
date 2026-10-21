"""Live arXiv intake. Runs only with IRP_TEST_NETWORK=1."""

import os

import pytest

from irp.application.context import OperationContext
from irp.application.operations import execute
from irp.providers.intake.arxiv import HttpFetcher

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(os.environ.get("IRP_TEST_NETWORK") != "1", reason="set IRP_TEST_NETWORK=1"),
]


def test_real_arxiv_latex_source_and_pdf(study_dir):
    context = OperationContext(actor="cli", fetcher=HttpFetcher())
    result = execute("fetch_paper", {"study": str(study_dir), "paper": "1706.03762"}, context)
    assert result["paper"]["arxiv_id"] == "1706.03762"
    assert result["paper"]["version"].startswith("v")
    assert result["paper"]["source_format"] == "latex"
    assert result["paper"]["title"].startswith("Attention Is All You Need")
    paths = {f["path"] for f in result["files"]}
    assert "paper/paper.pdf" in paths and "paper/source" in paths
    tables = [i for i in result["outline"]["items"] if i["id"].startswith("tab:")]
    assert tables, "the outline should list the paper's tables"
    image = execute("get_page_image", {"study": str(study_dir), "page": 1, "dpi": 60}, context)
    assert image["width"] > 0
