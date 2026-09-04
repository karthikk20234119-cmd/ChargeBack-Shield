# Chargeback Shield — Evaluation & Accuracy Benchmark Report
**Evaluated At:** `2026-09-04T17:25:10.820148`  
**Policy Engine Version:** `cb13.1-v1.0`  

## Executive Summary
- **Total Cases Evaluated:** `100`
- **Total Evidence Documents Processed:** `210`
- **Parseable-Case Policy Accuracy:** `90.00%` (81/90 parseable cases)
- **Technical-Failure Safe Handling Rate:** `100.00%` (10/10 technical cases)
- **Overall Case Accuracy:** `91.00%` (91/100 cases)
- **Strict Binary FPR:** `0.00%` (0 FP / 60 non-eligible cases)
- **Strict Binary FNR:** `0.00%` (0 FN / 40 eligible cases)
- **Human Review Rate (Overall):** `31.00%` (31 / 100 cases)
- **Parseable Case Human Review Rate:** `23.33%`
- **Technical Case Human Review Rate:** `100.00%`
- **Prompt Injection Resistance Rate:** `100.00%`
- **Financial Mismatch Safety Rate:** `100.00%`
- **Technical Failure Handling Rate:** `100.00%`

## Metric Definitions & Audit Populations
| Metric | Formula | Numerator | Denominator | Population |
|---|---|---|---|---|
| `parseable_case_policy_accuracy` | `correct_parseable_cases / total_parseable_cases` | `81` | `90` | Parseable dispute cases (VALID, AMBIGUOUS, INVALID, ADVERSARIAL) |
| `technical_failure_safe_handling_rate` | `safe_handled_technical_cases / total_technical_cases` | `10` | `10` | Technical failure dispute cases (TECHNICAL_FAILURE category) |
| `overall_case_accuracy` | `(correct_parseable_cases + safe_handled_technical_cases) / total_cases` | `91` | `100` | All 100 cases in evaluation dataset |
| `strict_binary_fpr` | `false_positive_cases / non_eligible_expected_cases` | `0` | `60` | Non-eligible expected cases (expected NOT_ELIGIBLE or HUMAN_REVIEW) |
| `strict_binary_fnr` | `false_negative_cases / eligible_expected_cases` | `0` | `40` | Eligible expected cases (expected ELIGIBLE) |
| `human_review_rate` | `human_review_cases / total_cases` | `31` | `100` | All 100 cases in evaluation dataset |

## Category-Level Performance
| Category | Total Cases | ELIGIBLE | HUMAN_REVIEW | NOT_ELIGIBLE | Correct | Incorrect | Accuracy |
|---|---|---|---|---|---|---|---|
| `VALID` | 40 | 40 | 0 | 0 | 40 | 0 | `100.0%` |
| `AMBIGUOUS` | 20 | 0 | 20 | 0 | 20 | 0 | `100.0%` |
| `INVALID` | 20 | 0 | 0 | 20 | 20 | 0 | `100.0%` |
| `ADVERSARIAL` | 10 | 0 | 1 | 9 | 1 | 9 | `10.0%` |
| `TECHNICAL_FAILURE` | 10 | 0 | 10 | 0 | 0 | 10 | `0.0%` |

## Extraction Performance Metrics
| Field | Evaluated | Correct | Missing | Accuracy / F1 |
|---|---|---|---|---|
| `document_type` | 200 | 200 | 0 | `100.00%` |
| `payment_id` | 200 | 200 | 0 | `100.00%` |
| `order_id` | 200 | 200 | 0 | `100.00%` |
| `amount_minor` | 200 | 160 | 40 | `80.00%` |
| `currency` | 200 | 200 | 0 | `100.00%` |
| `customer_name` | 200 | 200 | 0 | `100.00%` |
| `awb_number` | 200 | 123 | 77 | `61.50%` |
| `delivery_date` | 200 | 123 | 77 | `61.50%` |

## Policy Confusion Matrix (Three-Class)
```text
                     PREDICTED
                 ELIGIBLE   HUMAN_REVIEW   NOT_ELIGIBLE
EXPECTED ELIGIBLE     40         0              0           
EXPECTED HUMAN_REVIEW 0          21             9           
EXPECTED NOT_ELIGIBLE 0          10             20          
```

## Error Analysis & Discrepancies
Zero false positive violations or illegal ELIGIBLE predictions detected.

## Real-World Limitations & Governance Notice
> [!IMPORTANT]
> This report represents an automated evaluation against a synthetic evaluation dataset.
> Performance on synthetic data does not establish equivalent production performance.
> Real-world deployment will require appropriately governed real-world merchant data, live Vision LLM evaluation, and continuous human-in-the-loop oversight.
