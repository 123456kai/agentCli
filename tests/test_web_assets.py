from pathlib import Path


def test_web_mvp_contains_named_components() -> None:
    web_root = Path("web/src")

    expected = [
        "main.tsx",
        "App.tsx",
        "components/layout/WorkbenchShell.tsx",
        "components/chat/ChatPanel.tsx",
        "components/code/CodeEditor.tsx",
        "components/code/FileTabs.tsx",
        "components/files/FileExplorer.tsx",
        "components/timeline/AgentTimeline.tsx",
        "components/evidence/EvidencePanel.tsx",
        "components/answer/AnswerPanel.tsx",
        "components/status/StatusBar.tsx",
        "components/CallGraph.tsx",
        "api/client.ts",
        "api/events.ts",
        "styles.css",
    ]

    for relative in expected:
        assert (web_root / relative).exists(), relative


def test_web_entry_is_vite_typescript_entry() -> None:
    index = Path("web/index.html").read_text(encoding="utf-8")

    assert 'type="module"' in index
    assert 'src="/src/main.tsx"' in index
    assert "unpkg.com" not in index
    assert "text/babel" not in index


def test_web_client_uses_eventsource_for_live_sse() -> None:
    client = Path("web/src/api/client.ts").read_text(encoding="utf-8")

    assert "new EventSource" in client
    assert "run_finished" in client


def test_web_app_uses_codex_style_workbench_components() -> None:
    app = Path("web/src/App.tsx").read_text(encoding="utf-8")
    shell = Path("web/src/components/layout/WorkbenchShell.tsx").read_text(encoding="utf-8")
    styles = Path("web/src/styles.css").read_text(encoding="utf-8")

    assert "WorkbenchShell" in app
    assert "CodeEditor" in app
    assert "EvidencePanel" in app
    assert "openEvidence" in app
    assert "topbar" in shell
    assert "statusbar" in shell
    assert "grid-template-areas" in styles


def test_web_app_integrates_monaco_live_events_evidence_and_file_explorer() -> None:
    app = Path("web/src/App.tsx").read_text(encoding="utf-8")
    code_editor = Path("web/src/components/code/CodeEditor.tsx").read_text(encoding="utf-8")
    evidence_panel = Path("web/src/components/evidence/EvidencePanel.tsx").read_text(encoding="utf-8")
    file_explorer = Path("web/src/components/files/FileExplorer.tsx").read_text(encoding="utf-8")
    client = Path("web/src/api/client.ts").read_text(encoding="utf-8")

    assert '@monaco-editor/react' in code_editor
    assert "highlightedRange" in code_editor
    assert "deltaDecorations" in code_editor
    assert "agentLineHighlight" in code_editor
    assert "subscribeRunEvents" in app
    assert "startRun" in client
    assert "new EventSource" in client
    assert "onOpenEvidence" in evidence_panel
    assert "onQueryChange" in file_explorer


def test_web_app_handles_failure_status_initial_file_listing_and_evidence_ranges() -> None:
    app = Path("web/src/App.tsx").read_text(encoding="utf-8")
    client = Path("web/src/api/client.ts").read_text(encoding="utf-8")

    assert "useEffect" in app
    assert "refreshFiles(\"\")" in app
    assert "current === \"failed\"" in app
    assert "lineOffset" in client
    assert "line_offset" in client


def test_web_tooling_files_exist() -> None:
    package_json = Path("web/package.json").read_text(encoding="utf-8")

    assert '"vite"' in package_json
    assert '"@monaco-editor/react"' in package_json
    assert Path("web/tsconfig.json").exists()
    assert Path("web/vite.config.ts").exists()
