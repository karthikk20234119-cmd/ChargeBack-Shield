import os
import json
import pytest
import pypdf
from PIL import Image

from dataset.generator import generate_dataset
from dataset.validate_dataset import validate_dataset

DATASET_DIR = "dataset"

@pytest.fixture(scope="session", autouse=True)
def ensure_dataset_generated():
    if not os.path.exists(os.path.join(DATASET_DIR, "manifest.json")):
        generate_dataset(total_cases=100, seed=12345, base_dir=DATASET_DIR)

def test_manifest_correct():
    manifest_path = os.path.join(DATASET_DIR, "manifest.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    assert manifest["dataset_version"] == "1.0"
    assert manifest["seed"] == 12345
    assert manifest["total_cases"] == 100
    assert manifest["categories"]["VALID"] == 40
    assert manifest["categories"]["AMBIGUOUS"] == 20
    assert manifest["categories"]["INVALID"] == 20
    assert manifest["categories"]["ADVERSARIAL"] == 10
    assert manifest["categories"]["TECHNICAL_FAILURE"] == 10

def test_dataset_count():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    cases_dir = os.path.join(DATASET_DIR, "cases")
    
    gt_files = [f for f in os.listdir(ground_truth_dir) if f.endswith(".json")]
    case_dirs = [d for d in os.listdir(cases_dir) if os.path.isdir(os.path.join(cases_dir, d))]
    
    assert len(gt_files) == 100
    assert len(case_dirs) == 100

def test_category_distribution():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    counts = {"VALID": 0, "AMBIGUOUS": 0, "INVALID": 0, "ADVERSARIAL": 0, "TECHNICAL_FAILURE": 0}
    
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            with open(os.path.join(ground_truth_dir, f_name), "r", encoding="utf-8") as f:
                data = json.load(f)
                cat = data.get("category")
                counts[cat] = counts.get(cat, 0) + 1
                
    assert counts["VALID"] == 40
    assert counts["AMBIGUOUS"] == 20
    assert counts["INVALID"] == 20
    assert counts["ADVERSARIAL"] == 10
    assert counts["TECHNICAL_FAILURE"] == 10

def test_unique_case_ids():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    case_ids = set()
    
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            with open(os.path.join(ground_truth_dir, f_name), "r", encoding="utf-8") as f:
                data = json.load(f)
                case_id = data.get("case_id")
                assert case_id not in case_ids
                case_ids.add(case_id)
                
    assert len(case_ids) == 100

def test_unique_document_ids():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    document_ids = set()
    
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            with open(os.path.join(ground_truth_dir, f_name), "r", encoding="utf-8") as f:
                data = json.load(f)
                for doc in data.get("documents", []):
                    doc_id = doc.get("document_id")
                    assert doc_id not in document_ids
                    document_ids.add(doc_id)
                    
    assert len(document_ids) > 100

def test_ground_truth_exists():
    cases_dir = os.path.join(DATASET_DIR, "cases")
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    
    for case_id in os.listdir(cases_dir):
        gt_file = os.path.join(ground_truth_dir, f"{case_id}.json")
        assert os.path.exists(gt_file)

def test_valid_documents_open():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    cases_dir = os.path.join(DATASET_DIR, "cases")
    
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            with open(os.path.join(ground_truth_dir, f_name), "r", encoding="utf-8") as f:
                data = json.load(f)
                if data["category"] == "VALID":
                    case_id = data["case_id"]
                    for doc in data["documents"]:
                        doc_path = os.path.join(cases_dir, case_id, doc["filename"])
                        assert os.path.exists(doc_path)
                        if doc_path.endswith(".pdf"):
                            reader = pypdf.PdfReader(doc_path)
                            assert len(reader.pages) > 0
                        elif doc_path.endswith(".png"):
                            img = Image.open(doc_path)
                            img.verify()

def test_ground_truth_is_separate():
    cases_dir = os.path.join(DATASET_DIR, "cases")
    assert not os.path.exists(os.path.join(cases_dir, "ground_truth"))
    assert not os.path.exists(os.path.join(cases_dir, "ground_truth.json"))

def test_deterministic_generation(tmp_path):
    target_tmp = str(tmp_path / "dataset_test")
    generate_dataset(total_cases=10, seed=999, base_dir=target_tmp)
    
    # Re-run with same seed
    target_tmp2 = str(tmp_path / "dataset_test_2")
    generate_dataset(total_cases=10, seed=999, base_dir=target_tmp2)
    
    gt1 = json.load(open(os.path.join(target_tmp, "ground_truth", "case_0001.json")))
    gt2 = json.load(open(os.path.join(target_tmp2, "ground_truth", "case_0001.json")))
    
    assert gt1["trusted_data"]["amount"] == gt2["trusted_data"]["amount"]
    assert gt1["trusted_data"]["customer_name"] == gt2["trusted_data"]["customer_name"]

def test_no_real_credentials():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            content = open(os.path.join(ground_truth_dir, f_name)).read()
            assert "rzp_live_" not in content
            assert "gsk_" not in content
            assert "sk-proj-" not in content

def test_invalid_cases_contain_expected_contradictions():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    invalid_count = 0
    
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            data = json.load(open(os.path.join(ground_truth_dir, f_name)))
            if data["category"] == "INVALID":
                invalid_count += 1
                assert data["expected_outcome"] == "REJECT"
                assert data["contradiction_reason"] is not None
                
    assert invalid_count == 20

def test_adversarial_cases_contain_adversarial_content():
    ground_truth_dir = os.path.join(DATASET_DIR, "ground_truth")
    adv_count = 0
    
    for f_name in os.listdir(ground_truth_dir):
        if f_name.endswith(".json"):
            data = json.load(open(os.path.join(ground_truth_dir, f_name)))
            if data["category"] == "ADVERSARIAL":
                adv_count += 1
                assert data["expected_outcome"] == "HUMAN_REVIEW"
                assert "Adversarial prompt injection" in data["contradiction_reason"]
                
    assert adv_count == 10

def test_dataset_validator_script():
    assert validate_dataset(DATASET_DIR) is True
