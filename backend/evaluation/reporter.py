import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def save_evaluation_results(results: Dict[str, Any], output_dir: str = "evaluation") -> str:
    """
    Saves evaluation results into output_dir/results.json.
    """
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return json_path

def generate_markdown_report(results: Dict[str, Any], output_dir: str = "evaluation") -> str:
    """
    Generates evaluation/report.md from evaluation results.
    Includes Metric Definitions, Executive Summary, Category Breakdown, Confusion Matrix, and Safety Metrics.
    """
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "report.md")

    summary = results.get("summary", {})
    cat_metrics = results.get("category_metrics", {})
    ext_metrics = results.get("extraction_metrics", {})
    conf_matrix = results.get("confusion_matrix", {})
    error_analysis = results.get("error_analysis", [])
    metric_defs = results.get("metric_definitions", {})

    md = []
    md.append("# Chargeback Shield — Evaluation & Accuracy Benchmark Report")
    md.append(f"**Evaluated At:** `{results.get('evaluated_at')}`  ")
    md.append(f"**Policy Engine Version:** `{results.get('policy_version', 'cb13.1-v1.0')}`  ")
    md.append("")

    # --- Executive Summary ---
    md.append("## Executive Summary")
    md.append(f"- **Total Cases Evaluated:** `{summary.get('total_cases')}`")
    md.append(f"- **Total Evidence Documents Processed:** `{summary.get('total_documents')}`")
    md.append(f"- **Parseable-Case Policy Accuracy:** `{summary.get('parseable_case_policy_accuracy', 0) * 100:.2f}%` ({metric_defs.get('parseable_case_policy_accuracy', {}).get('numerator')}/{metric_defs.get('parseable_case_policy_accuracy', {}).get('denominator')} parseable cases)")
    md.append(f"- **Technical-Failure Safe Handling Rate:** `{summary.get('technical_failure_safe_handling_rate', 0) * 100:.2f}%` ({metric_defs.get('technical_failure_safe_handling_rate', {}).get('numerator')}/{metric_defs.get('technical_failure_safe_handling_rate', {}).get('denominator')} technical cases)")
    md.append(f"- **Overall Case Accuracy:** `{summary.get('overall_case_accuracy', 0) * 100:.2f}%` ({metric_defs.get('overall_case_accuracy', {}).get('numerator')}/{metric_defs.get('overall_case_accuracy', {}).get('denominator')} cases)")
    md.append(f"- **Strict Binary FPR:** `{summary.get('strict_binary_fpr', 0) * 100:.2f}%` ({summary.get('false_positive_count', 0)} FP / {summary.get('non_eligible_expected_cases', 0)} non-eligible cases)")
    md.append(f"- **Strict Binary FNR:** `{summary.get('strict_binary_fnr', 0) * 100:.2f}%` ({summary.get('false_negative_count', 0)} FN / {summary.get('eligible_expected_cases', 0)} eligible cases)")
    md.append(f"- **Human Review Rate (Overall):** `{summary.get('human_review_rate', 0) * 100:.2f}%` ({summary.get('human_review_count', 0)} / {summary.get('total_cases', 0)} cases)")
    md.append(f"- **Parseable Case Human Review Rate:** `{summary.get('parseable_human_review_rate', 0) * 100:.2f}%`")
    md.append(f"- **Technical Case Human Review Rate:** `{summary.get('technical_human_review_rate', 0) * 100:.2f}%`")
    md.append(f"- **Prompt Injection Resistance Rate:** `{summary.get('prompt_injection_resistance_rate', 0) * 100:.2f}%`")
    md.append(f"- **Financial Mismatch Safety Rate:** `{summary.get('financial_mismatch_safety_rate', 0) * 100:.2f}%`")
    md.append(f"- **Technical Failure Handling Rate:** `{summary.get('technical_failure_handling_rate', 0) * 100:.2f}%`")
    md.append("")

    # --- Metric Definitions & Audit Denominators ---
    md.append("## Metric Definitions & Audit Populations")
    md.append("| Metric | Formula | Numerator | Denominator | Population |")
    md.append("|---|---|---|---|---|")
    for mname, mdata in metric_defs.items():
        md.append(f"| `{mname}` | `{mdata.get('formula')}` | `{mdata.get('numerator')}` | `{mdata.get('denominator')}` | {mdata.get('population')} |")
    md.append("")

    # --- Category Breakdown ---
    md.append("## Category-Level Performance")
    md.append("| Category | Total Cases | ELIGIBLE | HUMAN_REVIEW | NOT_ELIGIBLE | Correct | Incorrect | Accuracy |")
    md.append("|---|---|---|---|---|---|---|---|")
    for cat, data in cat_metrics.items():
        tot = data.get("total", 1)
        corr = data.get("correct", 0)
        inc = tot - corr
        acc = (corr / tot) * 100
        md.append(f"| `{cat}` | {tot} | {data.get('eligible', 0)} | {data.get('human_review', 0)} | {data.get('not_eligible', 0)} | {corr} | {inc} | `{acc:.1f}%` |")
    md.append("")

    # --- Extraction Metrics ---
    md.append("## Extraction Performance Metrics")
    md.append("| Field | Evaluated | Correct | Missing | Accuracy / F1 |")
    md.append("|---|---|---|---|---|")
    for field_name, em in ext_metrics.items():
        md.append(f"| `{field_name}` | {em.get('total')} | {em.get('correct')} | {em.get('missing')} | `{em.get('accuracy') * 100:.2f}%` |")
    md.append("")

    # --- Policy Confusion Matrix ---
    md.append("## Policy Confusion Matrix (Three-Class)")
    md.append("```text")
    md.append("                     PREDICTED")
    md.append("                 ELIGIBLE   HUMAN_REVIEW   NOT_ELIGIBLE")
    labels = ["ELIGIBLE", "HUMAN_REVIEW", "NOT_ELIGIBLE"]
    for row in labels:
        e_val = conf_matrix.get(row, {}).get("ELIGIBLE", 0)
        h_val = conf_matrix.get(row, {}).get("HUMAN_REVIEW", 0)
        n_val = conf_matrix.get(row, {}).get("NOT_ELIGIBLE", 0)
        md.append(f"EXPECTED {row:<12} {e_val:<10} {h_val:<14} {n_val:<12}")
    md.append("```")
    md.append("")

    # --- Error Analysis ---
    md.append("## Error Analysis & Discrepancies")
    if error_analysis:
        md.append("| Case ID | Category | Field | Stage | Reason |")
        md.append("|---|---|---|---|---|")
        for err in error_analysis:
            md.append(f"| `{err.get('case_id')}` | `{err.get('category')}` | `{err.get('field')}` | `{err.get('stage')}` | {err.get('reason')} |")
    else:
        md.append("Zero false positive violations or illegal ELIGIBLE predictions detected.")
    md.append("")

    # --- Real-World Limitation Notice ---
    md.append("## Real-World Limitations & Governance Notice")
    md.append("> [!IMPORTANT]")
    md.append("> This report represents an automated evaluation against a synthetic evaluation dataset.")
    md.append("> Performance on synthetic data does not establish equivalent production performance.")
    md.append("> Real-world deployment will require appropriately governed real-world merchant data, live Vision LLM evaluation, and continuous human-in-the-loop oversight.")
    md.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    return report_path


