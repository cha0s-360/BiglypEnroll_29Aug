#!/usr/bin/env python3
"""
BiglypEnroll Backend API Testing Suite - Phase 2
Tests Parent Financing Endpoints (bank-config, preview, pay-financing)
"""
import requests
import json
import sys
from typing import Dict, Any, Optional

# Read backend URL from frontend/.env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"❌ Error reading backend URL: {e}")
        sys.exit(1)
    return None

BASE_URL = get_backend_url()
if not BASE_URL:
    print("❌ REACT_APP_BACKEND_URL not found in /app/frontend/.env")
    sys.exit(1)

print(f"🔗 Backend URL: {BASE_URL}")

# Test results tracking
test_results = {
    "passed": 0,
    "failed": 0,
    "details": []
}

def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")
    
    test_results["passed" if passed else "failed"] += 1
    test_results["details"].append({
        "name": name,
        "passed": passed,
        "details": details
    })

def login(email: str, password: str) -> Optional[str]:
    """Login and return access token"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            print(f"✅ Logged in as {email}")
            return token
        else:
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error for {email}: {e}")
        return None

def test_phase2_parent_financing():
    """Test Phase 2 Parent Financing Endpoints"""
    print("\n" + "="*80)
    print("TESTING: Phase 2 Parent Financing Endpoints")
    print("="*80 + "\n")
    
    # ========================================================================
    # Setup: Login as parent and admin
    # ========================================================================
    print("\n--- Setup: Login ---")
    parent_token = login("parent@biglyp.com", "parent123")
    if not parent_token:
        log_test("Setup: Login as parent", False, "Login failed")
        return
    log_test("Setup: Login as parent", True, "Successfully logged in")
    
    creditops_token = login("creditops@biglyp.com", "creditops123")
    if not creditops_token:
        log_test("Setup: Login as creditops", False, "Login failed")
        return
    log_test("Setup: Login as creditops", True, "Successfully logged in")
    
    # ========================================================================
    # Test 1: GET /api/parent/financing/bank-config
    # ========================================================================
    print("\n--- Test 1: GET /api/parent/financing/bank-config ---")
    try:
        response = requests.get(
            f"{BASE_URL}/api/parent/financing/bank-config",
            headers={"Authorization": f"Bearer {parent_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            config = response.json()
            log_test("Test 1: GET bank-config returns 200", True, f"Response: {json.dumps(config, indent=2)}")
            
            # Verify expected fields
            has_required_fields = all([
                "id" in config,
                "name" in config,
                "advance_emi" in config,
                "min_loan_amount" in config
            ])
            
            if has_required_fields:
                log_test("Test 1: bank-config has required fields", True, 
                        f"id={config.get('id')}, name={config.get('name')}, advance_emi={config.get('advance_emi')}, min_loan_amount={config.get('min_loan_amount')}")
            else:
                log_test("Test 1: bank-config has required fields", False, 
                        f"Missing fields in response")
            
            # Verify CSB Bank Limited with advance_emi=true and min_loan_amount=25000
            if config.get("name") == "CSB Bank Limited":
                log_test("Test 1: Active bank is CSB Bank Limited", True, "Correct bank")
            else:
                log_test("Test 1: Active bank is CSB Bank Limited", False, 
                        f"Expected 'CSB Bank Limited', got '{config.get('name')}'")
            
            if config.get("advance_emi") == True:
                log_test("Test 1: advance_emi is true", True, "Correct value")
            else:
                log_test("Test 1: advance_emi is true", False, 
                        f"Expected true, got {config.get('advance_emi')}")
            
            if config.get("min_loan_amount") == 25000:
                log_test("Test 1: min_loan_amount is 25000", True, "Correct value")
            else:
                log_test("Test 1: min_loan_amount is 25000", False, 
                        f"Expected 25000, got {config.get('min_loan_amount')}")
        else:
            log_test("Test 1: GET bank-config", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 1: GET bank-config", False, f"Exception: {e}")
    
    # ========================================================================
    # Test 2: POST /api/parent/financing/preview - ADVANCE MODE
    # ========================================================================
    print("\n--- Test 2: POST /api/parent/financing/preview - ADVANCE MODE ---")
    
    # Test 2a: amount=138000, down_payment=50000, tenure=3
    print("\n  Test 2a: amount=138000, down_payment=50000, tenure=3")
    try:
        response = requests.post(
            f"{BASE_URL}/api/parent/financing/preview",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={"amount": 138000, "down_payment": 50000, "tenure": 3},
            timeout=10
        )
        
        if response.status_code == 200:
            preview = response.json()
            log_test("Test 2a: POST preview returns 200", True, f"Response: {json.dumps(preview, indent=2)}")
            
            # Verify advance mode: down_payment IGNORED (forced to 0), financed_amount=138000
            if preview.get("financed_amount") == 138000:
                log_test("Test 2a: financed_amount=138000 (down_payment ignored)", True, 
                        f"Correct: financed_amount={preview.get('financed_amount')}")
            else:
                log_test("Test 2a: financed_amount=138000 (down_payment ignored)", False, 
                        f"Expected 138000, got {preview.get('financed_amount')}")
            
            if preview.get("down_payment") == 0:
                log_test("Test 2a: down_payment=0 (forced in advance mode)", True, 
                        f"Correct: down_payment={preview.get('down_payment')}")
            else:
                log_test("Test 2a: down_payment=0 (forced in advance mode)", False, 
                        f"Expected 0, got {preview.get('down_payment')}")
            
            # Verify emi=46000 (ceil(138000/3))
            expected_emi = 46000
            if preview.get("emi") == expected_emi:
                log_test("Test 2a: emi=46000", True, f"Correct: emi={preview.get('emi')}")
            else:
                log_test("Test 2a: emi=46000", False, 
                        f"Expected {expected_emi}, got {preview.get('emi')}")
            
            # Verify advance_mode=true
            if preview.get("advance_mode") == True:
                log_test("Test 2a: advance_mode=true", True, "Correct")
            else:
                log_test("Test 2a: advance_mode=true", False, 
                        f"Expected true, got {preview.get('advance_mode')}")
            
            # Verify advance_amount=46000 (same as emi)
            if preview.get("advance_amount") == expected_emi:
                log_test("Test 2a: advance_amount=46000", True, 
                        f"Correct: advance_amount={preview.get('advance_amount')}")
            else:
                log_test("Test 2a: advance_amount=46000", False, 
                        f"Expected {expected_emi}, got {preview.get('advance_amount')}")
            
            # Verify amount_payable_now=47628 (advance 46000 + processing_fee 1628)
            # processing_fee = max(499, round(138000*0.01)) * 1.18 = 1380 * 1.18 = 1628.4 -> 1628
            expected_processing_fee = round(max(499, round(138000 * 0.01)) * 1.18)
            expected_amount_payable_now = expected_emi + expected_processing_fee
            
            if preview.get("processing_fee") == expected_processing_fee:
                log_test("Test 2a: processing_fee=1628", True, 
                        f"Correct: processing_fee={preview.get('processing_fee')}")
            else:
                log_test("Test 2a: processing_fee=1628", False, 
                        f"Expected {expected_processing_fee}, got {preview.get('processing_fee')}")
            
            if preview.get("amount_payable_now") == expected_amount_payable_now:
                log_test("Test 2a: amount_payable_now=47628", True, 
                        f"Correct: amount_payable_now={preview.get('amount_payable_now')}")
            else:
                log_test("Test 2a: amount_payable_now=47628", False, 
                        f"Expected {expected_amount_payable_now}, got {preview.get('amount_payable_now')}")
            
            # Verify meets_min=true (138000 >= 25000)
            if preview.get("meets_min") == True:
                log_test("Test 2a: meets_min=true", True, "Correct")
            else:
                log_test("Test 2a: meets_min=true", False, 
                        f"Expected true, got {preview.get('meets_min')}")
            
            if preview.get("min_loan_amount") == 25000:
                log_test("Test 2a: min_loan_amount=25000", True, "Correct")
            else:
                log_test("Test 2a: min_loan_amount=25000", False, 
                        f"Expected 25000, got {preview.get('min_loan_amount')}")
            
            # Verify schedule[0].label == "1st Installment (Advance)"
            schedule = preview.get("schedule", [])
            if len(schedule) > 0 and schedule[0].get("label") == "1st Installment (Advance)":
                log_test("Test 2a: schedule[0].label='1st Installment (Advance)'", True, 
                        f"Correct: {schedule[0].get('label')}")
            else:
                log_test("Test 2a: schedule[0].label='1st Installment (Advance)'", False, 
                        f"Expected '1st Installment (Advance)', got '{schedule[0].get('label') if schedule else 'N/A'}'")
        else:
            log_test("Test 2a: POST preview", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 2a: POST preview", False, f"Exception: {e}")
    
    # Test 2b: amount=20000, down_payment=0, tenure=3 (below min)
    print("\n  Test 2b: amount=20000, down_payment=0, tenure=3 (below min)")
    try:
        response = requests.post(
            f"{BASE_URL}/api/parent/financing/preview",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={"amount": 20000, "down_payment": 0, "tenure": 3},
            timeout=10
        )
        
        if response.status_code == 200:
            preview = response.json()
            log_test("Test 2b: POST preview returns 200", True, f"Response: {json.dumps(preview, indent=2)}")
            
            # Verify financed_amount=20000
            if preview.get("financed_amount") == 20000:
                log_test("Test 2b: financed_amount=20000", True, "Correct")
            else:
                log_test("Test 2b: financed_amount=20000", False, 
                        f"Expected 20000, got {preview.get('financed_amount')}")
            
            # Verify meets_min=false (20000 < 25000)
            if preview.get("meets_min") == False:
                log_test("Test 2b: meets_min=false (below min 25000)", True, "Correct")
            else:
                log_test("Test 2b: meets_min=false (below min 25000)", False, 
                        f"Expected false, got {preview.get('meets_min')}")
        else:
            log_test("Test 2b: POST preview", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 2b: POST preview", False, f"Exception: {e}")
    
    # ========================================================================
    # Test 3: DOWN-PAYMENT MODE test
    # ========================================================================
    print("\n--- Test 3: DOWN-PAYMENT MODE test ---")
    
    # Step 1: Get the active bank id
    print("\n  Step 1: Get active bank id")
    active_bank_id = None
    original_bank_config = None
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            banks = response.json()
            for bank in banks:
                if bank.get("active") == True:
                    active_bank_id = bank.get("id")
                    original_bank_config = bank
                    log_test("Test 3 Step 1: Found active bank", True, 
                            f"id={active_bank_id}, name={bank.get('name')}")
                    break
            
            if not active_bank_id:
                log_test("Test 3 Step 1: Found active bank", False, "No active bank found")
                return
        else:
            log_test("Test 3 Step 1: GET banks", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
            return
    except Exception as e:
        log_test("Test 3 Step 1: GET banks", False, f"Exception: {e}")
        return
    
    # Step 2: Set advance_emi=false
    print("\n  Step 2: Set advance_emi=false")
    try:
        # Prepare update body with all fields from original config
        update_body = {
            "name": original_bank_config.get("name"),
            "active": original_bank_config.get("active"),
            "advance_emi": False,  # Change to false
            "min_loan_amount": original_bank_config.get("min_loan_amount"),
            "location_match_aadhaar": original_bank_config.get("location_match_aadhaar"),
            "name_match_rule": original_bank_config.get("name_match_rule"),
            "income_proof": original_bank_config.get("income_proof"),
            "fund_release": original_bank_config.get("fund_release")
        }
        
        response = requests.put(
            f"{BASE_URL}/api/credit/financing-banks/{active_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            json=update_body,
            timeout=10
        )
        
        if response.status_code == 200:
            updated_bank = response.json()
            if updated_bank.get("advance_emi") == False:
                log_test("Test 3 Step 2: Set advance_emi=false", True, "Successfully updated")
            else:
                log_test("Test 3 Step 2: Set advance_emi=false", False, 
                        f"Expected false, got {updated_bank.get('advance_emi')}")
        else:
            log_test("Test 3 Step 2: Set advance_emi=false", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
            return
    except Exception as e:
        log_test("Test 3 Step 2: Set advance_emi=false", False, f"Exception: {e}")
        return
    
    # Step 3: Test preview with down-payment mode
    print("\n  Step 3: Test preview with down-payment mode")
    try:
        response = requests.post(
            f"{BASE_URL}/api/parent/financing/preview",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={"amount": 138000, "down_payment": 50000, "tenure": 3},
            timeout=10
        )
        
        if response.status_code == 200:
            preview = response.json()
            log_test("Test 3 Step 3: POST preview returns 200", True, f"Response: {json.dumps(preview, indent=2)}")
            
            # Verify advance_mode=false
            if preview.get("advance_mode") == False:
                log_test("Test 3 Step 3: advance_mode=false", True, "Correct")
            else:
                log_test("Test 3 Step 3: advance_mode=false", False, 
                        f"Expected false, got {preview.get('advance_mode')}")
            
            # Verify down_payment=50000 (NOT ignored)
            if preview.get("down_payment") == 50000:
                log_test("Test 3 Step 3: down_payment=50000", True, "Correct")
            else:
                log_test("Test 3 Step 3: down_payment=50000", False, 
                        f"Expected 50000, got {preview.get('down_payment')}")
            
            # Verify financed_amount=88000 (138000 - 50000)
            expected_financed = 88000
            if preview.get("financed_amount") == expected_financed:
                log_test("Test 3 Step 3: financed_amount=88000", True, "Correct")
            else:
                log_test("Test 3 Step 3: financed_amount=88000", False, 
                        f"Expected {expected_financed}, got {preview.get('financed_amount')}")
            
            # Verify meets_min=true (88000 >= 25000)
            if preview.get("meets_min") == True:
                log_test("Test 3 Step 3: meets_min=true", True, "Correct")
            else:
                log_test("Test 3 Step 3: meets_min=true", False, 
                        f"Expected true, got {preview.get('meets_min')}")
            
            # Verify amount_payable_now = 50000 + processing_fee
            # processing_fee = max(499, round(88000*0.01)) * 1.18 = 880 * 1.18 = 1038.4 -> 1038
            expected_processing_fee = round(max(499, round(88000 * 0.01)) * 1.18)
            expected_amount_payable_now = 50000 + expected_processing_fee
            
            if preview.get("amount_payable_now") == expected_amount_payable_now:
                log_test("Test 3 Step 3: amount_payable_now=50000+processing_fee", True, 
                        f"Correct: amount_payable_now={preview.get('amount_payable_now')}")
            else:
                log_test("Test 3 Step 3: amount_payable_now=50000+processing_fee", False, 
                        f"Expected {expected_amount_payable_now}, got {preview.get('amount_payable_now')}")
        else:
            log_test("Test 3 Step 3: POST preview", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 3 Step 3: POST preview", False, f"Exception: {e}")
    
    # Step 4: RESTORE advance_emi=true
    print("\n  Step 4: RESTORE advance_emi=true")
    try:
        restore_body = {
            "name": original_bank_config.get("name"),
            "active": original_bank_config.get("active"),
            "advance_emi": True,  # Restore to true
            "min_loan_amount": original_bank_config.get("min_loan_amount"),
            "location_match_aadhaar": original_bank_config.get("location_match_aadhaar"),
            "name_match_rule": original_bank_config.get("name_match_rule"),
            "income_proof": original_bank_config.get("income_proof"),
            "fund_release": original_bank_config.get("fund_release")
        }
        
        response = requests.put(
            f"{BASE_URL}/api/credit/financing-banks/{active_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            json=restore_body,
            timeout=10
        )
        
        if response.status_code == 200:
            restored_bank = response.json()
            if restored_bank.get("advance_emi") == True:
                log_test("Test 3 Step 4: RESTORE advance_emi=true", True, "Successfully restored")
            else:
                log_test("Test 3 Step 4: RESTORE advance_emi=true", False, 
                        f"Expected true, got {restored_bank.get('advance_emi')}")
        else:
            log_test("Test 3 Step 4: RESTORE advance_emi=true", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 3 Step 4: RESTORE advance_emi=true", False, f"Exception: {e}")
    
    # ========================================================================
    # Test 4: POST /api/parent/pay-financing
    # ========================================================================
    print("\n--- Test 4: POST /api/parent/pay-financing ---")
    
    # Step 1: Get parent's students and pending fees
    print("\n  Step 4 Step 1: Get parent's students and pending fees")
    student_id = None
    fee_head_ids = []
    total_fee_amount = 0
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/parent/fees",
            headers={"Authorization": f"Bearer {parent_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            fees_data = response.json()
            log_test("Test 4 Step 1: GET /api/parent/fees returns 200", True, 
                    f"Found {len(fees_data)} students")
            
            # Find a student with pending fees
            for student_fees in fees_data:
                student_id = student_fees.get("student_id")
                pending_items = [item for item in student_fees.get("items", []) 
                               if not item.get("paid")]
                
                if pending_items:
                    # Take first 1-2 pending items
                    selected_items = pending_items[:2]
                    fee_head_ids = [item.get("fee_head_id") for item in selected_items]
                    total_fee_amount = sum(item.get("amount", 0) for item in selected_items)
                    
                    log_test("Test 4 Step 1: Found student with pending fees", True, 
                            f"student_id={student_id}, fee_head_ids={fee_head_ids}, total={total_fee_amount}")
                    break
            
            if not student_id or not fee_head_ids:
                log_test("Test 4 Step 1: Found student with pending fees", False, 
                        "No students with pending fees found")
                return
        else:
            log_test("Test 4 Step 1: GET /api/parent/fees", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
            return
    except Exception as e:
        log_test("Test 4 Step 1: GET /api/parent/fees", False, f"Exception: {e}")
        return
    
    # Step 2: Test pay-financing with advance_emi=true (restored default)
    print("\n  Step 4 Step 2: Test pay-financing with advance_emi=true")
    try:
        response = requests.post(
            f"{BASE_URL}/api/parent/pay-financing",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={
                "student_id": student_id,
                "fee_head_ids": fee_head_ids,
                "tenure": 3,
                "down_payment": 0
            },
            timeout=10
        )
        
        if response.status_code == 200:
            payment = response.json()
            log_test("Test 4 Step 2: POST pay-financing returns 200", True, 
                    f"Response: {json.dumps(payment, indent=2)[:500]}")
            
            # Verify financing=true
            if payment.get("financing") == True:
                log_test("Test 4 Step 2: financing=true", True, "Correct")
            else:
                log_test("Test 4 Step 2: financing=true", False, 
                        f"Expected true, got {payment.get('financing')}")
            
            # Verify advance_mode=true
            if payment.get("advance_mode") == True:
                log_test("Test 4 Step 2: advance_mode=true", True, "Correct")
            else:
                log_test("Test 4 Step 2: advance_mode=true", False, 
                        f"Expected true, got {payment.get('advance_mode')}")
            
            # Verify advance_amount=emi
            emi = payment.get("emi")
            advance_amount = payment.get("advance_amount")
            if advance_amount == emi:
                log_test("Test 4 Step 2: advance_amount=emi", True, 
                        f"Correct: advance_amount={advance_amount}, emi={emi}")
            else:
                log_test("Test 4 Step 2: advance_amount=emi", False, 
                        f"Expected advance_amount={emi}, got {advance_amount}")
            
            # Verify amount_payable_now is set
            if payment.get("amount_payable_now") is not None:
                log_test("Test 4 Step 2: amount_payable_now is set", True, 
                        f"amount_payable_now={payment.get('amount_payable_now')}")
            else:
                log_test("Test 4 Step 2: amount_payable_now is set", False, 
                        "amount_payable_now is None")
            
            # Verify bank_name="CSB Bank Limited"
            if payment.get("bank_name") == "CSB Bank Limited":
                log_test("Test 4 Step 2: bank_name='CSB Bank Limited'", True, "Correct")
            else:
                log_test("Test 4 Step 2: bank_name='CSB Bank Limited'", False, 
                        f"Expected 'CSB Bank Limited', got '{payment.get('bank_name')}'")
            
            # Verify schedule exists
            schedule = payment.get("schedule", [])
            if len(schedule) > 0:
                log_test("Test 4 Step 2: schedule exists", True, 
                        f"schedule length={len(schedule)}")
            else:
                log_test("Test 4 Step 2: schedule exists", False, "schedule is empty")
            
            # Verify agreement_id exists
            agreement_id = payment.get("agreement_id")
            if agreement_id and agreement_id.startswith("BLP-AGR-"):
                log_test("Test 4 Step 2: agreement_id exists", True, 
                        f"agreement_id={agreement_id}")
            else:
                log_test("Test 4 Step 2: agreement_id exists", False, 
                        f"Expected 'BLP-AGR-*', got '{agreement_id}'")
        else:
            log_test("Test 4 Step 2: POST pay-financing", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 4 Step 2: POST pay-financing", False, f"Exception: {e}")
    
    # Step 3: Test minimum enforcement (temporarily raise min_loan_amount)
    print("\n  Step 4 Step 3: Test minimum enforcement")
    
    # Get current min_loan_amount
    current_min_loan = original_bank_config.get("min_loan_amount", 25000)
    
    # Temporarily raise min_loan_amount above the total fee amount
    temp_min_loan = int(total_fee_amount) + 10000
    
    print(f"    Temporarily raising min_loan_amount to {temp_min_loan} (above total {total_fee_amount})")
    try:
        temp_update_body = {
            "name": original_bank_config.get("name"),
            "active": original_bank_config.get("active"),
            "advance_emi": True,
            "min_loan_amount": temp_min_loan,
            "location_match_aadhaar": original_bank_config.get("location_match_aadhaar"),
            "name_match_rule": original_bank_config.get("name_match_rule"),
            "income_proof": original_bank_config.get("income_proof"),
            "fund_release": original_bank_config.get("fund_release")
        }
        
        response = requests.put(
            f"{BASE_URL}/api/credit/financing-banks/{active_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            json=temp_update_body,
            timeout=10
        )
        
        if response.status_code == 200:
            log_test("Test 4 Step 3: Temporarily raised min_loan_amount", True, 
                    f"Set to {temp_min_loan}")
            
            # Now try to pay-financing with amount below min
            # First, get fresh pending fees (since we just paid some)
            response = requests.get(
                f"{BASE_URL}/api/parent/fees",
                headers={"Authorization": f"Bearer {parent_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                fees_data = response.json()
                # Find a student with pending fees
                test_student_id = None
                test_fee_head_ids = []
                
                for student_fees in fees_data:
                    test_student_id = student_fees.get("student_id")
                    pending_items = [item for item in student_fees.get("items", []) 
                                   if not item.get("paid")]
                    
                    if pending_items:
                        # Take just 1 item to keep amount low
                        selected_items = pending_items[:1]
                        test_fee_head_ids = [item.get("fee_head_id") for item in selected_items]
                        test_total = sum(item.get("amount", 0) for item in selected_items)
                        
                        # Only proceed if this amount is below our temp min
                        if test_total < temp_min_loan:
                            log_test("Test 4 Step 3: Found fee below temp min", True, 
                                    f"fee_total={test_total} < min={temp_min_loan}")
                            
                            # Try to pay-financing (should fail with 400)
                            response = requests.post(
                                f"{BASE_URL}/api/parent/pay-financing",
                                headers={"Authorization": f"Bearer {parent_token}"},
                                json={
                                    "student_id": test_student_id,
                                    "fee_head_ids": test_fee_head_ids,
                                    "tenure": 3,
                                    "down_payment": 0
                                },
                                timeout=10
                            )
                            
                            if response.status_code == 400:
                                error_detail = response.json().get("detail", "")
                                if "minimum loan amount" in error_detail.lower():
                                    log_test("Test 4 Step 3: pay-financing returns 400 for below min", True, 
                                            f"Error: {error_detail}")
                                else:
                                    log_test("Test 4 Step 3: pay-financing returns 400 for below min", False, 
                                            f"Expected 'minimum loan amount' in error, got: {error_detail}")
                            else:
                                log_test("Test 4 Step 3: pay-financing returns 400 for below min", False, 
                                        f"Expected 400, got {response.status_code}")
                            break
                        else:
                            log_test("Test 4 Step 3: Found fee below temp min", False, 
                                    f"All fees >= temp min (fee_total={test_total} >= min={temp_min_loan})")
                            break
        else:
            log_test("Test 4 Step 3: Temporarily raised min_loan_amount", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("Test 4 Step 3: Test minimum enforcement", False, f"Exception: {e}")
    
    # Step 4: RESTORE min_loan_amount to 25000
    print("\n  Step 4 Step 4: RESTORE min_loan_amount to 25000")
    try:
        final_restore_body = {
            "name": original_bank_config.get("name"),
            "active": original_bank_config.get("active"),
            "advance_emi": True,
            "min_loan_amount": 25000,
            "location_match_aadhaar": original_bank_config.get("location_match_aadhaar"),
            "name_match_rule": original_bank_config.get("name_match_rule"),
            "income_proof": original_bank_config.get("income_proof"),
            "fund_release": original_bank_config.get("fund_release")
        }
        
        response = requests.put(
            f"{BASE_URL}/api/credit/financing-banks/{active_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            json=final_restore_body,
            timeout=10
        )
        
        if response.status_code == 200:
            final_bank = response.json()
            if final_bank.get("min_loan_amount") == 25000 and final_bank.get("advance_emi") == True:
                log_test("Test 4 Step 4: RESTORE to advance_emi=true, min_loan_amount=25000", True, 
                        "Successfully restored to defaults")
            else:
                log_test("Test 4 Step 4: RESTORE to advance_emi=true, min_loan_amount=25000", False, 
                        f"advance_emi={final_bank.get('advance_emi')}, min_loan_amount={final_bank.get('min_loan_amount')}")
        else:
            log_test("Test 4 Step 4: RESTORE min_loan_amount", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Test 4 Step 4: RESTORE min_loan_amount", False, f"Exception: {e}")
    
    # ========================================================================
    # Final verification: Verify CSB Bank config is restored
    # ========================================================================
    print("\n--- Final verification: Verify CSB Bank config is restored ---")
    try:
        response = requests.get(
            f"{BASE_URL}/api/parent/financing/bank-config",
            headers={"Authorization": f"Bearer {parent_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            config = response.json()
            if (config.get("name") == "CSB Bank Limited" and 
                config.get("advance_emi") == True and 
                config.get("min_loan_amount") == 25000):
                log_test("Final verification: CSB Bank config restored", True, 
                        f"name={config.get('name')}, advance_emi={config.get('advance_emi')}, min_loan_amount={config.get('min_loan_amount')}")
            else:
                log_test("Final verification: CSB Bank config restored", False, 
                        f"Expected CSB Bank Limited with advance_emi=true and min_loan_amount=25000, got: {json.dumps(config)}")
        else:
            log_test("Final verification: GET bank-config", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("Final verification: GET bank-config", False, f"Exception: {e}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed: {test_results['passed']}")
    print(f"❌ Failed: {test_results['failed']}")
    print(f"📊 Total: {test_results['passed'] + test_results['failed']}")
    
    if test_results['failed'] > 0:
        print("\n❌ FAILED TESTS:")
        for detail in test_results['details']:
            if not detail['passed']:
                print(f"  - {detail['name']}")
                if detail['details']:
                    print(f"    {detail['details']}")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    try:
        test_phase2_parent_financing()
        print_summary()
        
        # Exit with appropriate code
        sys.exit(0 if test_results['failed'] == 0 else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
