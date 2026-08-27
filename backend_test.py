#!/usr/bin/env python3
"""
Backend API Testing for BiglypEnroll
Test: POST /api/parent/cibil-check endpoint (Bucket 4 Screen 2 eligibility gate)
"""

import requests
import sys
from typing import Dict, Any

# Base URL from frontend/.env
BASE_URL = "https://github-preview-63.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"


def login(email: str, password: str) -> str:
    """Login and return Bearer token"""
    url = f"{BASE_URL}/auth/login"
    response = requests.post(url, json={"email": email, "password": password})
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code} {response.text}")
        sys.exit(1)
    data = response.json()
    token = data.get("token")
    if not token:
        print(f"❌ No token in login response: {data}")
        sys.exit(1)
    print(f"✅ Login successful: {email}")
    return token


def test_cibil_check(token: str, pan: str, consent: bool, expected_status: int, test_name: str) -> Dict[str, Any]:
    """Test POST /api/parent/cibil-check endpoint"""
    url = f"{BASE_URL}/parent/cibil-check"
    headers = {"Authorization": f"Bearer {token}"}
    body = {"pan": pan, "consent": consent}
    
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Request: POST {url}")
    print(f"Body: {body}")
    
    response = requests.post(url, json=body, headers=headers)
    
    print(f"Response Status: {response.status_code}")
    
    if response.status_code != expected_status:
        print(f"❌ FAILED: Expected status {expected_status}, got {response.status_code}")
        print(f"Response: {response.text}")
        return {"success": False, "status": response.status_code, "data": None}
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response Data:")
        print(f"  - score: {data.get('score')} (type: {type(data.get('score')).__name__})")
        print(f"  - band: {data.get('band')} (type: {type(data.get('band')).__name__})")
        print(f"  - approved: {data.get('approved')} (type: {type(data.get('approved')).__name__})")
        print(f"  - emi_threshold: {data.get('emi_threshold')} (type: {type(data.get('emi_threshold')).__name__})")
        print(f"  - emi_eligible: {data.get('emi_eligible')} (type: {type(data.get('emi_eligible')).__name__})")
        print(f"  - max_eligible: {data.get('max_eligible')}")
        print(f"  - pan_masked: {data.get('pan_masked')}")
        print(f"  - bureau: {data.get('bureau')}")
        print(f"  - pull_type: {data.get('pull_type')}")
        print(f"  - factors: {len(data.get('factors', []))} items")
        print(f"  - decision: {data.get('decision')[:50]}...")
        print(f"  - checked_at: {data.get('checked_at')}")
        return {"success": True, "status": response.status_code, "data": data}
    else:
        print(f"Response: {response.text}")
        return {"success": True, "status": response.status_code, "data": None}


