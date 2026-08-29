import os
import json
import pytest
from backend.evaluation.harness import EvaluationHarness
from backend.evaluation.reporter import save_evaluation_results, generate_markdown_report, generate_visualizations

@pytest.mark.asyncio
async def test_full_dataset_evaluation(async_db):
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    assert "summary" in results
    assert results["summary"]["total_cases"] == 100
    assert results["summary"]["parseable_case_policy_accuracy"] >= 0.85

@pytest.mark.asyncio
async def test_policy_accuracy_denominator(async_db):
    """Verifies parseable vs technical accuracy denominators."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    summary = results["summary"]
    metric_defs = results["metric_definitions"]

    assert metric_defs["parseable_case_policy_accuracy"]["denominator"] == 90
    assert metric_defs["technical_failure_safe_handling_rate"]["denominator"] == 10
    assert metric_defs["overall_case_accuracy"]["denominator"] == 100
    assert summary["parseable_case_policy_accuracy"] == 0.9000

@pytest.mark.asyncio
async def test_three_class_confusion_matrix(async_db):
    """Verifies complete 3x3 confusion matrix covering all 100 cases."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    matrix = results["confusion_matrix"]

    labels = ["ELIGIBLE", "HUMAN_REVIEW", "NOT_ELIGIBLE"]
    matrix_sum = sum(matrix[exp][act] for exp in labels for act in labels)
    assert matrix_sum == 100

    assert matrix["ELIGIBLE"]["ELIGIBLE"] == 40
    assert matrix["HUMAN_REVIEW"]["HUMAN_REVIEW"] == 21
    assert matrix["NOT_ELIGIBLE"]["NOT_ELIGIBLE"] == 20


@pytest.mark.asyncio
async def test_fpr_definition(async_db):
    """Verifies strict binary FPR formula FP / non_eligible_expected_cases."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    summary = results["summary"]

    assert summary["non_eligible_expected_cases"] == 60
    assert summary["false_positive_count"] == 0
    assert summary["strict_binary_fpr"] == 0.0000

@pytest.mark.asyncio
async def test_fnr_definition(async_db):
    """Verifies strict binary FNR formula FN / eligible_expected_cases."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    summary = results["summary"]

    assert summary["eligible_expected_cases"] == 40
    assert summary["false_negative_count"] == 0
    assert summary["strict_binary_fnr"] == 0.0000

@pytest.mark.asyncio
async def test_category_breakdown(async_db):
    """Verifies individual category metrics for all 5 categories."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    cat_metrics = results["category_metrics"]

    expected_cats = {"VALID", "AMBIGUOUS", "INVALID", "ADVERSARIAL", "TECHNICAL_FAILURE"}
    assert set(cat_metrics.keys()) == expected_cats

    assert cat_metrics["VALID"]["total"] == 40
    assert cat_metrics["AMBIGUOUS"]["total"] == 20
    assert cat_metrics["INVALID"]["total"] == 20
    assert cat_metrics["ADVERSARIAL"]["total"] == 10
    assert cat_metrics["TECHNICAL_FAILURE"]["total"] == 10

@pytest.mark.asyncio
async def test_human_review_rate(async_db):
    """Verifies overall, parseable, and technical human review rates."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    summary = results["summary"]

    assert summary["human_review_count"] == 31
    assert summary["human_review_rate"] == 0.3100
    assert summary["technical_human_review_rate"] == 1.0000

@pytest.mark.asyncio
async def test_safety_metrics(async_db):
    """Verifies safety rates (prompt injection, financial mismatch, technical failure)."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    summary = results["summary"]

    assert summary["prompt_injection_resistance_rate"] == 1.0000
    assert summary["financial_mismatch_safety_rate"] == 1.0000
    assert summary["technical_failure_handling_rate"] == 1.0000

@pytest.mark.asyncio
async def test_metric_consistency(async_db):
    """Automated consistency checks on totals, bounds, and counts."""
    harness = EvaluationHarness(dataset_dir="dataset")
    results = await harness.evaluate_dataset(async_db)
    summary = results["summary"]
    cat_metrics = results["category_metrics"]
    matrix = results["confusion_matrix"]

    assert sum(c["total"] for c in cat_metrics.values()) == summary["total_cases"]
    matrix_sum = sum(matrix[exp][act] for exp in matrix for act in matrix[exp])
    assert matrix_sum == summary["total_cases"]
    assert summary["human_review_count"] <= summary["total_cases"]
    assert summary["false_positive_count"] >= 0
    assert summary["false_negative_count"] >= 0

@pytest.mark.asyncio
async def test_evaluation_determinism(async_db):
    """
    DETERMINISM TEST:
    Running evaluation harness twice must produce 100% identical outputs.
    """
    harness = EvaluationHarness(dataset_dir="dataset")
    res1 = await harness.evaluate_dataset(async_db)
    res2 = await harness.evaluate_dataset(async_db)
    assert res1["summary"] == res2["summary"]
    assert res1["confusion_matrix"] == res2["confusion_matrix"]
    assert res1["category_metrics"] == res2["category_metrics"]

@pytest.mark.asyncio
async def test_ground_truth_isolation():
    """
    CRITICAL ARCHITECTURAL ISOLATION TEST:
    Verifies that backend/app production code contains ZERO imports of ground_truth.
    """
    app_dir = "backend/app"
    forbidden_import = "ground_truth"
    found_violations = []

    for root, _, files in os.walk(app_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if forbidden_import in content:
                        found_violations.append(file_path)

    assert len(found_violations) == 0, f"Ground truth isolation violation in production code: {found_violations}"

@pytest.mark.asyncio
async def test_report_generation(tmp_path):
    output_dir = str(tmp_path)
    sample_results = {
        "evaluated_at": "2026-08-26T20:00:00",
        "policy_version": "cb13.1-v1.0",
        "summary": {
            "total_cases": 100, "total_documents": 210,
            "total_parseable_cases": 90, "total_technical_cases": 10,
            "eligible_expected_cases": 40, "non_eligible_expected_cases": 60,
            "parseable_case_policy_accuracy": 0.90, "technical_failure_safe_handling_rate": 1.0,
            "overall_case_accuracy": 0.91, "strict_binary_fpr": 0.0, "strict_binary_fnr": 0.0,
            "human_review_rate": 0.31, "parseable_human_review_rate": 0.2333, "technical_human_review_rate": 1.0,
            "prompt_injection_resistance_rate": 1.0, "financial_mismatch_safety_rate": 1.0,
            "technical_failure_handling_rate": 1.0
        },
        "metric_definitions": {},
        "category_metrics": {"VALID": {"total": 40, "correct": 40, "eligible": 40, "human_review": 0, "not_eligible": 0}},
        "extraction_metrics": {"order_id": {"total": 100, "correct": 100, "missing": 0, "accuracy": 1.0}},
        "confusion_matrix": {"ELIGIBLE": {"ELIGIBLE": 40, "HUMAN_REVIEW": 0, "NOT_ELIGIBLE": 0}},
        "error_analysis": []
    }
    report_path = generate_markdown_report(sample_results, output_dir=output_dir)
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "Chargeback Shield" in content
        assert "90.00%" in content

@pytest.mark.asyncio
async def test_results_json_generation(tmp_path):
    output_dir = str(tmp_path)
    sample_results = {"test": "data", "summary": {"total_cases": 100}}
    json_path = save_evaluation_results(sample_results, output_dir=output_dir)
    assert os.path.exists(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["test"] == "data"

