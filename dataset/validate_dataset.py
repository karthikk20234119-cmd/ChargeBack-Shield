import os
import sys
import json
import pypdf
from PIL import Image

def validate_dataset(base_dir: str = "dataset") -> bool:
    manifest_path = os.path.join(base_dir, "manifest.json")
    cases_dir = os.path.join(base_dir, "cases")
    ground_truth_dir = os.path.join(base_dir, "ground_truth")

    print(f"Validating dataset at: '{base_dir}'...")

    if not os.path.exists(manifest_path):
        print("FAIL: manifest.json missing")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Check Manifest Schema & Category Counts
    total_cases = manifest.get("total_cases", 0)
    categories_expected = manifest.get("categories", {})
    
    print(f"Manifest total cases: {total_cases}")
    print(f"Manifest category breakdown: {categories_expected}")

    # 2. Check Data Leakage (Ground truth must NOT exist inside cases/)
    if os.path.exists(os.path.join(cases_dir, "ground_truth")) or os.path.exists(os.path.join(cases_dir, "ground_truth.json")):
        print("FAIL: Data leakage! Ground truth files detected inside model-input cases directory.")
        return False

    seen_case_ids = set()
    seen_document_ids = set()
    category_counts = {"VALID": 0, "AMBIGUOUS": 0, "INVALID": 0, "ADVERSARIAL": 0, "TECHNICAL_FAILURE": 0}

    # 3. Iterate over ground truth files and cases
    gt_files = [f for f in os.listdir(ground_truth_dir) if f.endswith(".json")]
    if len(gt_files) != total_cases:
        print(f"FAIL: Ground truth file count ({len(gt_files)}) does not match manifest total cases ({total_cases}).")
        return False

    for gt_filename in gt_files:
        gt_path = os.path.join(ground_truth_dir, gt_filename)
        with open(gt_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        case_id = data.get("case_id")
        category = data.get("category")
        trusted_data = data.get("trusted_data", {})
        docs = data.get("documents", [])
        expected_outcome = data.get("expected_outcome")

        # 4. Check Required Fields
        if not case_id or not category or not trusted_data or expected_outcome is None:
            print(f"FAIL: Missing required schema fields in ground truth file {gt_filename}.")
            return False

        # 5. Check Duplicate Case IDs
        if case_id in seen_case_ids:
            print(f"FAIL: Duplicate case_id detected: {case_id}")
            return False
        seen_case_ids.add(case_id)

        category_counts[category] = category_counts.get(category, 0) + 1

        # 6. Verify Case Directory & Document Ownership
        case_path = os.path.join(cases_dir, case_id)
        if not os.path.exists(case_path):
            print(f"FAIL: Case directory missing for ground truth case {case_id}")
            return False

        for doc in docs:
            doc_id = doc.get("document_id")
            filename = doc.get("filename")

            if not doc_id or not filename:
                print(f"FAIL: Document record missing document_id or filename in {case_id}")
                return False

            if doc_id in seen_document_ids:
                print(f"FAIL: Duplicate document_id detected: {doc_id}")
                return False
            seen_document_ids.add(doc_id)

            file_full_path = os.path.join(case_path, filename)
            if not os.path.exists(file_full_path):
                print(f"FAIL: Referenced document file missing: {file_full_path}")
                return False

            # Check filename leakage (filename should not contain labels like "VALID" or "REJECT")
            filename_lower = filename.lower()
            if "valid" in filename_lower or "reject" in filename_lower or "allow" in filename_lower:
                print(f"FAIL: Data leakage in filename '{filename}' for case {case_id}.")
                return False

            # 7. Check file integrity for VALID documents
            if category == "VALID":
                if filename.endswith(".pdf"):
                    try:
                        reader = pypdf.PdfReader(file_full_path)
                        if len(reader.pages) == 0:
                            print(f"FAIL: Valid case {case_id} PDF document has 0 pages.")
                            return False
                    except Exception as e:
                        print(f"FAIL: Valid case {case_id} PDF failed to parse: {e}")
                        return False
                elif filename.endswith(".png") or filename.endswith(".jpg"):
                    try:
                        img = Image.open(file_full_path)
                        img.verify()
                    except Exception as e:
                        print(f"FAIL: Valid case {case_id} image failed to parse: {e}")
                        return False

            # 8. Check technical failure cases
            if category == "TECHNICAL_FAILURE":
                is_failed = False
                if filename.endswith(".pdf"):
                    try:
                        reader = pypdf.PdfReader(file_full_path)
                        if len(reader.pages) == 0:
                            is_failed = True
                    except Exception:
                        is_failed = True
                elif filename.endswith(".png") or filename.endswith(".jpg"):
                    try:
                        img = Image.open(file_full_path)
                        img.verify()
                    except Exception:
                        is_failed = True
                elif filename.endswith(".exe") or os.path.getsize(file_full_path) == 0:
                    is_failed = True

                if not is_failed:
                    print(f"FAIL: TECHNICAL_FAILURE case {case_id} file {filename} is unexpectedly valid.")
                    return False

    # 9. Verify Category Counts against Manifest
    for cat_name, expected_num in categories_expected.items():
        actual_num = category_counts.get(cat_name, 0)
        if actual_num != expected_num:
            print(f"FAIL: Category count mismatch for {cat_name}: expected {expected_num}, found {actual_num}")
            return False

    print("==================================================")
    print("SUCCESS: Dataset validation passed 100%!")
    print(f"Total Cases Validated: {len(seen_case_ids)}")
    print(f"Total Documents Validated: {len(seen_document_ids)}")
    print(f"Category Breakdown: {category_counts}")
    print("==================================================")
    return True

if __name__ == "__main__":
    base_dir_arg = sys.argv[1] if len(sys.argv) > 1 else "dataset"
    success = validate_dataset(base_dir_arg)
    if not success:
        sys.exit(1)
