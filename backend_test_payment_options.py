#!/usr/bin/env python3
"""
BiglypEnroll Backend Testing - School payment options (Option A/B/C) persistence + parent exposure
"""
import requests
import json

# Backend URL from frontend/.env
BASE_URL = "https://bigly-signup.preview.emergentagent.com/api"

# Test credentials from test_credentials.md
SCHOOL_EMAIL = "school@biglyp.com"
SCHOOL_PASSWORD = "school123"
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"

def login(email: str, password: str) -> str:
    """Login and return access token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed for {email}: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("token")

def test_step_1_get_student_id():
    """Step 1: Login as parent, GET /api/parent/children to obtain Aarav Sharma's student_id"""
    print("\n[STEP 1] GET /api/parent/children - Get Aarav Sharma's student_id")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/children", headers=headers)
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    children = resp.json()
    
    aarav = None
    for child in children:
        if child.get("name") == "Aarav Sharma":
            aarav = child
            break
    
    assert aarav is not None, "Aarav Sharma not found in children list"
    student_id = aarav["id"]
    print(f"  ✅ Found Aarav Sharma: student_id={student_id}, grade={aarav.get('grade')}")
    return student_id

def test_step_2_set_payment_options():
    """Step 2: POST /api/school/onboarding with payment_options {emi:true, auto_debit:false, full:true}"""
    print("\n[STEP 2] POST /api/school/onboarding - Set payment_options {emi:true, auto_debit:false, full:true}")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, GET /api/school to capture existing fields
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200, f"Failed to GET /api/school: {resp.status_code}"
    school = resp.json()
    
    print(f"  Current school data captured:")
    print(f"    - campuses: {len(school.get('campuses', []))} items")
    print(f"    - courses: {len(school.get('courses', []))} items")
    print(f"    - team: {len(school.get('team', []))} items")
    print(f"    - multi_account_enabled: {school.get('multi_account_enabled')}")
    print(f"    - settlement_accounts: {len(school.get('settlement_accounts', []))} items")
    print(f"    - payment_options (before): {school.get('payment_options')}")
    
    # POST /api/school/onboarding with payment_options
    onboarding_payload = {
        "campuses": school.get("campuses", []),
        "courses": school.get("courses", []),
        "team": school.get("team", []),
        "multi_account_enabled": school.get("multi_account_enabled", False),
        "settlement_accounts": school.get("settlement_accounts", []),
        "payment_options": {"emi": True, "auto_debit": False, "full": True},
        "complete": True
    }
    
    resp = requests.post(f"{BASE_URL}/school/onboarding", json=onboarding_payload, headers=headers)
    print(f"  POST /api/school/onboarding status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"  Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    print(f"  ✅ PASS: Onboarding updated successfully")

def test_step_3_verify_payment_options_persisted():
    """Step 3: GET /api/school -> confirm payment_options == {emi:true, auto_debit:false, full:true}"""
    print("\n[STEP 3] GET /api/school - Verify payment_options persisted")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    school = resp.json()
    
    payment_options = school.get("payment_options")
    print(f"  payment_options: {payment_options}")
    
    assert payment_options is not None, "payment_options is None"
    assert payment_options.get("emi") is True, f"Expected emi=True, got {payment_options.get('emi')}"
    assert payment_options.get("auto_debit") is False, f"Expected auto_debit=False, got {payment_options.get('auto_debit')}"
    assert payment_options.get("full") is True, f"Expected full=True, got {payment_options.get('full')}"
    
    print(f"  ✅ PASS: payment_options correctly persisted as {{emi:true, auto_debit:false, full:true}}")

def test_step_4_verify_parent_exposure(student_id: str):
    """Step 4: GET /api/parent/fees/{student_id} as parent -> confirm payment_options exposed"""
    print(f"\n[STEP 4] GET /api/parent/fees/{student_id} - Verify payment_options exposed to parent")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/fees/{student_id}", headers=headers)
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    payment_options = data.get("payment_options")
    print(f"  payment_options: {payment_options}")
    
    assert payment_options is not None, "payment_options is None"
    assert payment_options.get("emi") is True, f"Expected emi=True, got {payment_options.get('emi')}"
    assert payment_options.get("auto_debit") is False, f"Expected auto_debit=False, got {payment_options.get('auto_debit')}"
    assert payment_options.get("full") is True, f"Expected full=True, got {payment_options.get('full')}"
    
    print(f"  ✅ PASS: payment_options correctly exposed to parent as {{emi:true, auto_debit:false, full:true}}")

def test_step_5_all_false_fallback():
    """Step 5: POST onboarding with payment_options all-false -> should fallback to all-true"""
    print("\n[STEP 5] POST /api/school/onboarding - Test all-false fallback")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, GET /api/school to capture existing fields
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200, f"Failed to GET /api/school: {resp.status_code}"
    school = resp.json()
    
    # POST with payment_options all-false
    onboarding_payload = {
        "campuses": school.get("campuses", []),
        "courses": school.get("courses", []),
        "team": school.get("team", []),
        "multi_account_enabled": school.get("multi_account_enabled", False),
        "settlement_accounts": school.get("settlement_accounts", []),
        "payment_options": {"emi": False, "auto_debit": False, "full": False},
        "complete": True
    }
    
    resp = requests.post(f"{BASE_URL}/school/onboarding", json=onboarding_payload, headers=headers)
    print(f"  POST /api/school/onboarding status: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # GET /api/school to verify fallback
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    school = resp.json()
    
    payment_options = school.get("payment_options")
    print(f"  payment_options after all-false: {payment_options}")
    
    assert payment_options is not None, "payment_options is None"
    assert payment_options.get("emi") is True, f"Expected emi=True (fallback), got {payment_options.get('emi')}"
    assert payment_options.get("auto_debit") is True, f"Expected auto_debit=True (fallback), got {payment_options.get('auto_debit')}"
    assert payment_options.get("full") is True, f"Expected full=True (fallback), got {payment_options.get('full')}"
    
    print(f"  ✅ PASS: payment_options correctly fell back to all-true when all-false was sent")

def test_step_6_omit_payment_options():
    """Step 6: POST onboarding WITHOUT payment_options key -> existing value must remain unchanged"""
    print("\n[STEP 6] POST /api/school/onboarding - Test omitting payment_options key")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, set a known payment_options value
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200, f"Failed to GET /api/school: {resp.status_code}"
    school = resp.json()
    
    # Set payment_options to {emi:false, auto_debit:true, full:false}
    onboarding_payload = {
        "campuses": school.get("campuses", []),
        "courses": school.get("courses", []),
        "team": school.get("team", []),
        "multi_account_enabled": school.get("multi_account_enabled", False),
        "settlement_accounts": school.get("settlement_accounts", []),
        "payment_options": {"emi": False, "auto_debit": True, "full": False},
        "complete": True
    }
    
    resp = requests.post(f"{BASE_URL}/school/onboarding", json=onboarding_payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # Verify it was set
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200
    school = resp.json()
    payment_options_before = school.get("payment_options")
    print(f"  payment_options before omit test: {payment_options_before}")
    
    # Now POST without payment_options key
    onboarding_payload_no_po = {
        "campuses": school.get("campuses", []),
        "courses": school.get("courses", []),
        "team": school.get("team", []),
        "multi_account_enabled": school.get("multi_account_enabled", False),
        "settlement_accounts": school.get("settlement_accounts", []),
        # NO payment_options key
        "complete": True
    }
    
    resp = requests.post(f"{BASE_URL}/school/onboarding", json=onboarding_payload_no_po, headers=headers)
    print(f"  POST /api/school/onboarding (without payment_options) status: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # GET /api/school to verify payment_options unchanged
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    school = resp.json()
    
    payment_options_after = school.get("payment_options")
    print(f"  payment_options after omit: {payment_options_after}")
    
    assert payment_options_after == payment_options_before, \
        f"payment_options changed when it should have remained unchanged: before={payment_options_before}, after={payment_options_after}"
    
    print(f"  ✅ PASS: payment_options remained unchanged when key was omitted")

def test_step_7_cleanup():
    """Step 7: CLEANUP - Restore payment_options to all-true"""
    print("\n[STEP 7] CLEANUP - Restore payment_options to all-true")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET /api/school to capture existing fields
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200, f"Failed to GET /api/school: {resp.status_code}"
    school = resp.json()
    
    # POST with payment_options all-true
    onboarding_payload = {
        "campuses": school.get("campuses", []),
        "courses": school.get("courses", []),
        "team": school.get("team", []),
        "multi_account_enabled": school.get("multi_account_enabled", False),
        "settlement_accounts": school.get("settlement_accounts", []),
        "payment_options": {"emi": True, "auto_debit": True, "full": True},
        "complete": True
    }
    
    resp = requests.post(f"{BASE_URL}/school/onboarding", json=onboarding_payload, headers=headers)
    print(f"  POST /api/school/onboarding status: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # Verify
    resp = requests.get(f"{BASE_URL}/school", headers=headers)
    assert resp.status_code == 200
    school = resp.json()
    payment_options = school.get("payment_options")
    print(f"  payment_options after cleanup: {payment_options}")
    
    assert payment_options.get("emi") is True
    assert payment_options.get("auto_debit") is True
    assert payment_options.get("full") is True
    
    print(f"  ✅ PASS: payment_options restored to all-true")

def main():
    print("=" * 80)
    print("BiglypEnroll Backend Testing - School payment options persistence + parent exposure")
    print("=" * 80)
    
    try:
        # Step 1: Get Aarav's student_id
        student_id = test_step_1_get_student_id()
        
        # Step 2: Set payment_options {emi:true, auto_debit:false, full:true}
        test_step_2_set_payment_options()
        
        # Step 3: Verify payment_options persisted
        test_step_3_verify_payment_options_persisted()
        
        # Step 4: Verify payment_options exposed to parent
        test_step_4_verify_parent_exposure(student_id)
        
        # Step 5: Test all-false fallback
        test_step_5_all_false_fallback()
        
        # Step 6: Test omitting payment_options key
        test_step_6_omit_payment_options()
        
        # Step 7: Cleanup - restore to all-true
        test_step_7_cleanup()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✅")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
