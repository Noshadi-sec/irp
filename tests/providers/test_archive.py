import gzip
import io
import tarfile
import zipfile

import pytest

from irp.domain.errors import IRPError
from irp.providers.intake.archive import detect_kind, unpack_source


def tar_gz(members: dict[str, bytes], *, symlink: tuple[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        if symlink:
            info = tarfile.TarInfo(symlink[0])
            info.type = tarfile.SYMTYPE
            info.linkname = symlink[1]
            archive.addfile(info)
    return gzip.compress(buffer.getvalue())


def test_multi_file_source(tmp_path):
    unpacked = unpack_source(
        tar_gz({"main.tex": b"\\documentclass{article}", "sec/a.tex": b"x"}), tmp_path / "src"
    )
    assert unpacked.kind == "tar"
    assert unpacked.files == ["main.tex", "sec/a.tex"]


def test_single_gzipped_tex(tmp_path):
    unpacked = unpack_source(
        gzip.compress(b"\\documentclass{article}\n\\begin{document}x\\end{document}"),
        tmp_path / "s",
    )
    assert unpacked.kind == "gzip-single"
    assert (tmp_path / "s" / "main.tex").is_file()


def test_pdf_only_download_writes_nothing(tmp_path):
    assert unpack_source(b"%PDF-1.4 ...", tmp_path / "s").kind == "pdf"
    assert detect_kind(b"%PDF-1.7") == "pdf"


def test_zip_source(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("paper/main.tex", "\\documentclass{article}")
    assert unpack_source(buffer.getvalue(), tmp_path / "s").files == ["paper/main.tex"]


@pytest.mark.parametrize("name", ["../escape.tex", "/abs/main.tex", "a/../../b.tex"])
def test_path_traversal_is_refused(tmp_path, name):
    with pytest.raises(IRPError):
        unpack_source(tar_gz({name: b"x"}), tmp_path / "s")
    assert not (tmp_path / "escape.tex").exists()


def test_links_are_skipped(tmp_path):
    unpacked = unpack_source(
        tar_gz({"main.tex": b"x"}, symlink=("evil", "/etc/passwd")), tmp_path / "s"
    )
    assert unpacked.files == ["main.tex"]
    assert not (tmp_path / "s" / "evil").exists()


def test_destination_must_be_empty(tmp_path):
    (tmp_path / "s").mkdir()
    (tmp_path / "s" / "old").write_text("x")
    with pytest.raises(ValueError):
        unpack_source(tar_gz({"main.tex": b"x"}), tmp_path / "s")