def test_cibil_check_no_auth(pan: str, consent: bool, test_name: str) -> Dict[str, Any]:
    """Test POST /api/parent/cibil-check endpoint without auth"""
    url = f"{BASE_URL}/parent/cibil-check"
    body = {"pan": pan, "consent": consent}
    
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Request: POST {url} (NO AUTH HEADER)")
    print(f"Body: {body}")
    
    response = requests.post(url, json=body)
    
    print(f"Response Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code not in [401, 403]:
        print(f"❌ FAILED: Expected status 401 or 403, got {response.status_code}")
        return {"success": False, "status": response.status_code, "data": None}
    
    print(f"✅ PASSED: Correctly returned {response.status_code}")
    return {"success": True, "status": response.status_code, "data": None}


def main():
    print("="*80)
    print("BACKEND API TESTING: POST /api/parent/cibil-check")
    print("="*80)
    
    # Login as parent
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    
    results = []
    
    # Test 1: Low score PAN (ZZZZZ prefix) - should have emi_eligible=false
    result1 = test_cibil_check(
        token=token,
        pan="ZZZZZ1234A",
        consent=True,
        expected_status=200,
        test_name="Test 1: Low score PAN (ZZZZZ1234A) - emi_eligible should be false"
    )
    results.append(("Test 1", result1))
    
    if result1["success"] and result1["data"]:
        data = result1["data"]
        # Verify emi_threshold == 750
        if data.get("emi_threshold") != 750:
            print(f"❌ FAILED: emi_threshold should be 750, got {data.get('emi_threshold')}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: emi_threshold == 750")
        
        # Verify emi_eligible == false
        if data.get("emi_eligible") != False:
            print(f"❌ FAILED: emi_eligible should be False, got {data.get('emi_eligible')}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: emi_eligible == False")
        
        # Verify score < 750
        if data.get("score") >= 750:
            print(f"❌ FAILED: score should be < 750, got {data.get('score')}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: score < 750 (score={data.get('score')})")
        
        # Verify existing fields present
        if not isinstance(data.get("score"), int):
            print(f"❌ FAILED: score should be int, got {type(data.get('score'))}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: score is int")
        
        if not isinstance(data.get("approved"), bool):
            print(f"❌ FAILED: approved should be bool, got {type(data.get('approved'))}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: approved is bool")
        
        if not isinstance(data.get("band"), str):
            print(f"❌ FAILED: band should be str, got {type(data.get('band'))}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: band is str")
        
        # Verify consistency: emi_eligible == (score >= emi_threshold)
        expected_eligible = data.get("score") >= data.get("emi_threshold")
        if data.get("emi_eligible") != expected_eligible:
            print(f"❌ FAILED: Consistency check failed. emi_eligible={data.get('emi_eligible')}, but score={data.get('score')} >= emi_threshold={data.get('emi_threshold')} should be {expected_eligible}")
            result1["success"] = False
        else:
            print(f"✅ PASSED: Consistency check (emi_eligible == score >= emi_threshold)")
    
    # Test 2: High score PAN (AAAAA prefix) - should have emi_eligible=true
    result2 = test_cibil_check(
        token=token,
        pan="AAAAA1234A",
        consent=True,
        expected_status=200,
        test_name="Test 2: High score PAN (AAAAA1234A) - emi_eligible should be true"
    )
    results.append(("Test 2", result2))
    
    if result2["success"] and result2["data"]:
        data = result2["data"]
        # Verify emi_threshold == 750
        if data.get("emi_threshold") != 750:
            print(f"❌ FAILED: emi_threshold should be 750, got {data.get('emi_threshold')}")
            result2["success"] = False
        else:
            print(f"✅ PASSED: emi_threshold == 750")
        
        # Verify emi_eligible == true
        if data.get("emi_eligible") != True:
            print(f"❌ FAILED: emi_eligible should be True, got {data.get('emi_eligible')}")
            result2["success"] = False
        else:
            print(f"✅ PASSED: emi_eligible == True")
        
        # Verify score >= 750
        if data.get("score") < 750:
            print(f"❌ FAILED: score should be >= 750, got {data.get('score')}")
            result2["success"] = False
        else:
            print(f"✅ PASSED: score >= 750 (score={data.get('score')})")
        
        # Verify consistency: emi_eligible == (score >= emi_threshold)
        expected_eligible = data.get("score") >= data.get("emi_threshold")
        if data.get("emi_eligible") != expected_eligible:
            print(f"❌ FAILED: Consistency check failed. emi_eligible={data.get('emi_eligible')}, but score={data.get('score')} >= emi_threshold={data.get('emi_threshold')} should be {expected_eligible}")
            result2["success"] = False
        else:
            print(f"✅ PASSED: Consistency check (emi_eligible == score >= emi_threshold)")
    
    # Test 3: Invalid PAN - should return 400
    result3 = test_cibil_check(
        token=token,
        pan="ABC",
        consent=True,
        expected_status=400,
        test_name="Test 3: Invalid PAN (ABC) - should return 400"
    )
    results.append(("Test 3", result3))
    if result3["success"]:
        print(f"✅ PASSED: Invalid PAN correctly returned 400")
    
    # Test 4: Consent false - should return 400
    result4 = test_cibil_check(
        token=token,
        pan="AAAAA1234A",
        consent=False,
        expected_status=400,
        test_name="Test 4: Consent false - should return 400"
    )
    results.append(("Test 4", result4))
    if result4["success"]:
        print(f"✅ PASSED: Consent false correctly returned 400")
    
    # Test 5: No auth header - should return 401 or 403
    result5 = test_cibil_check_no_auth(
        pan="AAAAA1234A",
        consent=True,
        test_name="Test 5: No auth header - should return 401 or 403"
    )
    results.append(("Test 5", result5))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, r in results if r["success"])
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
