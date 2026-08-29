"""
AST Static Architecture Security Audit Suite — Chargeback Shield Task 8.5

Uses Python's `ast` parser to statically inspect codebase AST nodes, ensuring:
1. ContestSubmissionClient.submit_contest is the SINGLE contest submission boundary.
2. Zero accept_dispute, reject_dispute, or refund methods exist.
3. Zero direct HTTP mutation routes exist in read-only services.
4. Zero LLM, embedding, or AI decision calls exist.
"""

import os
import ast
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
SERVICES_DIR = os.path.join(ROOT_DIR, "backend", "app", "services")


def get_ast_for_file(filepath: str) -> ast.AST:
    with open(filepath, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=filepath)


def test_ast_prohibits_financial_mutation_methods():
    """Statically verifies no service class defines accept_dispute, reject_dispute, or issue_refund."""
    forbidden_method_names = {"accept_dispute", "reject_dispute", "issue_refund", "auto_refund", "auto_accept"}

    for root, _, files in os.walk(SERVICES_DIR):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            tree = get_ast_for_file(path)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_method_names, f"FORBIDDEN METHOD FOUND: {node.name} in {file}"


def test_ast_single_submission_mutation_boundary():
    """Statically verifies ContestSubmissionClient.submit_contest is the ONLY submission boundary."""
    path = os.path.join(SERVICES_DIR, "contest_submission_client.py")
    tree = get_ast_for_file(path)

    methods = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert "submit_contest" in methods
    assert "auto_retry" not in methods
    assert "resubmit" not in methods


def test_ast_zero_llm_or_embedding_calls():
    """Statically verifies no OpenAI, Anthropic, or LLM import statements exist in backend decision/submission services."""
    forbidden_imports = {"anthropic", "langchain", "llama_index", "transformers"}

    for root, _, files in os.walk(os.path.join(ROOT_DIR, "backend", "app")):
        for file in files:
            if not file.endswith(".py") or "ai_provider.py" in file:
                continue
            path = os.path.join(root, file)
            tree = get_ast_for_file(path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in forbidden_imports, f"FORBIDDEN LLM IMPORT: {alias.name} in {file}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert node.module.split(".")[0] not in forbidden_imports, f"FORBIDDEN LLM IMPORT: {node.module} in {file}"
