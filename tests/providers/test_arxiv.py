import pytest

from irp.domain.errors import IRPError
from irp.providers.intake.arxiv import ArxivRef, fetch_metadata, parse_arxiv_ref
from tests.support.arxiv import FakeArxiv


@pytest.mark.parametrize(
    ("text", "ref"),
    [
        ("2501.12345", ArxivRef("2501.12345", None)),
        ("2501.12345v2", ArxivRef("2501.12345", "v2")),
        ("arXiv:2501.12345v3", ArxivRef("2501.12345", "v3")),
        ("https://arxiv.org/abs/2501.12345v2", ArxivRef("2501.12345", "v2")),
        ("https://arxiv.org/pdf/2501.12345v2.pdf", ArxivRef("2501.12345", "v2")),
        ("https://export.arxiv.org/abs/2501.12345", ArxivRef("2501.12345", None)),
        ("hep-th/9901001v1", ArxivRef("hep-th/9901001", "v1")),
        ("math.GT/0309136", ArxivRef("math.GT/0309136", None)),
    ],
)
def test_parse_arxiv_ref(text, ref):
    assert parse_arxiv_ref(text) == ref


@pytest.mark.parametrize(
    "text", ["https://example.com/abs/2501.12345", "paper.pdf", "1234", "/tmp/2501.12345"]
)
def test_non_arxiv_inputs(text):
    assert parse_arxiv_ref(text) is None


def test_metadata_pins_the_latest_version():
    metadata = fetch_metadata(ArxivRef("2501.00001", None), FakeArxiv(version="v3"))
    assert metadata.version == "v3"
    assert metadata.title == "Least Squares Recovers a Linear Trend in Ten Thousand Samples"
    assert metadata.authors == ["Ada Example", "Alan Example"]
    assert metadata.primary_category == "stat.ML"


def test_metadata_for_a_missing_paper_is_a_typed_error():
    class Empty:
        def get(self, url):
            from irp.providers.intake.arxiv import Download

            return Download(
                url, b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>', "application/atom+xml"
            )

    with pytest.raises(IRPError) as error:
        fetch_metadata(ArxivRef("2501.99999", None), Empty())
    assert error.value.code.value == "paper_unavailable"
