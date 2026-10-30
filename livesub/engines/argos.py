"""Offline translation with Argos language packages."""

from __future__ import annotations

from collections import deque
import os
import re

from livesub.engines import StatusCallback
from livesub.settings import MODEL_DIR


def _find_path(
    edges: set[tuple[str, str]], source: str, target: str
) -> list[tuple[str, str]] | None:
    if source == target:
        return []
    queue = deque([(source, [])])
    seen = {source}
    while queue:
        current, path = queue.popleft()
        for start, end in sorted(edges):
            if start != current or end in seen:
                continue
            next_path = path + [(start, end)]
            if end == target:
                return next_path
            seen.add(end)
            queue.append((end, next_path))
    return None


def _configure_argos_paths() -> None:
    """Keep model files next to the app before importing Argos."""
    argos_dir = MODEL_DIR / "argos"
    os.environ["ARGOS_CHUNK_TYPE"] = "MINISBD"
    os.environ["ARGOS_DEVICE_TYPE"] = "cpu"
    os.environ["XDG_DATA_HOME"] = str(argos_dir / "data")
    os.environ["XDG_CONFIG_HOME"] = str(argos_dir / "config")
    os.environ["XDG_CACHE_HOME"] = str(argos_dir / "cache")


class ArgosTranslator:
    def __init__(self) -> None:
        _configure_argos_paths()
        try:
            import argostranslate.package as package
            import argostranslate.translate as translate
        except ImportError as exc:
            raise RuntimeError("Thiếu argostranslate. Cài các gói trong requirements.txt.") from exc
        self.package = package
        self.translate_module = translate
        self.ready_pairs: set[tuple[str, str]] = set()

    def ensure_pair(self, source: str, target: str, status: StatusCallback) -> None:
        if source == target or (source, target) in self.ready_pairs:
            return
        installed = self.package.get_installed_packages()
        installed_edges = {(pkg.from_code, pkg.to_code) for pkg in installed}
        if _find_path(installed_edges, source, target) is not None:
            self.ready_pairs.add((source, target))
            return
        status(f"Đang tìm gói dịch {source} → {target}…")
        try:
            self.package.update_package_index()
            available = self.package.get_available_packages()
        except Exception as exc:
            raise RuntimeError(
                f"Chưa có gói dịch {source} → {target} trên máy và không tải được danh sách model: {exc}"
            ) from exc
        by_edge = {(pkg.from_code, pkg.to_code): pkg for pkg in available}
        path = _find_path(installed_edges | set(by_edge), source, target)
        if path is None:
            raise RuntimeError(
                f"Argos chưa có đường dịch {source} → {target}. Hãy chọn Ollama hoặc cặp ngôn ngữ khác."
            )
        for edge in path:
            if edge in installed_edges:
                continue
            status(f"Đang tải gói dịch miễn phí {edge[0]} → {edge[1]}…")
            try:
                self.package.install_from_path(by_edge[edge].download())
            except Exception as exc:
                raise RuntimeError(f"Không cài được gói dịch {edge[0]} → {edge[1]}: {exc}") from exc
            installed_edges.add(edge)
        self.ready_pairs.add((source, target))

    def translate(
        self, text: str, source: str, target: str,
        terms: tuple[str, ...], status: StatusCallback,
    ) -> str:
        if source == target:
            return text
        self.ensure_pair(source, target, status)
        try:
            if not terms:
                return self.translate_module.translate(text, source, target).strip()
            pattern = re.compile(
                "(" + "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)) + ")"
            )
            exact_terms = set(terms)

            def translate_piece(part: str) -> str:
                if part in exact_terms:
                    return part
                left = len(part) - len(part.lstrip())
                right = len(part) - len(part.rstrip())
                middle = part.strip()
                if not middle:
                    return part
                return (
                    part[:left]
                    + self.translate_module.translate(middle, source, target).strip()
                    + (part[len(part) - right:] if right else "")
                )

            return "".join(translate_piece(part) for part in pattern.split(text) if part).strip()
        except Exception as exc:
            raise RuntimeError(f"Argos không dịch được {source} → {target}: {exc}") from exc
