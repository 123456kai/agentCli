import re
import subprocess
from pathlib import Path

IGNORED_NAMES: frozenset[str] = frozenset(
    (
        ".DS_Store",
        ".bzr",
        ".git",
        ".hg",
        ".svn",
        ".build",
        ".cache",
        ".coverage",
        ".fleet",
        ".gradle",
        ".idea",
        ".ipynb_checkpoints",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".vs",
        ".vscode",
        ".next",
        ".nuxt",
        ".parcel-cache",
        ".svelte-kit",
        ".turbo",
        ".vercel",
        "node_modules",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "pip-wheel-metadata",
        "venv",
        ".mvn",
        "out",
        "target",
        "bin",
        "cmake-build-debug",
        "cmake-build-release",
        "obj",
        "bazel-bin",
        "bazel-out",
        "bazel-testlogs",
        "buck-out",
        ".dart_tool",
        ".serverless",
        ".stack-work",
        ".terraform",
        ".terragrunt-cache",
        "DerivedData",
        "Pods",
        "deps",
        "tmp",
        "vendor",
    )
)

IGNORED_PATTERNS: re.Pattern[str] = re.compile(
    r"|".join(
        (
            r".*_cache$",
            r".*-cache$",
            r".*\.egg-info$",
            r".*\.dist-info$",
            r".*\.py[co]$",
            r".*\.class$",
            r".*\.sw[po]$",
            r".*~$",
            r".*\.(?:tmp|bak)$",
        )
    ),
    re.IGNORECASE,
)

SENSITIVE_NAMES: frozenset[str] = frozenset(
    (
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "credentials.json",
        "service-account.json",
        "secrets.yml",
        "secrets.yaml",
        "id_rsa",
        "id_ed25519",
        ".htpasswd",
    )
)

BINARY_EXTENSIONS: frozenset[str] = frozenset(
    (
        ".7z",
        ".bz2",
        ".dll",
        ".ear",
        ".exe",
        ".gz",
        ".gzip",
        ".ico",
        ".jar",
        ".jpg",
        ".jpeg",
        ".mp3",
        ".mp4",
        ".o",
        ".pdf",
        ".png",
        ".pyc",
        ".pyd",
        ".rar",
        ".so",
        ".tar",
        ".tgz",
        ".war",
        ".whl",
        ".xz",
        ".zip",
    )
)

MAX_LINES = 1000
MAX_BYTES = 100 << 10
MAX_LINE_LENGTH = 2000


def is_ignored(name: str) -> bool:
    if not name:
        return True
    if name in IGNORED_NAMES:
        return True
    return bool(IGNORED_PATTERNS.fullmatch(name))


def is_binary_by_extension(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def is_sensitive_file(path: Path) -> bool:
    return path.name in SENSITIVE_NAMES


def resolve_safe_path(repo_root: Path, user_path: str) -> Path:
    """Resolve *user_path* relative to *repo_root*, rejecting traversal and out-of-repo paths."""
    resolved_root = repo_root.resolve()

    raw = Path(user_path)
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (resolved_root / raw).resolve()

    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        raise ValueError(
            f"Path '{user_path}' resolves outside the repository root. "
            "Only paths within the repository are accessible."
        )

    if ".." in raw.parts:
        raise ValueError(
            f"Path '{user_path}' contains '..' which is not allowed."
        )

    return candidate


def walk_filtered(repo_root: Path, scope: str | None = None) -> list[Path]:
    """Walk the repo returning file paths, filtering ignored entries."""
    import os

    resolved_root = repo_root.resolve()
    walk_root = (resolved_root / scope).resolve() if scope else resolved_root

    try:
        if not walk_root.is_relative_to(resolved_root):
            return []
    except (OSError, ValueError):
        return []

    files: list[Path] = []
    try:
        for current_root, dirs, filenames in os.walk(walk_root):
            dirs[:] = sorted(d for d in dirs if not is_ignored(d))
            relative_root = Path(current_root).resolve().relative_to(resolved_root)
            if relative_root.parts and any(is_ignored(p) for p in relative_root.parts):
                dirs[:] = []
                continue
            for fname in sorted(filenames):
                if is_ignored(fname):
                    continue
                files.append(Path(current_root) / fname)
    except OSError:
        pass

    return files


def detect_git(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_root,
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except Exception:
        return False


def list_files_git(repo_root: Path) -> list[str] | None:
    """List tracked + untracked files via git ls-files. Returns None on failure."""
    resolved = repo_root.resolve()
    try:
        tracked = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--recurse-submodules"],
            cwd=resolved,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if tracked.returncode != 0:
            return None
        others = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z", "--others", "--exclude-standard"],
            cwd=resolved,
            capture_output=True,
            text=True,
            timeout=5,
        )
        untracked = others.stdout.split("\0") if others.returncode == 0 else []
    except Exception:
        return None

    paths: list[str] = []
    for entry in tracked.stdout.split("\0"):
        if not entry:
            continue
        parts = entry.split("/")
        if any(is_ignored(p) for p in parts):
            continue
        paths.append(entry)

    tracked_set = set(paths)
    for entry in untracked:
        if not entry:
            continue
        parts = entry.split("/")
        if any(is_ignored(p) for p in parts):
            continue
        if entry not in tracked_set:
            paths.append(entry)

    return sorted(paths)


def enumerate_repo_files(repo_root: Path) -> list[str]:
    """Get relative file paths for the repo, preferring git ls-files."""
    resolved = repo_root.resolve()
    if detect_git(resolved):
        git_files = list_files_git(resolved)
        if git_files is not None:
            return git_files
    walk_files = walk_filtered(resolved)
    return sorted(
        f.resolve().relative_to(resolved).as_posix() for f in walk_files
    )
