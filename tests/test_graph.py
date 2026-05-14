from pathlib import Path

from agentcli.analysis.graph import build_graph_index, build_skeleton_graph
from agentcli.analysis.graph import expand_call_node, get_node_detail


def test_build_skeleton_graph_returns_unique_nodes_and_edges(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        """
def helper():
    return "a"


def main():
    return helper()
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "b.py").write_text(
        """
def helper():
    return "b"
""".strip(),
        encoding="utf-8",
    )

    result = build_skeleton_graph(tmp_path)

    ids = {node["id"] for node in result["nodes"]}
    assert "pkg/a.py::main" in ids
    assert "pkg/a.py::helper" in ids
    assert "pkg/b.py::helper" in ids
    assert any(
        edge["source"] == "pkg/a.py::main" and edge["target"] == "pkg/a.py::helper"
        for edge in result["edges"]
    )


def test_build_skeleton_graph_empty_repo(tmp_path: Path) -> None:
    result = build_skeleton_graph(tmp_path)

    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["warning"] == "no_python_files"


def test_build_graph_index_reports_skipped_syntax_error_files(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def func(:\n    pass\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("def ok():\n    pass\n", encoding="utf-8")

    index = build_graph_index(tmp_path)

    assert "broken.py" in index["skipped_files"]
    assert "ok.py::ok" in index["nodes_by_id"]


def test_build_skeleton_graph_methods_use_class_qualified_labels(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        """
class Worker:
    def run(self):
        self.save()

    def save(self):
        pass
""".strip(),
        encoding="utf-8",
    )

    result = build_skeleton_graph(tmp_path)

    labels = {node["label"] for node in result["nodes"]}
    assert "Worker.run" in labels
    assert "Worker.save" in labels
    assert any(
        edge["source"] == "app.py::Worker.run" and edge["target"] == "app.py::Worker.save"
        for edge in result["edges"]
    )


def test_build_skeleton_graph_nested_methods_use_full_qualname(tmp_path: Path) -> None:
    (tmp_path / "nested.py").write_text(
        """
class A:
    class Inner:
        def run(self):
            pass


class B:
    class Inner:
        def run(self):
            pass
""".strip(),
        encoding="utf-8",
    )

    result = build_skeleton_graph(tmp_path)

    ids = {node["id"] for node in result["nodes"]}
    assert "nested.py::A.Inner.run" in ids
    assert "nested.py::B.Inner.run" in ids


def test_expand_call_node_returns_bfs_subgraph(tmp_path: Path) -> None:
    (tmp_path / "chain.py").write_text(
        """
def a():
    return b()


def b():
    return c()


def c():
    return "done"
""".strip(),
        encoding="utf-8",
    )

    result = expand_call_node(tmp_path, "chain.py::a", depth=2)

    ids = {node["id"] for node in result["nodes"]}
    assert result["root"] == "chain.py::a"
    assert "chain.py::a" in ids
    assert "chain.py::b" in ids
    assert "chain.py::c" in ids
    assert any(edge["source"] == "chain.py::b" and edge["target"] == "chain.py::c" for edge in result["edges"])


def test_expand_call_node_respects_depth(tmp_path: Path) -> None:
    (tmp_path / "chain.py").write_text(
        """
def a():
    return b()


def b():
    return c()


def c():
    return "done"
""".strip(),
        encoding="utf-8",
    )

    result = expand_call_node(tmp_path, "chain.py::a", depth=1)

    ids = {node["id"] for node in result["nodes"]}
    assert "chain.py::b" in ids
    assert "chain.py::c" not in ids


def test_expand_call_node_unknown_or_external_node(tmp_path: Path) -> None:
    result = expand_call_node(tmp_path, "missing.py::ghost", depth=3)

    assert result == {"root": "missing.py::ghost", "nodes": [], "edges": []}


def test_get_node_detail_returns_incoming_and_outgoing_edges(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        """
def setup():
    pass


def main():
    setup()
""".strip(),
        encoding="utf-8",
    )

    result = get_node_detail(tmp_path, "app.py::setup")

    assert result["node"]["id"] == "app.py::setup"
    assert [edge["source"] for edge in result["incoming"]] == ["app.py::main"]
    assert result["outgoing"] == []
