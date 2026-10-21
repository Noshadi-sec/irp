import sys
import time

from irp.providers.compute.local import (
    changed_files,
    execute_process,
    shell_argv,
    snapshot_tree,
)


def run(tmp_path, command, timeout=None):
    return execute_process(
        shell_argv(command),
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        stdout_path=tmp_path / "out.txt",
        stderr_path=tmp_path / "err.txt",
        timeout_s=timeout,
    )


def test_success_failure_and_streams(tmp_path):
    ok = run(tmp_path, "echo hello; echo oops >&2")
    assert (ok.status, ok.exit_code) == ("succeeded", 0)
    assert (tmp_path / "out.txt").read_text() == "hello\n"
    assert (tmp_path / "err.txt").read_text() == "oops\n"
    failed = run(tmp_path, "exit 3")
    assert (failed.status, failed.exit_code) == ("failed", 3)


def test_timeout_stops_the_whole_process_group(tmp_path):
    marker = tmp_path / "child-alive"
    start = time.monotonic()
    result = run(tmp_path, f"(sleep 30; touch {marker}) & sleep 30", timeout=1)
    assert result.status == "timeout"
    assert time.monotonic() - start < 15
    time.sleep(0.5)
    assert not marker.exists()


def test_peak_memory_is_reported(tmp_path):
    command = f'{sys.executable} -c "b = bytearray(64 * 1024 * 1024); print(len(b))"'
    result = run(tmp_path, command)
    assert result.status == "succeeded"
    assert result.max_rss_bytes is not None and result.max_rss_bytes > 60 * 1024 * 1024


def test_changed_files_hashes_new_and_modified(tmp_path):
    (tmp_path / "keep.txt").write_text("same")
    (tmp_path / "edit.txt").write_text("before")
    before = snapshot_tree(tmp_path)
    time.sleep(0.01)
    (tmp_path / "edit.txt").write_text("after!")
    (tmp_path / "new.json").write_text("{}")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("ignored")
    files, truncated = changed_files(tmp_path, before, prefix="code")
    assert [f["path"] for f in files] == ["code/edit.txt", "code/new.json"]
    assert not truncated
