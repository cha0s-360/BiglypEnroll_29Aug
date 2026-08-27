#!/usr/bin/env python3
"""
BiglypEnroll Backend API Testing Suite
Tests Financing Banks CRUD endpoints in backend/credit.py
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
            token = data.get("token")  # Backend returns "token" not "access_token"
            print(f"✅ Logged in as {email}")
            return token
        else:
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error for {email}: {e}")
        return None

def test_financing_banks_crud():
    """Test Financing Banks CRUD endpoints"""
    print("\n" + "="*80)
    print("TESTING: Financing Banks CRUD Endpoints")
    print("="*80 + "\n")
    
    # ========================================================================
    # Scenario 1: Login as creditops and GET list
    # ========================================================================
    print("\n--- Scenario 1: Login as creditops and GET list ---")
    creditops_token = login("creditops@biglyp.com", "creditops123")
    if not creditops_token:
        log_test("Scenario 1: Login as creditops", False, "Login failed")
        return
    
    log_test("Scenario 1: Login as creditops", True, "Successfully logged in")
    
    # GET list of financing banks
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            banks = response.json()
            log_test("Scenario 1: GET list returns 200", True, f"Returned {len(banks)} banks")
            
            # Check for seeded "CSB Bank Limited"
            csb_bank = next((b for b in banks if b.get("name") == "CSB Bank Limited"), None)
            if csb_bank:
                # Verify full nested config
                has_all_fields = all([
                    "id" in csb_bank,
                    "name" in csb_bank,
                    "active" in csb_bank,
                    "advance_emi" in csb_bank,
                    "min_loan_amount" in csb_bank,
                    "location_match_aadhaar" in csb_bank,
                    "name_match_rule" in csb_bank,
                    "income_proof" in csb_bank,
                    "fund_release" in csb_bank,
                    "created_at" in csb_bank,
                    "updated_at" in csb_bank
                ])
                
                # Check nested income_proof structure
                income_proof = csb_bank.get("income_proof", {})
                has_income_proof_fields = all([
                    "cibil_threshold" in income_proof,
                    "income_threshold" in income_proof,
                    "required_matrix" in income_proof
                ])
                
                # Check nested required_matrix
                required_matrix = income_proof.get("required_matrix", {})
                has_matrix_fields = all([
                    "high_cibil_high_income" in required_matrix,
                    "high_cibil_low_income" in required_matrix,
                    "low_cibil_high_income" in required_matrix,
                    "low_cibil_low_income" in required_matrix
                ])
                
                # Check nested fund_release
                fund_release = csb_bank.get("fund_release", {})
                has_fund_release_fields = all([
                    "multi_account_allowed" in fund_release,
                    "vendor_external_allowed" in fund_release
                ])
                
                # Check no Mongo _id leaks
                has_no_mongo_id = "_id" not in csb_bank
                
                if has_all_fields and has_income_proof_fields and has_matrix_fields and has_fund_release_fields and has_no_mongo_id:
                    log_test("Scenario 1: CSB Bank Limited found with full nested config", True, 
                            f"All fields present, no _id leak")
                else:
                    missing = []
                    if not has_all_fields:
                        missing.append("top-level fields")
                    if not has_income_proof_fields:
                        missing.append("income_proof fields")
                    if not has_matrix_fields:
                        missing.append("required_matrix fields")
                    if not has_fund_release_fields:
                        missing.append("fund_release fields")
                    if not has_no_mongo_id:
                        missing.append("_id leaked")
                    log_test("Scenario 1: CSB Bank Limited config incomplete", False, 
                            f"Missing: {', '.join(missing)}")
            else:
                log_test("Scenario 1: CSB Bank Limited not found", False, "Seeded bank missing")
        else:
            log_test("Scenario 1: GET list returns 200", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Scenario 1: GET list", False, f"Exception: {e}")
    
    # ========================================================================
    # Scenario 2: POST create a new bank with ALL fields
    # ========================================================================
    print("\n--- Scenario 2: POST create a new bank with ALL fields ---")
    new_bank_data = {
        "name": "Test Bank Ltd",
        "active": True,
        "advance_emi": True,
        "min_loan_amount": 30000,
        "location_match_aadhaar": True,
        "name_match_rule": "pan",
        "income_proof": {
            "cibil_threshold": 760,
            "income_threshold": 800000,
            "required_matrix": {
                "high_cibil_high_income": False,
                "high_cibil_low_income": True,
                "low_cibil_high_income": True,
                "low_cibil_low_income": True
            }
        },
        "fund_release": {
            "multi_account_allowed": True,
            "vendor_external_allowed": False
        }
    }
    
    created_bank_id = None
    try:
        response = requests.post(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {creditops_token}"},
            json=new_bank_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            created_bank = response.json()
            created_bank_id = created_bank.get("id")
            
            # Verify response has id (UUID)
            if created_bank_id and len(created_bank_id) == 36:
                log_test("Scenario 2: POST returns id (UUID)", True, f"id: {created_bank_id}")
            else:
                log_test("Scenario 2: POST returns id (UUID)", False, f"Invalid id: {created_bank_id}")
            
            # Verify all fields echoed back
            fields_match = all([
                created_bank.get("name") == new_bank_data["name"],
                created_bank.get("active") == new_bank_data["active"],
                created_bank.get("advance_emi") == new_bank_data["advance_emi"],
                created_bank.get("min_loan_amount") == new_bank_data["min_loan_amount"],
                created_bank.get("location_match_aadhaar") == new_bank_data["location_match_aadhaar"],
                created_bank.get("name_match_rule") == new_bank_data["name_match_rule"]
            ])
            
            # Verify nested income_proof
            income_proof = created_bank.get("income_proof", {})
            income_proof_match = all([
                income_proof.get("cibil_threshold") == new_bank_data["income_proof"]["cibil_threshold"],
                income_proof.get("income_threshold") == new_bank_data["income_proof"]["income_threshold"]
            ])
            
            # Verify nested required_matrix
            required_matrix = income_proof.get("required_matrix", {})
            matrix_match = all([
                required_matrix.get("high_cibil_high_income") == new_bank_data["income_proof"]["required_matrix"]["high_cibil_high_income"],
                required_matrix.get("high_cibil_low_income") == new_bank_data["income_proof"]["required_matrix"]["high_cibil_low_income"],
                required_matrix.get("low_cibil_high_income") == new_bank_data["income_proof"]["required_matrix"]["low_cibil_high_income"],
                required_matrix.get("low_cibil_low_income") == new_bank_data["income_proof"]["required_matrix"]["low_cibil_low_income"]
            ])
            
            # Verify nested fund_release
            fund_release = created_bank.get("fund_release", {})
            fund_release_match = all([
                fund_release.get("multi_account_allowed") == new_bank_data["fund_release"]["multi_account_allowed"],
                fund_release.get("vendor_external_allowed") == new_bank_data["fund_release"]["vendor_external_allowed"]
            ])
            
            # Verify no Mongo _id leak
            no_mongo_id = "_id" not in created_bank
            
            if fields_match and income_proof_match and matrix_match and fund_release_match and no_mongo_id:
                log_test("Scenario 2: POST echoes ALL fields correctly", True, 
                        "All fields including nested income_proof.required_matrix and fund_release match")
            else:
                issues = []
                if not fields_match:
                    issues.append("top-level fields mismatch")
                if not income_proof_match:
                    issues.append("income_proof mismatch")
                if not matrix_match:
                    issues.append("required_matrix mismatch")
                if not fund_release_match:
                    issues.append("fund_release mismatch")
                if not no_mongo_id:
                    issues.append("_id leaked")
                log_test("Scenario 2: POST echoes ALL fields correctly", False, 
                        f"Issues: {', '.join(issues)}")
        else:
            log_test("Scenario 2: POST create bank", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Scenario 2: POST create bank", False, f"Exception: {e}")
    
    if not created_bank_id:
        print("\n⚠️  Cannot continue with scenarios 3-5 without created bank id")
        return
    
    # ========================================================================
    # Scenario 3: GET /api/credit/financing-banks/{id} for the created bank
    # ========================================================================
    print("\n--- Scenario 3: GET by id for the created bank ---")
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks/{created_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            bank = response.json()
            
            # Verify full config identical to what was saved
            config_match = all([
                bank.get("id") == created_bank_id,
                bank.get("name") == new_bank_data["name"],
                bank.get("active") == new_bank_data["active"],
                bank.get("advance_emi") == new_bank_data["advance_emi"],
                bank.get("min_loan_amount") == new_bank_data["min_loan_amount"],
                bank.get("location_match_aadhaar") == new_bank_data["location_match_aadhaar"],
                bank.get("name_match_rule") == new_bank_data["name_match_rule"]
            ])
            
            # Verify nested structures
            income_proof = bank.get("income_proof", {})
            required_matrix = income_proof.get("required_matrix", {})
            fund_release = bank.get("fund_release", {})
            
            nested_match = all([
                income_proof.get("cibil_threshold") == new_bank_data["income_proof"]["cibil_threshold"],
                income_proof.get("income_threshold") == new_bank_data["income_proof"]["income_threshold"],
                required_matrix.get("high_cibil_high_income") == new_bank_data["income_proof"]["required_matrix"]["high_cibil_high_income"],
                required_matrix.get("high_cibil_low_income") == new_bank_data["income_proof"]["required_matrix"]["high_cibil_low_income"],
                required_matrix.get("low_cibil_high_income") == new_bank_data["income_proof"]["required_matrix"]["low_cibil_high_income"],
                required_matrix.get("low_cibil_low_income") == new_bank_data["income_proof"]["required_matrix"]["low_cibil_low_income"],
                fund_release.get("multi_account_allowed") == new_bank_data["fund_release"]["multi_account_allowed"],
                fund_release.get("vendor_external_allowed") == new_bank_data["fund_release"]["vendor_external_allowed"]
            ])
            
            if config_match and nested_match:
                log_test("Scenario 3: GET by id returns full config", True, 
                        "Config identical to what was saved")
            else:
                log_test("Scenario 3: GET by id returns full config", False, 
                        "Config mismatch")
        else:
            log_test("Scenario 3: GET by id", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Scenario 3: GET by id", False, f"Exception: {e}")
    
    # ========================================================================
    # Scenario 4: PUT update the created bank
    # ========================================================================
    print("\n--- Scenario 4: PUT update the created bank ---")
    update_data = {
        "name": "Test Bank Renamed",
        "active": True,
        "advance_emi": False,  # changed
        "min_loan_amount": 50000,  # changed
        "location_match_aadhaar": True,
        "name_match_rule": "aadhaar",  # changed
        "income_proof": {
            "cibil_threshold": 760,
            "income_threshold": 800000,
            "required_matrix": {
                "high_cibil_high_income": True,  # flipped
                "high_cibil_low_income": True,
                "low_cibil_high_income": True,
                "low_cibil_low_income": True
            }
        },
        "fund_release": {
            "multi_account_allowed": True,
            "vendor_external_allowed": True  # changed
        }
    }
    
    original_updated_at = None
    try:
        # Get original updated_at
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks/{created_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        if response.status_code == 200:
            original_updated_at = response.json().get("updated_at")
        
        # Update
        response = requests.put(
            f"{BASE_URL}/api/credit/financing-banks/{created_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            json=update_data,
            timeout=10
        )
        
        if response.status_code == 200:
            updated_bank = response.json()
            
            # Verify changes persisted
            changes_match = all([
                updated_bank.get("name") == "Test Bank Renamed",
                updated_bank.get("advance_emi") == False,
                updated_bank.get("min_loan_amount") == 50000,
                updated_bank.get("name_match_rule") == "aadhaar"
            ])
            
            # Verify nested changes
            income_proof = updated_bank.get("income_proof", {})
            required_matrix = income_proof.get("required_matrix", {})
            fund_release = updated_bank.get("fund_release", {})
            
            nested_changes_match = all([
                required_matrix.get("high_cibil_high_income") == True,
                fund_release.get("vendor_external_allowed") == True
            ])
            
            # Verify updated_at changed
            new_updated_at = updated_bank.get("updated_at")
            updated_at_changed = new_updated_at != original_updated_at
            
            if changes_match and nested_changes_match:
                log_test("Scenario 4: PUT persists changes", True, 
                        "All changes including nested fields persisted")
            else:
                log_test("Scenario 4: PUT persists changes", False, 
                        "Some changes not persisted")
            
            if updated_at_changed:
                log_test("Scenario 4: PUT updates updated_at", True, 
                        f"Changed from {original_updated_at} to {new_updated_at}")
            else:
                log_test("Scenario 4: PUT updates updated_at", False, 
                        "updated_at did not change")
        else:
            log_test("Scenario 4: PUT update bank", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
    except Exception as e:
        log_test("Scenario 4: PUT update bank", False, f"Exception: {e}")
    
    # ========================================================================
    # Scenario 5: DELETE, GET (404), DELETE again (404)
    # ========================================================================
    print("\n--- Scenario 5: DELETE, GET (404), DELETE again (404) ---")
    try:
        # DELETE
        response = requests.delete(
            f"{BASE_URL}/api/credit/financing-banks/{created_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok") == True:
                log_test("Scenario 5: DELETE returns 200 with ok:true", True, 
                        f"Response: {result}")
            else:
                log_test("Scenario 5: DELETE returns 200 with ok:true", False, 
                        f"Response: {result}")
        else:
            log_test("Scenario 5: DELETE", False, 
                    f"Status: {response.status_code}, Body: {response.text[:200]}")
        
        # GET by deleted id (should be 404)
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks/{created_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 404:
            log_test("Scenario 5: GET deleted id returns 404", True, 
                    "Bank not found after deletion")
        else:
            log_test("Scenario 5: GET deleted id returns 404", False, 
                    f"Status: {response.status_code}, expected 404")
        
        # DELETE again (should be 404)
        response = requests.delete(
            f"{BASE_URL}/api/credit/financing-banks/{created_bank_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 404:
            log_test("Scenario 5: DELETE again returns 404", True, 
                    "Cannot delete already deleted bank")
        else:
            log_test("Scenario 5: DELETE again returns 404", False, 
                    f"Status: {response.status_code}, expected 404")
    except Exception as e:
        log_test("Scenario 5: DELETE operations", False, f"Exception: {e}")
    
    # ========================================================================
    # Scenario 6: GET a random non-existent id (404)
    # ========================================================================
    print("\n--- Scenario 6: GET a random non-existent id (404) ---")
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks/{fake_id}",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 404:
            log_test("Scenario 6: GET non-existent id returns 404", True, 
                    f"Correctly returned 404 for fake id")
        else:
            log_test("Scenario 6: GET non-existent id returns 404", False, 
                    f"Status: {response.status_code}, expected 404")
    except Exception as e:
        log_test("Scenario 6: GET non-existent id", False, f"Exception: {e}")
    
    # ========================================================================
    # Scenario 7: Role guard - login as parent
    # ========================================================================
    print("\n--- Scenario 7: Role guard - login as parent ---")
    parent_token = login("parent@biglyp.com", "parent123")
    if not parent_token:
        log_test("Scenario 7: Login as parent", False, "Login failed")
        return
    
    log_test("Scenario 7: Login as parent", True, "Successfully logged in")
    
    # Get a valid bank id for testing GET by id
    valid_bank_id = None
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        if response.status_code == 200:
            banks = response.json()
            if banks:
                valid_bank_id = banks[0].get("id")
    except:
        pass
    
    # Test GET list (should be 403)
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {parent_token}"},
            timeout=10
        )
        
        if response.status_code == 403:
            log_test("Scenario 7: Parent GET list returns 403", True, 
                    "Non-admin blocked from listing banks")
        else:
            log_test("Scenario 7: Parent GET list returns 403", False, 
                    f"Status: {response.status_code}, expected 403")
    except Exception as e:
        log_test("Scenario 7: Parent GET list", False, f"Exception: {e}")
    
    # Test POST create (should be 403)
    try:
        response = requests.post(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={"name": "Test Bank"},
            timeout=10
        )
        
        if response.status_code == 403:
            log_test("Scenario 7: Parent POST create returns 403", True, 
                    "Non-admin blocked from creating banks")
        else:
            log_test("Scenario 7: Parent POST create returns 403", False, 
                    f"Status: {response.status_code}, expected 403")
    except Exception as e:
        log_test("Scenario 7: Parent POST create", False, f"Exception: {e}")
    
    # Test PUT update (should be 403)
    if valid_bank_id:
        try:
            response = requests.put(
                f"{BASE_URL}/api/credit/financing-banks/{valid_bank_id}",
                headers={"Authorization": f"Bearer {parent_token}"},
                json={"name": "Test Bank Updated"},
                timeout=10
            )
            
            if response.status_code == 403:
                log_test("Scenario 7: Parent PUT update returns 403", True, 
                        "Non-admin blocked from updating banks")
            else:
                log_test("Scenario 7: Parent PUT update returns 403", False, 
                        f"Status: {response.status_code}, expected 403")
        except Exception as e:
            log_test("Scenario 7: Parent PUT update", False, f"Exception: {e}")
    
    # Test DELETE (should be 403)
    if valid_bank_id:
        try:
            response = requests.delete(
                f"{BASE_URL}/api/credit/financing-banks/{valid_bank_id}",
                headers={"Authorization": f"Bearer {parent_token}"},
                timeout=10
            )
            
            if response.status_code == 403:
                log_test("Scenario 7: Parent DELETE returns 403", True, 
                        "Non-admin blocked from deleting banks")
            else:
                log_test("Scenario 7: Parent DELETE returns 403", False, 
                        f"Status: {response.status_code}, expected 403")
        except Exception as e:
            log_test("Scenario 7: Parent DELETE", False, f"Exception: {e}")
    
    # Test GET by id (should be 200 - any authenticated user allowed)
    if valid_bank_id:
        try:
            response = requests.get(
                f"{BASE_URL}/api/credit/financing-banks/{valid_bank_id}",
                headers={"Authorization": f"Bearer {parent_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                log_test("Scenario 7: Parent GET by id returns 200", True, 
                        "Authenticated non-admin allowed to lookup bank config")
            else:
                log_test("Scenario 7: Parent GET by id returns 200", False, 
                        f"Status: {response.status_code}, expected 200")
        except Exception as e:
            log_test("Scenario 7: Parent GET by id", False, f"Exception: {e}")
    
    # ========================================================================
    # Scenario 8: Unauthenticated (no token) on any endpoint (401)
    # ========================================================================
    print("\n--- Scenario 8: Unauthenticated (no token) on any endpoint (401) ---")
    
    # Test GET list without token
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks",
            timeout=10
        )
        
        if response.status_code == 401:
            log_test("Scenario 8: Unauthenticated GET list returns 401", True, 
                    "No token rejected")
        else:
            log_test("Scenario 8: Unauthenticated GET list returns 401", False, 
                    f"Status: {response.status_code}, expected 401")
    except Exception as e:
        log_test("Scenario 8: Unauthenticated GET list", False, f"Exception: {e}")
    
    # Test POST create without token
    try:
        response = requests.post(
            f"{BASE_URL}/api/credit/financing-banks",
            json={"name": "Test Bank"},
            timeout=10
        )
        
        if response.status_code == 401:
            log_test("Scenario 8: Unauthenticated POST create returns 401", True, 
                    "No token rejected")
        else:
            log_test("Scenario 8: Unauthenticated POST create returns 401", False, 
                    f"Status: {response.status_code}, expected 401")
    except Exception as e:
        log_test("Scenario 8: Unauthenticated POST create", False, f"Exception: {e}")
    
    # Test GET by id without token
    if valid_bank_id:
        try:
            response = requests.get(
                f"{BASE_URL}/api/credit/financing-banks/{valid_bank_id}",
                timeout=10
            )
            
            if response.status_code == 401:
                log_test("Scenario 8: Unauthenticated GET by id returns 401", True, 
                        "No token rejected")
            else:
                log_test("Scenario 8: Unauthenticated GET by id returns 401", False, 
                        f"Status: {response.status_code}, expected 401")
        except Exception as e:
            log_test("Scenario 8: Unauthenticated GET by id", False, f"Exception: {e}")
    
    # Test PUT update without token
    if valid_bank_id:
        try:
            response = requests.put(
                f"{BASE_URL}/api/credit/financing-banks/{valid_bank_id}",
                json={"name": "Test Bank Updated"},
                timeout=10
            )
            
            if response.status_code == 401:
                log_test("Scenario 8: Unauthenticated PUT update returns 401", True, 
                        "No token rejected")
            else:
                log_test("Scenario 8: Unauthenticated PUT update returns 401", False, 
                        f"Status: {response.status_code}, expected 401")
        except Exception as e:
            log_test("Scenario 8: Unauthenticated PUT update", False, f"Exception: {e}")
    
    # Test DELETE without token
    if valid_bank_id:
        try:
            response = requests.delete(
                f"{BASE_URL}/api/credit/financing-banks/{valid_bank_id}",
                timeout=10
            )
            
            if response.status_code == 401:
                log_test("Scenario 8: Unauthenticated DELETE returns 401", True, 
                        "No token rejected")
            else:
                log_test("Scenario 8: Unauthenticated DELETE returns 401", False, 
                        f"Status: {response.status_code}, expected 401")
        except Exception as e:
            log_test("Scenario 8: Unauthenticated DELETE", False, f"Exception: {e}")
    
    # ========================================================================
    # Final check: Verify CSB Bank Limited still present
    # ========================================================================
    print("\n--- Final check: Verify CSB Bank Limited still present ---")
    try:
        response = requests.get(
            f"{BASE_URL}/api/credit/financing-banks",
            headers={"Authorization": f"Bearer {creditops_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            banks = response.json()
            csb_bank = next((b for b in banks if b.get("name") == "CSB Bank Limited"), None)
            if csb_bank:
                log_test("Final check: CSB Bank Limited still present", True, 
                        "Default seeded bank intact")
            else:
                log_test("Final check: CSB Bank Limited still present", False, 
                        "Default seeded bank missing")
        else:
            log_test("Final check: CSB Bank Limited check", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("Final check: CSB Bank Limited check", False, f"Exception: {e}")

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
        test_financing_banks_crud()
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
