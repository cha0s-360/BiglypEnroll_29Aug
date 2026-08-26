#!/usr/bin/env python3
"""
BiglypEnroll Backend Testing - CIBIL soft-pull endpoint
Test POST /api/parent/cibil-check
"""
import requests
import json

# Backend URL from frontend/.env
BASE_URL = "https://enroll-system-22.preview.emergentagent.com/api"

# Test credentials
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"

def login(email: str, password: str) -> str:
    """Login and return access token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed for {email}: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("token")

def test_1_valid_pan():
    """Test 1: Valid PAN 'ABCDE1234F' with consent=true -> HTTP 200 with all required fields"""
    print("\n[TEST 1] Valid PAN 'ABCDE1234F' with consent=true")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"pan": "ABCDE1234F", "consent": True}
    resp = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {json.dumps(resp.json(), indent=2)}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Check all required fields
    required_fields = ["score", "band", "band_color", "approved", "max_eligible", 
                      "pan_masked", "bureau", "pull_type", "factors", "decision", "checked_at"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Validate field types and values
    assert isinstance(data["score"], int), f"score must be int, got {type(data['score'])}"
    assert 300 <= data["score"] <= 900, f"score must be 300-900, got {data['score']}"
    assert data["band"] in ["Excellent", "Good", "Fair", "Poor"], f"Invalid band: {data['band']}"
    assert isinstance(data["approved"], bool), f"approved must be bool, got {type(data['approved'])}"
    assert isinstance(data["max_eligible"], int), f"max_eligible must be int, got {type(data['max_eligible'])}"
    assert isinstance(data["pan_masked"], str), f"pan_masked must be str, got {type(data['pan_masked'])}"
    assert isinstance(data["bureau"], str), f"bureau must be str, got {type(data['bureau'])}"
    assert isinstance(data["pull_type"], str), f"pull_type must be str, got {type(data['pull_type'])}"
    assert isinstance(data["factors"], list), f"factors must be list, got {type(data['factors'])}"
    assert len(data["factors"]) == 4, f"factors must have 4 items, got {len(data['factors'])}"
    
    # Check factors structure
    for factor in data["factors"]:
        assert "label" in factor, "Each factor must have 'label'"
        assert "status" in factor, "Each factor must have 'status'"
    
    assert isinstance(data["decision"], str), f"decision must be str, got {type(data['decision'])}"
    assert isinstance(data["checked_at"], str), f"checked_at must be str, got {type(data['checked_at'])}"
    
    # Check specific value for ABCDE1234F (should be 801 based on md5 hash)
    assert data["score"] == 801, f"Expected score 801 for ABCDE1234F, got {data['score']}"
    assert data["band"] == "Excellent", f"Expected band 'Excellent', got {data['band']}"
    assert data["approved"] is True, f"Expected approved=True, got {data['approved']}"
    
    print(f"  ✅ PASS: All required fields present with correct types and values")
    print(f"  Score: {data['score']}, Band: {data['band']}, Approved: {data['approved']}, Max Eligible: {data['max_eligible']}")
    return data

def test_2_deterministic():
    """Test 2: Same PAN twice returns identical score (deterministic)"""
    print("\n[TEST 2] Deterministic check - same PAN twice")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"pan": "ABCDE1234F", "consent": True}
    
    # First call
    resp1 = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    score1 = data1["score"]
    
    # Second call
    resp2 = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    score2 = data2["score"]
    
    print(f"  First call score: {score1}")
    print(f"  Second call score: {score2}")
    
    assert score1 == score2, f"Not deterministic: {score1} != {score2}"
    print(f"  ✅ PASS: Deterministic - same score returned both times")

def test_3_excellent_hook():
    """Test 3: PAN 'AAAAA1234A' -> score >= 800, band='Excellent', approved=true, max_eligible=250000"""
    print("\n[TEST 3] Excellent hook - PAN 'AAAAA1234A'")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"pan": "AAAAA1234A", "consent": True}
    resp = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    print(f"  Response: {json.dumps(data, indent=2)}")
    
    assert data["score"] >= 800, f"Expected score >= 800, got {data['score']}"
    assert data["band"] == "Excellent", f"Expected band 'Excellent', got {data['band']}"
    assert data["approved"] is True, f"Expected approved=True, got {data['approved']}"
    assert data["max_eligible"] == 250000, f"Expected max_eligible=250000, got {data['max_eligible']}"
    
    print(f"  ✅ PASS: Excellent hook working - score={data['score']}, band={data['band']}, approved={data['approved']}, max_eligible={data['max_eligible']}")

def test_4_poor_hook():
    """Test 4: PAN 'ZZZZZ9999Z' -> score in 540..579, band='Poor', approved=false, max_eligible=0"""
    print("\n[TEST 4] Poor hook - PAN 'ZZZZZ9999Z'")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"pan": "ZZZZZ9999Z", "consent": True}
    resp = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    print(f"  Response: {json.dumps(data, indent=2)}")
    
    assert 540 <= data["score"] <= 579, f"Expected score in 540..579, got {data['score']}"
    assert data["band"] == "Poor", f"Expected band 'Poor', got {data['band']}"
    assert data["approved"] is False, f"Expected approved=False, got {data['approved']}"
    assert data["max_eligible"] == 0, f"Expected max_eligible=0, got {data['max_eligible']}"
    
    print(f"  ✅ PASS: Poor hook working - score={data['score']}, band={data['band']}, approved={data['approved']}, max_eligible={data['max_eligible']}")

def test_5_consent_false():
    """Test 5: consent=false with valid PAN -> HTTP 400 with detail mentioning 'consent'"""
    print("\n[TEST 5] Consent=false with valid PAN")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"pan": "ABCDE1234F", "consent": False}
    resp = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    # Check that error message mentions "consent"
    error_text = resp.text.lower()
    assert "consent" in error_text, f"Error message should mention 'consent', got: {resp.text}"
    
    print(f"  ✅ PASS: Consent=false correctly rejected with 400 and error mentioning 'consent'")

def test_6_invalid_pan():
    """Test 6: Invalid PAN '123' -> HTTP 400 with detail mentioning 'PAN'"""
    print("\n[TEST 6] Invalid PAN '123'")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"pan": "123", "consent": True}
    resp = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload, headers=headers)
    
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    # Check that error message mentions "PAN"
    error_text = resp.text.upper()
    assert "PAN" in error_text, f"Error message should mention 'PAN', got: {resp.text}"
    
    print(f"  ✅ PASS: Invalid PAN correctly rejected with 400 and error mentioning 'PAN'")

def test_7_no_auth():
    """Test 7: No Authorization header -> HTTP 401 or 403"""
    print("\n[TEST 7] No Authorization header")
    
    payload = {"pan": "ABCDE1234F", "consent": True}
    resp = requests.post(f"{BASE_URL}/parent/cibil-check", json=payload)
    
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code in [401, 403], f"Expected 401 or 403, got {resp.status_code}"
    
    print(f"  ✅ PASS: Unauthenticated request correctly rejected with {resp.status_code}")

def main():
    print("=" * 80)
    print("BiglypEnroll Backend Testing - CIBIL soft-pull endpoint")
    print("POST /api/parent/cibil-check")
    print("=" * 80)
    
    test_results = []
    
    try:
        # Test 1: Valid PAN with all required fields
        try:
            test_1_valid_pan()
            test_results.append(("Test 1: Valid PAN 'ABCDE1234F'", "PASS"))
        except Exception as e:
            test_results.append(("Test 1: Valid PAN 'ABCDE1234F'", f"FAIL: {e}"))
            raise
        
        # Test 2: Deterministic check
        try:
            test_2_deterministic()
            test_results.append(("Test 2: Deterministic check", "PASS"))
        except Exception as e:
            test_results.append(("Test 2: Deterministic check", f"FAIL: {e}"))
            raise
        
        # Test 3: Excellent hook
        try:
            test_3_excellent_hook()
            test_results.append(("Test 3: Excellent hook 'AAAAA1234A'", "PASS"))
        except Exception as e:
            test_results.append(("Test 3: Excellent hook 'AAAAA1234A'", f"FAIL: {e}"))
            raise
        
        # Test 4: Poor hook
        try:
            test_4_poor_hook()
            test_results.append(("Test 4: Poor hook 'ZZZZZ9999Z'", "PASS"))
        except Exception as e:
            test_results.append(("Test 4: Poor hook 'ZZZZZ9999Z'", f"FAIL: {e}"))
            raise
        
        # Test 5: Consent=false
        try:
            test_5_consent_false()
            test_results.append(("Test 5: Consent=false", "PASS"))
        except Exception as e:
            test_results.append(("Test 5: Consent=false", f"FAIL: {e}"))
            raise
        
        # Test 6: Invalid PAN
        try:
            test_6_invalid_pan()
            test_results.append(("Test 6: Invalid PAN '123'", "PASS"))
        except Exception as e:
            test_results.append(("Test 6: Invalid PAN '123'", f"FAIL: {e}"))
            raise
        
        # Test 7: No Authorization
        try:
            test_7_no_auth()
            test_results.append(("Test 7: No Authorization header", "PASS"))
        except Exception as e:
            test_results.append(("Test 7: No Authorization header", f"FAIL: {e}"))
            raise
        
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        for test_name, result in test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✅")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        for test_name, result in test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        for test_name, result in test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