def generate_visualizations(results: Dict[str, Any], output_dir: str = "evaluation"):
    """
    Generates visualization charts using matplotlib if installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(output_dir, exist_ok=True)

        # 1. Category Accuracy Bar Chart
        cat_metrics = results.get("category_metrics", {})
        categories = list(cat_metrics.keys())
        accuracies = [(cat_metrics[c]["correct"] / max(cat_metrics[c]["total"], 1)) * 100 for c in categories]

        plt.figure(figsize=(8, 4))
        plt.bar(categories, accuracies, color="#1e88e5")
        plt.title("Policy Engine Accuracy by Category (%)")
        plt.xlabel("Category")
        plt.ylabel("Accuracy (%)")
        plt.ylim(0, 105)
        for i, v in enumerate(accuracies):
            plt.text(i, v + 2, f"{v:.1f}%", ha="center", fontweight="bold")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "category_accuracy.png"))
        plt.close()

        # 2. Extraction Field Accuracy Bar Chart
        ext_metrics = results.get("extraction_metrics", {})
        fields = list(ext_metrics.keys())
        ext_accs = [ext_metrics[f]["accuracy"] * 100 for f in fields]

        plt.figure(figsize=(10, 4))
        plt.barh(fields, ext_accs, color="#43a047")
        plt.title("AI Extraction Field Accuracy (%)")
        plt.xlabel("Accuracy (%)")
        plt.xlim(0, 105)
        for i, v in enumerate(ext_accs):
            plt.text(v + 1, i, f"{v:.1f}%", va="center")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "extraction_accuracy.png"))
        plt.close()

        logger.info(f"Successfully generated visualization charts in {output_dir}/")
    except Exception as ex:
        logger.info(f"Skipping matplotlib chart generation: {ex}")
