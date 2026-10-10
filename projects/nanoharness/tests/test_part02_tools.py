"""Part 2: tools. read_file, write_file, edit_file, list_dir, grep, all locked to the working dir."""
import os

import pytest

from nanoharness.tools import ToolRegistry, edit_file, file_tools, grep, list_dir, read_file, resolve_path, write_file


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 1\n\n\nprint(main())\n")
    (tmp_path / "README.md").write_text("# demo\nmain entry point\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: main\n")
    return str(tmp_path)


def test_resolve_path_stays_inside_the_working_dir(repo, tmp_path):
    assert resolve_path(repo, "src/app.py") == os.path.join(os.path.realpath(repo), "src", "app.py")
    assert resolve_path(repo, ".") == os.path.realpath(repo)
    for bad in ("../outside.txt", "/etc/passwd", "src/../../x"):
        with pytest.raises(PermissionError):
            resolve_path(repo, bad)
    os.symlink("/", os.path.join(repo, "escape"))
    with pytest.raises(PermissionError):
        resolve_path(repo, "escape/etc/passwd")


def test_read_file_numbers_lines_and_pages(repo):
    out = read_file(repo, "src/app.py")
    assert out.splitlines()[0] == "    1\tdef main():"
    assert "    2\t    return 1" in out
    page = read_file(repo, "src/app.py", offset=2, limit=2)
    assert page.splitlines()[0] == "    2\t    return 1"
    assert "[... 2 more lines; use offset=4 ...]" in page
    with pytest.raises(FileNotFoundError):
        read_file(repo, "missing.py")


def test_write_file_creates_parents(repo):
    msg = write_file(repo, "new/deep/file.txt", "hello")
    assert "5" in msg
    assert open(os.path.join(repo, "new", "deep", "file.txt")).read() == "hello"


def test_edit_file_exact_unique_replace(repo):
    edit_file(repo, "src/app.py", "return 1", "return 2")
    assert "return 2" in open(os.path.join(repo, "src", "app.py")).read()
    with pytest.raises(ValueError, match="not found"):
        edit_file(repo, "src/app.py", "return 99", "x")
    write_file(repo, "dup.txt", "a\na\n")
    with pytest.raises(ValueError, match="2 times"):
        edit_file(repo, "dup.txt", "a", "b")
    assert "2 occurrence" in edit_file(repo, "dup.txt", "a", "b", replace_all=True)
    assert open(os.path.join(repo, "dup.txt")).read() == "b\nb\n"


def test_list_dir_sorts_marks_dirs_and_skips_noise(repo):
    assert list_dir(repo).splitlines() == ["README.md", "src/"]
    os.mkdir(os.path.join(repo, "empty"))
    assert list_dir(repo, "empty") == "(empty directory)"


def test_grep_finds_matches_with_relative_paths(repo):
    out = grep(repo, r"main")
    assert "README.md:2: main entry point" in out
    assert "src/app.py:1: def main():" in out
    assert ".git" not in out
    assert grep(repo, r"main", glob="*.py").count("README") == 0
    assert grep(repo, r"zzz_nothing") == "No matches."


def test_tools_through_the_registry_report_errors(repo):
    reg = ToolRegistry(file_tools(repo))
    assert sorted(t["name"] for t in reg.schemas()) == ["edit_file", "grep", "list_dir", "read_file", "write_file"]
    out, err = reg.call("read_file", {"path": "../../etc/passwd"})
    assert err and "PermissionError" in out
    out, err = reg.call("edit_file", {"path": "src/app.py", "old_string": "nope", "new_string": "x"})
    assert err and "Read the file" in out
    out, err = reg.call("list_dir", {})
    assert not err and "src/" in out
