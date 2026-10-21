from irp.providers.intake.latex import find_main_file, flatten, index_document, strip_comment
from tests.support.arxiv import TOY_PAPER


def toy_index():
    document = flatten(TOY_PAPER, find_main_file(TOY_PAPER))
    return document, index_document(document)


def test_main_file_and_inputs_are_flattened_with_origins():
    document, _ = toy_index()
    assert document.main_file == "main.tex"
    files = {line.file for line in document.lines}
    assert files == {"main.tex", "sections/method.tex"}
    method = next(line for line in document.lines if "\\section{Method}" in line.text)
    assert (method.file, method.line) == ("sections/method.tex", 1)


def test_sections_are_numbered_and_appendix_is_lettered():
    _, index = toy_index()
    assert [(s["id"], s["title"]) for s in index["sections"]] == [
        ("sec:1", "Introduction"),
        ("sec:2", "Method"),
        ("sec:3", "Experiments"),
        ("sec:A", "Implementation details"),
    ]
    assert index["sections"][1]["labels"] == ["sec:method"]


def test_items_keep_labels_captions_and_numbers():
    _, index = toy_index()
    by_id = {item["id"]: item for item in index["items"]}
    assert by_id["eq:3"]["labels"] == ["eq:closed"]
    assert by_id["tab:1"]["caption"].startswith("Least squares on synthetic data")
    assert by_id["tab:1"]["labels"] == ["tab:main"]
    assert by_id["alg:1"]["section"] == "sec:2"
    assert sum(1 for item in index["items"] if item["kind"] == "equation") == 3


def test_comments_do_not_create_structure(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n% \\section{Hidden}\n\\section{Shown} % \\input{nothing}\n\\end{document}\n"
    )
    document = flatten(tmp_path, tmp_path / "main.tex")
    index = index_document(document)
    assert [s["title"] for s in index["sections"]] == ["Shown"]
    assert index["missing_inputs"] == []


def test_missing_inputs_and_include_cycles(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\input{a}\n\\input{gone}\n\\end{document}\n"
    )
    (tmp_path / "a.tex").write_text("\\section{A}\n\\input{main}\n")
    document = flatten(tmp_path, tmp_path / "main.tex")
    assert document.missing_inputs == ["gone"]
    assert sum(1 for line in document.lines if line.file == "main.tex") == 5


def test_inputs_cannot_escape_the_source_root(tmp_path):
    outside = tmp_path / "secret.tex"
    outside.write_text("secret")
    root = tmp_path / "src"
    root.mkdir()
    (root / "main.tex").write_text("\\documentclass{article}\n\\input{../secret}\n")
    document = flatten(root, root / "main.tex")
    assert all(line.text != "secret" for line in document.lines)


def test_numbered_align_rows_and_starred_environments(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\begin{align}\na &= b \\\\\nc &= d \\nonumber \\\\\ne &= f\n\\end{align}\n"
        "\\begin{equation*}\nx\n\\end{equation*}\n"
        "\\begin{equation}\ny\n\\end{equation}\n\\end{document}\n"
    )
    index = index_document(flatten(tmp_path, tmp_path / "main.tex"))
    numbered = [item["numbers"] for item in index["items"] if item["kind"] == "equation"]
    assert numbered == [["1", "2"], [], ["3"]]


def test_strip_comment_keeps_escaped_percent():
    assert strip_comment("94.1\\% accuracy % note") == "94.1\\% accuracy "


def test_two_column_floats_are_numbered(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\begin{figure}\\caption{One}\\end{figure}\n"
        "\\begin{figure*}\\caption{Two}\\end{figure*}\n"
        "\\begin{table*}\\caption{Wide}\\end{table*}\n\\end{document}\n"
    )
    index = index_document(flatten(tmp_path, tmp_path / "main.tex"))
    assert [item["id"] for item in index["items"]] == ["fig:1", "fig:2", "tab:1"]
