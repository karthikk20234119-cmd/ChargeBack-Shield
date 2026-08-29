import os
import sys
import asyncio
import json
import logging

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base
from backend.app.database import AsyncSessionLocal
from backend.evaluation.harness import EvaluationHarness
from backend.evaluation.reporter import save_evaluation_results, generate_markdown_report, generate_visualizations

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("=" * 60)
    print("CHARGEBACK SHIELD — END-TO-END EVALUATION HARNESS")
    print("=" * 60)


    # Clean stale database file if present
    if os.path.exists("chargeback_shield.db"):
        try:
            os.remove("chargeback_shield.db")
        except Exception:
            pass

    # Initialize fresh DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


    async with AsyncSessionLocal() as db:
        harness = EvaluationHarness(dataset_dir="dataset")
        print("\n[1/3] Running evaluation over synthetic dataset...")
        results = await harness.evaluate_dataset(db)

        print("\n[2/3] Writing results to evaluation/results.json and evaluation/report.md...")
        json_path = save_evaluation_results(results, output_dir="evaluation")
        report_path = generate_markdown_report(results, output_dir="evaluation")
        generate_visualizations(results, output_dir="evaluation")

        summary = results["summary"]
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS SUMMARY")
        print("=" * 60)
        print(f"Total Cases Evaluated:           {summary['total_cases']}")
        print(f"Total Documents Processed:       {summary['total_documents']}")
        print(f"Parseable Policy Accuracy:       {summary['parseable_case_policy_accuracy'] * 100:.2f}%")
        print(f"Tech Failure Safe Rate:          {summary['technical_failure_safe_handling_rate'] * 100:.2f}%")
        print(f"Overall Case Accuracy:           {summary['overall_case_accuracy'] * 100:.2f}%")
        print(f"Strict Binary FPR:               {summary['strict_binary_fpr'] * 100:.2f}%")
        print(f"Strict Binary FNR:               {summary['strict_binary_fnr'] * 100:.2f}%")
        print(f"Human Review Rate:               {summary['human_review_rate'] * 100:.2f}%")
        print(f"Prompt Injection Resistance:     {summary['prompt_injection_resistance_rate'] * 100:.2f}%")
        print(f"Financial Mismatch Safety:       {summary['financial_mismatch_safety_rate'] * 100:.2f}%")
        print(f"Technical Failure Handling:      {summary['technical_failure_handling_rate'] * 100:.2f}%")
        print("=" * 60)
        print(f"\nArtifacts saved successfully:\n- {json_path}\n- {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
