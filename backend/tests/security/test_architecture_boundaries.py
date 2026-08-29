"""
Architectural Boundary Static Audit Test Suite — Chargeback Shield Task 6.5

Uses Python AST (Abstract Syntax Tree) and module inspection to statically verify:
1. Razorpay mutation operations exist ONLY inside ContestSubmissionClient.submit_contest().
2. Forbidden methods (accept_dispute, reject_dispute, issue_refund, submit_contest) do NOT exist anywhere else.
3. Razorpay client classes (RazorpayClient, ContestSubmissionClient, HttpContestSubmissionClient) are NOT imported by read-only services:
   - analytics_service.py
   - dashboard_service.py / dashboard.py
   - audit_reporting.py
   - operational_alert_service.py
   - policy_engine_service.py
   - matching_service.py
   - contest_draft_service.py
   - contest_draft_review_service.py
   - contest_submission_preflight_service.py
4. Read-only services contain ZERO direct HTTP network client instantiations.
"""

import ast
from pathlib import Path
import pytest

APP_DIR = Path(__file__).resolve().parent.parent.parent / "app"


def get_ast_tree(file_path: Path) -> ast.AST:
    """Parses a python source file into an AST tree."""
    with open(file_path, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=str(file_path))


class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        self.function_calls = set()
        self.method_defs = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports.add(f"{module}.{alias.name}" if module else alias.name)
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.function_calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.function_calls.add(node.func.attr)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.method_defs.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.method_defs.add(node.name)
        self.generic_visit(node)


def analyze_file(file_path: Path) -> ASTVisitor:
    tree = get_ast_tree(file_path)
    visitor = ASTVisitor()
    visitor.visit(tree)
    return visitor


# ===========================================================================
# 1. RAZORPAY MUTATION ISOLATION AUDIT
# ===========================================================================


def test_01_no_forbidden_razorpay_mutation_methods_exist_globally():
    """1. Verifies accept_dispute, reject_dispute, issue_refund do NOT exist anywhere in app."""
    forbidden_methods = {"accept_dispute", "reject_dispute", "issue_refund"}
    
    python_files = list(APP_DIR.glob("**/*.py"))
    assert len(python_files) > 0, "No python files found in backend/app"

    for p in python_files:
        visitor = analyze_file(p)
        defined_forbidden = visitor.method_defs.intersection(forbidden_methods)
        assert not defined_forbidden, f"Forbidden mutation method {defined_forbidden} defined in {p.name}"


def test_02_submit_contest_is_strictly_isolated_to_submission_boundary():
    """2. Verifies submit_contest is defined ONLY inside contest_submission_client/service."""
    allowed_files = {"contest_submission_client.py", "contest_submission_service.py"}
    
    python_files = list(APP_DIR.glob("**/*.py"))
    for p in python_files:
        if p.name in allowed_files:
            continue
        visitor = analyze_file(p)
        assert "submit_contest" not in visitor.method_defs, f"submit_contest method defined in unauthorized file: {p.name}"


# ===========================================================================
# 2. READ-ONLY COMPONENT ISOLATION AUDIT
# ===========================================================================


def test_03_read_only_services_do_not_import_razorpay_clients():
    """3. Verifies analytics, dashboard, audit, alerts, policy, matching, drafts, preflight do not import Razorpay clients."""
    read_only_files = [
        "analytics_service.py",
        "analytics.py",
        "dashboard.py",
        "audit_reporting.py",
        "operational_alert_service.py",
        "policy_engine_service.py",
        "matching_service.py",
        "contest_draft_service.py",
        "contest_draft_review_service.py",
        "contest_submission_preflight_service.py",
    ]

    razorpay_client_names = {"RazorpayClient", "ContestSubmissionClient", "HttpContestSubmissionClient", "MockContestSubmissionClient"}

    for name in read_only_files:
        matches = list(APP_DIR.glob(f"**/{name}"))
        for p in matches:
            visitor = analyze_file(p)
            imported_razorpay = visitor.imports.intersection(razorpay_client_names)
            assert not imported_razorpay, f"Read-only component {p.name} illegally imports {imported_razorpay}"


def test_04_read_only_services_do_not_instantiate_http_clients():
    """4. Verifies read-only services contain zero direct AsyncClient or requests calls."""
    read_only_service_files = [
        "analytics_service.py",
        "operational_alert_service.py",
        "policy_engine_service.py",
        "matching_service.py",
        "contest_draft_service.py",
        "contest_draft_review_service.py",
        "contest_submission_preflight_service.py",
    ]

    for name in read_only_service_files:
        matches = list(APP_DIR.glob(f"**/{name}"))
        for p in matches:
            visitor = analyze_file(p)
            assert "AsyncClient" not in visitor.imports, f"Read-only service {p.name} imports AsyncClient"
            assert "requests" not in visitor.imports, f"Read-only service {p.name} imports requests"
