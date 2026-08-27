"""
Backend API Testing for School↔Bank Financing Management
Tests /api/credit/dummy-banks and /api/credit/fin-schools CRUD endpoints
"""
import requests
import json
from typing import Dict, Any, List

# Base URL from frontend/.env
BASE_URL = "https://github-preview-63.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@biglyp.com"
ADMIN_PASSWORD = "admin123"
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"

# Global variables to store tokens and created resources
admin_token = None
parent_token = None
created_school_ids = []


def login(email: str, password: str) -> str:
    """Login and return Bearer token"""
    url = f"{BASE_URL}/auth/login"
    response = requests.post(url, json={"email": email, "password": password})
    print(f"Login {email}: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        token = data.get("token")
        print(f"  Token received: {token[:20]}..." if token else "  No token in response")
        return token
    else:
        print(f"  Login failed: {response.text}")
        return None


def test_1_dummy_banks_authenticated():
    """Test 1: GET /api/credit/dummy-banks (any authenticated) returns hardcoded list of 10 banks"""
    print("\n=== Test 1: GET /api/credit/dummy-banks (authenticated) ===")
    
    url = f"{BASE_URL}/credit/dummy-banks"
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    banks = response.json()
    print(f"Banks returned: {len(banks)}")
    assert len(banks) == 10, f"Expected 10 banks, got {len(banks)}"
    
    # Check expected bank IDs
    expected_ids = ["hdfc", "icici", "axis", "sbi", "kotak", "csb", "idfc", "yes", "federal", "bajaj"]
    actual_ids = [b["id"] for b in banks]
    print(f"Bank IDs: {actual_ids}")
    
    for expected_id in expected_ids:
        assert expected_id in actual_ids, f"Expected bank ID '{expected_id}' not found"
    
    # Check structure
    for bank in banks:
        assert "id" in bank, "Bank missing 'id' field"
        assert "name" in bank, "Bank missing 'name' field"
    
    print("✅ Test 1 PASSED: dummy-banks returns 10 banks with correct IDs")
    return True


def test_2_create_fin_school_with_priority_sorting():
    """Test 2: POST /api/credit/fin-schools creates school with banks sorted by priority"""
    print("\n=== Test 2: POST /api/credit/fin-schools (priority sorting) ===")
    
    url = f"{BASE_URL}/credit/fin-schools"
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    payload = {
        "name": "Sunrise Academy",
        "financing_enabled": True,
        "banks": [
            {"bank_id": "hdfc", "interest_rate": 12.5, "priority": 2},
            {"bank_id": "icici", "interest_rate": 11.9, "priority": 1}
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    school = response.json()
    print(f"Created school ID: {school.get('id')}")
    created_school_ids.append(school.get('id'))
    
    # Verify structure
    assert "id" in school, "School missing 'id'"
    assert school["name"] == "Sunrise Academy", f"Name mismatch: {school['name']}"
    assert school["financing_enabled"] == True, "financing_enabled should be True"
    assert "banks" in school, "School missing 'banks'"
    assert "created_at" in school, "School missing 'created_at'"
    assert "updated_at" in school, "School missing 'updated_at'"
    
    # CRITICAL: Verify banks are sorted by priority (ascending)
    banks = school["banks"]
    print(f"Banks count: {len(banks)}")
    assert len(banks) == 2, f"Expected 2 banks, got {len(banks)}"
    
    # First bank should be ICICI (priority 1, rate 11.9)
    first_bank = banks[0]
    print(f"First bank: {first_bank}")
    assert first_bank["bank_id"] == "icici", f"First bank should be ICICI, got {first_bank['bank_id']}"
    assert first_bank["priority"] == 1, f"First bank priority should be 1, got {first_bank['priority']}"
    assert first_bank["interest_rate"] == 11.9, f"ICICI rate should be 11.9, got {first_bank['interest_rate']}"
    assert first_bank["bank_name"] == "ICICI Bank", f"Bank name should be auto-filled, got {first_bank.get('bank_name')}"
    
    # Second bank should be HDFC (priority 2, rate 12.5)
    second_bank = banks[1]
    print(f"Second bank: {second_bank}")
    assert second_bank["bank_id"] == "hdfc", f"Second bank should be HDFC, got {second_bank['bank_id']}"
    assert second_bank["priority"] == 2, f"Second bank priority should be 2, got {second_bank['priority']}"
    assert second_bank["interest_rate"] == 12.5, f"HDFC rate should be 12.5, got {second_bank['interest_rate']}"
    assert second_bank["bank_name"] == "HDFC Bank", f"Bank name should be auto-filled, got {second_bank.get('bank_name')}"
    
    print("✅ Test 2 PASSED: School created with banks sorted by priority (ICICI first, HDFC second)")
    return school["id"]


def test_3_list_fin_schools():
    """Test 3: GET /api/credit/fin-schools (admin) lists all schools"""
    print("\n=== Test 3: GET /api/credit/fin-schools (list) ===")
    
    url = f"{BASE_URL}/credit/fin-schools"
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    schools = response.json()
    print(f"Schools returned: {len(schools)}")
    assert len(schools) >= 1, "Should have at least 1 school (created in test 2)"
    
    # Find our created school
    created_school = None
    for school in schools:
        if school.get("name") == "Sunrise Academy":
            created_school = school
            break
    
    assert created_school is not None, "Created school 'Sunrise Academy' not found in list"
    print(f"Found created school: {created_school['id']}")
    
    # Verify banks are normalized and sorted
    banks = created_school.get("banks", [])
    assert len(banks) == 2, f"Expected 2 banks, got {len(banks)}"
    assert banks[0]["bank_id"] == "icici", "First bank should be ICICI (priority 1)"
    assert banks[1]["bank_id"] == "hdfc", "Second bank should be HDFC (priority 2)"
    
    print("✅ Test 3 PASSED: List returns created school with normalized banks")
    return True


def test_4_get_fin_school_by_id_authenticated():
    """Test 4: GET /api/credit/fin-schools/{id} (any authenticated) returns school details"""
    print("\n=== Test 4: GET /api/credit/fin-schools/{id} (authenticated) ===")
    
    school_id = created_school_ids[0]
    url = f"{BASE_URL}/credit/fin-schools/{school_id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    school = response.json()
    print(f"School ID: {school.get('id')}")
    assert school["id"] == school_id, "School ID mismatch"
    assert school["name"] == "Sunrise Academy", "School name mismatch"
    assert school["financing_enabled"] == True, "financing_enabled should be True"
    
    # Verify banks with independent rates and priority order
    banks = school["banks"]
    assert len(banks) == 2, f"Expected 2 banks, got {len(banks)}"
    assert banks[0]["bank_id"] == "icici", "First bank should be ICICI"
    assert banks[0]["interest_rate"] == 11.9, "ICICI rate should be 11.9"
    assert banks[0]["priority"] == 1, "ICICI priority should be 1"
    assert banks[1]["bank_id"] == "hdfc", "Second bank should be HDFC"
    assert banks[1]["interest_rate"] == 12.5, "HDFC rate should be 12.5"
    assert banks[1]["priority"] == 2, "HDFC priority should be 2"
    
    print("✅ Test 4 PASSED: GET by ID returns school with correct banks and rates")
    return True


def test_5_get_fin_school_by_id_not_found():
    """Test 5: GET /api/credit/fin-schools/{unknown_id} returns 404"""
    print("\n=== Test 5: GET /api/credit/fin-schools/{unknown_id} (404) ===")
    
    bogus_id = "00000000-0000-0000-0000-000000000000"
    url = f"{BASE_URL}/credit/fin-schools/{bogus_id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    print("✅ Test 5 PASSED: GET unknown ID returns 404")
    return True


def test_6_update_fin_school():
    """Test 6: PUT /api/credit/fin-schools/{id} updates school with new banks and rates"""
    print("\n=== Test 6: PUT /api/credit/fin-schools/{id} (update) ===")
    
    school_id = created_school_ids[0]
    url = f"{BASE_URL}/credit/fin-schools/{school_id}"
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    payload = {
        "name": "Sunrise Academy",
        "financing_enabled": False,
        "banks": [
            {"bank_id": "axis", "interest_rate": 13.0, "priority": 1},
            {"bank_id": "hdfc", "interest_rate": 12.5, "priority": 2},
            {"bank_id": "icici", "interest_rate": 10.5, "priority": 3}
        ]
    }
    
    response = requests.put(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    school = response.json()
    print(f"Updated school ID: {school.get('id')}")
    
    # Verify financing_enabled is now False
    assert school["financing_enabled"] == False, "financing_enabled should be False after update"
    
    # Verify banks are sorted by priority (axis first, hdfc second, icici third)
    banks = school["banks"]
    print(f"Banks count: {len(banks)}")
    assert len(banks) == 3, f"Expected 3 banks, got {len(banks)}"
    
    assert banks[0]["bank_id"] == "axis", f"First bank should be Axis, got {banks[0]['bank_id']}"
    assert banks[0]["interest_rate"] == 13.0, f"Axis rate should be 13.0, got {banks[0]['interest_rate']}"
    assert banks[0]["priority"] == 1, f"Axis priority should be 1, got {banks[0]['priority']}"
    
    assert banks[1]["bank_id"] == "hdfc", f"Second bank should be HDFC, got {banks[1]['bank_id']}"
    assert banks[1]["interest_rate"] == 12.5, f"HDFC rate should be 12.5, got {banks[1]['interest_rate']}"
    assert banks[1]["priority"] == 2, f"HDFC priority should be 2, got {banks[1]['priority']}"
    
    assert banks[2]["bank_id"] == "icici", f"Third bank should be ICICI, got {banks[2]['bank_id']}"
    assert banks[2]["interest_rate"] == 10.5, f"ICICI rate should be 10.5, got {banks[2]['interest_rate']}"
    assert banks[2]["priority"] == 3, f"ICICI priority should be 3, got {banks[2]['priority']}"
    
    # Verify updated_at changed
    assert "updated_at" in school, "School missing 'updated_at'"
    
    print("✅ Test 6 PASSED: School updated with new banks, rates, and financing_enabled=False")
    return True


def test_7_update_fin_school_not_found():
    """Test 7: PUT /api/credit/fin-schools/{unknown_id} returns 404"""
    print("\n=== Test 7: PUT /api/credit/fin-schools/{unknown_id} (404) ===")
    
    bogus_id = "00000000-0000-0000-0000-000000000000"
    url = f"{BASE_URL}/credit/fin-schools/{bogus_id}"
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    payload = {
        "name": "Test School",
        "financing_enabled": True,
        "banks": []
    }
    
    response = requests.put(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    print("✅ Test 7 PASSED: PUT unknown ID returns 404")
    return True


def test_8_validation_empty_name():
    """Test 8: POST with empty name returns 400"""
    print("\n=== Test 8: POST /api/credit/fin-schools (empty name validation) ===")
    
    url = f"{BASE_URL}/credit/fin-schools"
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    payload = {
        "name": "",
        "financing_enabled": True,
        "banks": []
    }
    
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    print("✅ Test 8 PASSED: Empty name returns 400")
    return True


def test_9_authorization_parent_list_403():
    """Test 9: Parent (non-admin) GET /api/credit/fin-schools returns 403"""
    print("\n=== Test 9: Parent GET /api/credit/fin-schools (403) ===")
    
    url = f"{BASE_URL}/credit/fin-schools"
    headers = {"Authorization": f"Bearer {parent_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    print("✅ Test 9 PASSED: Parent GET list returns 403")
    return True


def test_10_authorization_parent_create_403():
    """Test 10: Parent (non-admin) POST /api/credit/fin-schools returns 403"""
    print("\n=== Test 10: Parent POST /api/credit/fin-schools (403) ===")
    
    url = f"{BASE_URL}/credit/fin-schools"
    headers = {"Authorization": f"Bearer {parent_token}", "Content-Type": "application/json"}
    
    payload = {
        "name": "Test School",
        "financing_enabled": True,
        "banks": []
    }
    
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    print("✅ Test 10 PASSED: Parent POST returns 403")
    return True


def test_11_authorization_parent_update_403():
    """Test 11: Parent (non-admin) PUT /api/credit/fin-schools/{id} returns 403"""
    print("\n=== Test 11: Parent PUT /api/credit/fin-schools/{id} (403) ===")
    
    school_id = created_school_ids[0]
    url = f"{BASE_URL}/credit/fin-schools/{school_id}"
    headers = {"Authorization": f"Bearer {parent_token}", "Content-Type": "application/json"}
    
    payload = {
        "name": "Test School",
        "financing_enabled": True,
        "banks": []
    }
    
    response = requests.put(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    print("✅ Test 11 PASSED: Parent PUT returns 403")
    return True


def test_12_authorization_parent_delete_403():
    """Test 12: Parent (non-admin) DELETE /api/credit/fin-schools/{id} returns 403"""
    print("\n=== Test 12: Parent DELETE /api/credit/fin-schools/{id} (403) ===")
    
    school_id = created_school_ids[0]
    url = f"{BASE_URL}/credit/fin-schools/{school_id}"
    headers = {"Authorization": f"Bearer {parent_token}"}
    response = requests.delete(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    print("✅ Test 12 PASSED: Parent DELETE returns 403")
    return True


def test_13_authorization_parent_get_by_id_200():
    """Test 13: Parent (non-admin) CAN call GET /api/credit/fin-schools/{id} (200)"""
    print("\n=== Test 13: Parent GET /api/credit/fin-schools/{id} (200) ===")
    
    school_id = created_school_ids[0]
    url = f"{BASE_URL}/credit/fin-schools/{school_id}"
    headers = {"Authorization": f"Bearer {parent_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    school = response.json()
    print(f"School ID: {school.get('id')}")
    assert school["id"] == school_id, "School ID mismatch"
    
    print("✅ Test 13 PASSED: Parent CAN call GET by ID (200)")
    return True


def test_14_authorization_parent_dummy_banks_200():
    """Test 14: Parent (non-admin) CAN call GET /api/credit/dummy-banks (200)"""
    print("\n=== Test 14: Parent GET /api/credit/dummy-banks (200) ===")
    
    url = f"{BASE_URL}/credit/dummy-banks"
    headers = {"Authorization": f"Bearer {parent_token}"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    banks = response.json()
    print(f"Banks returned: {len(banks)}")
    assert len(banks) == 10, f"Expected 10 banks, got {len(banks)}"
    
    print("✅ Test 14 PASSED: Parent CAN call GET dummy-banks (200)")
    return True


def test_15_no_auth_401():
    """Test 15: No auth header returns 401 on protected endpoints"""
    print("\n=== Test 15: No auth header (401) ===")
    
    # Test dummy-banks
    url = f"{BASE_URL}/credit/dummy-banks"
    response = requests.get(url)
    print(f"dummy-banks status: {response.status_code}")
    assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    # Test fin-schools list
    url = f"{BASE_URL}/credit/fin-schools"
    response = requests.get(url)
    print(f"fin-schools list status: {response.status_code}")
    assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    print("✅ Test 15 PASSED: No auth returns 401/403")
    return True


def test_16_delete_fin_school():
    """Test 16: DELETE /api/credit/fin-schools/{id} removes school"""
    print("\n=== Test 16: DELETE /api/credit/fin-schools/{id} ===")
    
    school_id = created_school_ids[0]
    url = f"{BASE_URL}/credit/fin-schools/{school_id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.delete(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    result = response.json()
    assert result.get("ok") == True, "Expected {ok: true}"
    
    # Verify subsequent GET returns 404
    response = requests.get(url, headers=headers)
    print(f"GET after DELETE status: {response.status_code}")
    assert response.status_code == 404, f"Expected 404 after delete, got {response.status_code}"
    
    print("✅ Test 16 PASSED: School deleted, subsequent GET returns 404")
    return True


def test_17_delete_fin_school_not_found():
    """Test 17: DELETE /api/credit/fin-schools/{unknown_id} returns 404"""
    print("\n=== Test 17: DELETE /api/credit/fin-schools/{unknown_id} (404) ===")
    
    bogus_id = "00000000-0000-0000-0000-000000000000"
    url = f"{BASE_URL}/credit/fin-schools/{bogus_id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.delete(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    print("✅ Test 17 PASSED: DELETE unknown ID returns 404")
    return True


def cleanup():
    """Clean up any remaining test schools"""
    print("\n=== Cleanup: Deleting remaining test schools ===")
    
    for school_id in created_school_ids[1:]:  # Skip first one (already deleted in test 16)
        url = f"{BASE_URL}/credit/fin-schools/{school_id}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.delete(url, headers=headers)
        print(f"Deleted school {school_id}: {response.status_code}")
    
    print("✅ Cleanup complete")


def main():
    global admin_token, parent_token
    
    print("=" * 80)
    print("Backend API Testing: School↔Bank Financing Management")
    print("=" * 80)
    
    # Login
    print("\n--- Authentication ---")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    parent_token = login(PARENT_EMAIL, PARENT_PASSWORD)
    
    if not admin_token:
        print("❌ FAILED: Admin login failed")
        return
    
    if not parent_token:
        print("❌ FAILED: Parent login failed")
        return
    
    # Run tests
    tests = [
        test_1_dummy_banks_authenticated,
        test_2_create_fin_school_with_priority_sorting,
        test_3_list_fin_schools,
        test_4_get_fin_school_by_id_authenticated,
        test_5_get_fin_school_by_id_not_found,
        test_6_update_fin_school,
        test_7_update_fin_school_not_found,
        test_8_validation_empty_name,
        test_9_authorization_parent_list_403,
        test_10_authorization_parent_create_403,
        test_11_authorization_parent_update_403,
        test_12_authorization_parent_delete_403,
        test_13_authorization_parent_get_by_id_200,
        test_14_authorization_parent_dummy_banks_200,
        test_15_no_auth_401,
        test_16_delete_fin_school,
        test_17_delete_fin_school_not_found,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    # Cleanup
    try:
        cleanup()
    except Exception as e:
        print(f"⚠️  Cleanup error: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 80)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ {failed} TEST(S) FAILED")


if __name__ == "__main__":
    main()
