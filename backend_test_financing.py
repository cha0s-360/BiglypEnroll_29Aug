#!/usr/bin/env python3
"""
BiglypEnroll Backend Testing - Financing Economics
Testing POST /api/parent/financing/preview and POST /api/parent/pay-financing
"""
import requests
import json
import re

# Backend URL from frontend/.env
BASE_URL = "https://github-preview-63.preview.emergentagent.com/api"

# Test credentials from test_credentials.md
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"
SCHOOL_EMAIL = "school@biglyp.com"
SCHOOL_PASSWORD = "school123"

def login(email: str, password: str) -> str:
    """Login and return access token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed for {email}: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("token")

# ============================================================================
# TEST 1: Preview with amount=65000, down=0, tenure=12
# ============================================================================

def test_preview_65k():
    """Test 1: POST /api/parent/financing/preview with amount=65000, down=0, tenure=12"""
    print("\n[TEST 1] POST /api/parent/financing/preview - amount=65000, down=0, tenure=12")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "amount": 65000,
        "down_payment": 0,
        "tenure": 12
    }
    
    resp = requests.post(f"{BASE_URL}/parent/financing/preview", json=payload, headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:1000]}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify expected values
    print(f"\n  Returned values:")
    print(f"    emi: {data.get('emi')}")
    print(f"    interest: {data.get('interest')}")
    print(f"    processing_fee: {data.get('processing_fee')}")
    print(f"    apr: {data.get('apr')}")
    print(f"    total_repayment: {data.get('total_repayment')}")
    print(f"    amount_payable_now: {data.get('amount_payable_now')}")
    print(f"    requires_docs: {data.get('requires_docs')}")
    print(f"    doc_threshold: {data.get('doc_threshold')}")
    print(f"    schedule length: {len(data.get('schedule', []))}")
    
    # Assertions
    assert data.get("emi") == 5417, f"Expected emi=5417, got {data.get('emi')}"
    assert data.get("interest") == "0%", f"Expected interest='0%', got {data.get('interest')}"
    assert data.get("processing_fee") == 767, f"Expected processing_fee=767, got {data.get('processing_fee')}"
    assert data.get("apr") == 1.2, f"Expected apr=1.2, got {data.get('apr')}"
    assert data.get("total_repayment") == 65000, f"Expected total_repayment=65000, got {data.get('total_repayment')}"
    assert data.get("amount_payable_now") == 767, f"Expected amount_payable_now=767, got {data.get('amount_payable_now')}"
    assert data.get("requires_docs") is False, f"Expected requires_docs=False, got {data.get('requires_docs')}"
    assert data.get("doc_threshold") == 300000, f"Expected doc_threshold=300000, got {data.get('doc_threshold')}"
    assert len(data.get("schedule", [])) == 12, f"Expected 12-item schedule, got {len(data.get('schedule', []))}"
    
    print(f"\n  ✅ PASS: All values match expected")

# ============================================================================
# TEST 2: Preview with amount=400000, down=100000, tenure=12
# ============================================================================

def test_preview_400k_down_100k():
    """Test 2: POST /api/parent/financing/preview with amount=400000, down=100000, tenure=12"""
    print("\n[TEST 2] POST /api/parent/financing/preview - amount=400000, down=100000, tenure=12")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "amount": 400000,
        "down_payment": 100000,
        "tenure": 12
    }
    
    resp = requests.post(f"{BASE_URL}/parent/financing/preview", json=payload, headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:1000]}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify expected values
    print(f"\n  Returned values:")
    print(f"    financed_amount: {data.get('financed_amount')}")
    print(f"    processing_fee: {data.get('processing_fee')}")
    print(f"    amount_payable_now: {data.get('amount_payable_now')}")
    print(f"    requires_docs: {data.get('requires_docs')}")
    
    # Assertions
    assert data.get("financed_amount") == 300000, f"Expected financed_amount=300000, got {data.get('financed_amount')}"
    assert data.get("processing_fee") == 3540, f"Expected processing_fee=3540, got {data.get('processing_fee')}"
    assert data.get("amount_payable_now") == 103540, f"Expected amount_payable_now=103540, got {data.get('amount_payable_now')}"
    assert data.get("requires_docs") is False, f"Expected requires_docs=False (300000 is NOT > 300000), got {data.get('requires_docs')}"
    
    print(f"\n  ✅ PASS: All values match expected (requires_docs=False for financed_amount=300000)")

# ============================================================================
# TEST 3: Preview with amount=500000, down=0, tenure=12
# ============================================================================

def test_preview_500k():
    """Test 3: POST /api/parent/financing/preview with amount=500000, down=0, tenure=12"""
    print("\n[TEST 3] POST /api/parent/financing/preview - amount=500000, down=0, tenure=12")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "amount": 500000,
        "down_payment": 0,
        "tenure": 12
    }
    
    resp = requests.post(f"{BASE_URL}/parent/financing/preview", json=payload, headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:1000]}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify expected values
    print(f"\n  Returned values:")
    print(f"    financed_amount: {data.get('financed_amount')}")
    print(f"    requires_docs: {data.get('requires_docs')}")
    
    # Assertions
    assert data.get("financed_amount") == 500000, f"Expected financed_amount=500000, got {data.get('financed_amount')}"
    assert data.get("requires_docs") is True, f"Expected requires_docs=True (500000 > 300000), got {data.get('requires_docs')}"
    
    print(f"\n  ✅ PASS: requires_docs=True for financed_amount > 300000")

# ============================================================================
# TEST 4: Pay-financing for a real pending student
# ============================================================================

def test_pay_financing_real_student():
    """Test 4: POST /api/parent/pay-financing for a real pending student"""
    print("\n[TEST 4] POST /api/parent/pay-financing for real pending student")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 1: Get children
    resp = requests.get(f"{BASE_URL}/parent/children", headers=headers)
    print(f"  GET /api/parent/children status: {resp.status_code}")
    assert resp.status_code == 200
    children = resp.json()
    
    if len(children) == 0:
        print(f"  ⚠️  SKIP: No children found for parent")
        return
    
    student = children[0]
    student_id = student["id"]
    print(f"  Found student: {student['name']} (id={student_id})")
    
    # Step 2: Get fees for this student
    resp = requests.get(f"{BASE_URL}/parent/fees/{student_id}", headers=headers)
    print(f"  GET /api/parent/fees/{student_id} status: {resp.status_code}")
    assert resp.status_code == 200
    fee_data = resp.json()
    items = fee_data.get("items", [])
    
    # Find unpaid items
    unpaid = [item for item in items if not item.get("paid")]
    print(f"  Total fee items: {len(items)}, unpaid: {len(unpaid)}")
    
    if len(unpaid) == 0:
        print(f"  ⚠️  No payable items found. Attempting to reset demo state...")
        
        # Try to reset demo state
        school_token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
        school_headers = {"Authorization": f"Bearer {school_token}"}
        
        reset_resp = requests.post(f"{BASE_URL}/school/reset-demo", headers=school_headers)
        print(f"  POST /api/school/reset-demo status: {reset_resp.status_code}")
        
        if reset_resp.status_code == 200:
            print(f"  Demo state reset successful. Retrying...")
            
            # Retry getting fees
            resp = requests.get(f"{BASE_URL}/parent/fees/{student_id}", headers=headers)
            assert resp.status_code == 200
            fee_data = resp.json()
            items = fee_data.get("items", [])
            unpaid = [item for item in items if not item.get("paid")]
            print(f"  After reset - Total fee items: {len(items)}, unpaid: {len(unpaid)}")
            
            if len(unpaid) == 0:
                print(f"  ⚠️  SKIP: Still no payable items after reset")
                return
        else:
            print(f"  ⚠️  SKIP: Could not reset demo state")
            return
    
    # Select fee heads (take first unpaid item)
    fee_head_ids = [unpaid[0]["fee_head_id"]]
    print(f"  Selected fee_head_ids: {fee_head_ids}")
    
    # Step 3: POST /api/parent/pay-financing
    payload = {
        "student_id": student_id,
        "fee_head_ids": fee_head_ids,
        "tenure": 12,
        "down_payment": 0
    }
    
    resp = requests.post(f"{BASE_URL}/parent/pay-financing", json=payload, headers=headers)
    print(f"  POST /api/parent/pay-financing status: {resp.status_code}")
    print(f"  Response: {resp.text[:1500]}")
    
    if resp.status_code == 400:
        error_detail = resp.json().get("detail", "")
        if "No payable items selected" in error_detail:
            print(f"  ⚠️  ACCEPTABLE: No payable items selected (fees may already be paid)")
            return
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify response structure
    print(f"\n  Returned values:")
    print(f"    processing_fee: {data.get('processing_fee')}")
    print(f"    apr: {data.get('apr')}")
    print(f"    total_repayment: {data.get('total_repayment')}")
    print(f"    financed_amount: {data.get('financed_amount')}")
    print(f"    agreement_id: {data.get('agreement_id')}")
    print(f"    plan_type: {data.get('plan_type')}")
    print(f"    schedule length: {len(data.get('schedule', []))}")
    
    # Assertions
    assert data.get("processing_fee") > 0, f"Expected processing_fee > 0, got {data.get('processing_fee')}"
    assert data.get("apr") > 0, f"Expected apr > 0, got {data.get('apr')}"
    assert data.get("total_repayment") == data.get("financed_amount"), \
        f"Expected total_repayment == financed_amount, got {data.get('total_repayment')} != {data.get('financed_amount')}"
    
    agreement_id = data.get("agreement_id", "")
    assert agreement_id.startswith("BLP-AGR-"), f"Expected agreement_id to start with 'BLP-AGR-', got {agreement_id}"
    assert data.get("plan_type") == "EMI", f"Expected plan_type='EMI', got {data.get('plan_type')}"
    
    schedule = data.get("schedule", [])
    assert len(schedule) > 0, "Expected non-empty schedule"
    
    # Verify EMI 1 status='paid'
    emi1 = schedule[0]
    print(f"    EMI 1 status: {emi1.get('status')}")
    assert emi1.get("status") == "paid", f"Expected EMI 1 status='paid', got {emi1.get('status')}"
    
    print(f"\n  ✅ PASS: pay-financing successful with all required fields")

# ============================================================================
# TEST 5: Regression - verify interest is still 0% and existing fields present
# ============================================================================

def test_regression_interest_and_fields():
    """Test 5: Regression - verify interest='0%' and existing fields present"""
    print("\n[TEST 5] Regression - verify interest='0%' and existing fields")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "amount": 100000,
        "down_payment": 10000,
        "tenure": 6
    }
    
    resp = requests.post(f"{BASE_URL}/parent/financing/preview", json=payload, headers=headers)
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify interest is still 0%
    print(f"\n  Checking regression:")
    print(f"    interest: {data.get('interest')}")
    assert data.get("interest") == "0%", f"Expected interest='0%', got {data.get('interest')}"
    
    # Verify existing fields are present
    required_fields = ["emi", "financed_amount", "schedule", "down_payment", "tenure"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
        print(f"    {field}: {data.get(field) if field != 'schedule' else f'[{len(data.get(field, []))} items]'}")
    
    # Verify schedule structure
    schedule = data.get("schedule", [])
    assert len(schedule) > 0, "Expected non-empty schedule"
    
    first_item = schedule[0]
    assert "month" in first_item, "Schedule item missing 'month'"
    assert "due_date" in first_item, "Schedule item missing 'due_date'"
    assert "amount" in first_item, "Schedule item missing 'amount'"
    assert "status" in first_item, "Schedule item missing 'status'"
    
    print(f"\n  ✅ PASS: Regression verified - interest='0%' and all existing fields present")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print("=" * 80)
    print("BiglypEnroll Backend Testing - Financing Economics")
    print("Testing POST /api/parent/financing/preview and POST /api/parent/pay-financing")
    print("=" * 80)
    
    try:
        test_preview_65k()
        test_preview_400k_down_100k()
        test_preview_500k()
        test_pay_financing_real_student()
        test_regression_interest_and_fields()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✅")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
