#!/usr/bin/env python3
"""
BiglypEnroll Backend Testing - Psychometry Report PDF
Testing: GET /api/parent/psychometry/report/{student_id}
"""
import requests
import json
import re

# Backend URL from frontend/.env
BASE_URL = "https://github-preview-63.preview.emergentagent.com/api"

# Test credentials from test_credentials.md
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"
FINANCE_EMAIL = "finance@biglyp.com"
FINANCE_PASSWORD = "finance123"
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
# PSYCHOMETRY REPORT PDF TESTS
# ============================================================================

def test_1_parent_login_and_get_child():
    """Step 1: Login as parent and get first child (Aarav Sharma, Class 10)"""
    print("\n[TEST 1] Login as parent and get first child")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/children", headers=headers)
    print(f"  GET /api/parent/children status: {resp.status_code}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    assert len(data) > 0, "Expected at least one child"
    first_child = data[0]
    
    print(f"  First child:")
    print(f"    Name: {first_child.get('name')}")
    print(f"    Grade: {first_child.get('grade')}")
    print(f"    ID: {first_child.get('id')}")
    
    # Verify it's Aarav Sharma, Class 10
    assert first_child.get('name') == 'Aarav Sharma', f"Expected 'Aarav Sharma', got {first_child.get('name')}"
    assert first_child.get('grade') == 'Class 10', f"Expected 'Class 10', got {first_child.get('grade')}"
    
    print(f"  ✅ PASS: Found Aarav Sharma, Class 10 with ID {first_child.get('id')}")
    return token, first_child.get('id')

def test_2_get_pdf_report_authenticated(token: str, student_id: str):
    """Step 2: GET /api/parent/psychometry/report/{student_id} with Bearer token"""
    print(f"\n[TEST 2] GET /api/parent/psychometry/report/{student_id} with Bearer token")
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/psychometry/report/{student_id}", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('Content-Type')}")
    print(f"  Content-Disposition: {resp.headers.get('Content-Disposition')}")
    print(f"  Content-Length: {len(resp.content)} bytes")
    
    # Verify HTTP 200
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # Verify Content-Type is application/pdf
    content_type = resp.headers.get('Content-Type', '')
    assert 'application/pdf' in content_type, f"Expected 'application/pdf', got '{content_type}'"
    
    # Verify Content-Disposition contains filename with ExploreX_report_Aarav_Sharma.pdf
    content_disposition = resp.headers.get('Content-Disposition', '')
    assert 'ExploreX_report_Aarav_Sharma.pdf' in content_disposition, \
        f"Expected filename 'ExploreX_report_Aarav_Sharma.pdf' in Content-Disposition, got '{content_disposition}'"
    
    # Verify body size > 10KB
    body_size = len(resp.content)
    assert body_size > 10240, f"Expected body size > 10KB, got {body_size} bytes"
    
    # Verify body starts with %PDF
    pdf_header = resp.content[:4]
    assert pdf_header == b'%PDF', f"Expected PDF header '%PDF', got {pdf_header}"
    
    print(f"  ✅ PASS: PDF report downloaded successfully")
    print(f"    - HTTP 200")
    print(f"    - Content-Type: application/pdf")
    print(f"    - Filename: ExploreX_report_Aarav_Sharma.pdf")
    print(f"    - Size: {body_size} bytes (> 10KB)")
    print(f"    - Valid PDF header: %PDF")
    
    return True

def test_3_unauthenticated_request(student_id: str):
    """Step 3: Same request without Authorization header -> expect 401"""
    print(f"\n[TEST 3] GET /api/parent/psychometry/report/{student_id} without Authorization")
    
    resp = requests.get(f"{BASE_URL}/parent/psychometry/report/{student_id}")
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    # Verify HTTP 401
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    print(f"  ✅ PASS: Unauthenticated request correctly returned 401")
    return True

def test_4_finance_role_forbidden(student_id: str):
    """Step 4: Login as finance role and call endpoint -> expect 403"""
    print(f"\n[TEST 4] GET /api/parent/psychometry/report/{student_id} as finance role")
    token = login(FINANCE_EMAIL, FINANCE_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/psychometry/report/{student_id}", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    # Verify HTTP 403
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    data = resp.json()
    assert 'detail' in data, "Expected 'detail' field in error response"
    print(f"  Error detail: {data.get('detail')}")
    
    print(f"  ✅ PASS: Finance role correctly returned 403")
    return True

def test_5_school_admin_allowed(student_id: str):
    """Step 5: Login as school_admin and call endpoint -> expect 200 PDF"""
    print(f"\n[TEST 5] GET /api/parent/psychometry/report/{student_id} as school_admin")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/psychometry/report/{student_id}", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('Content-Type')}")
    print(f"  Content-Length: {len(resp.content)} bytes")
    
    # Verify HTTP 200
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # Verify Content-Type is application/pdf
    content_type = resp.headers.get('Content-Type', '')
    assert 'application/pdf' in content_type, f"Expected 'application/pdf', got '{content_type}'"
    
    # Verify body starts with %PDF
    pdf_header = resp.content[:4]
    assert pdf_header == b'%PDF', f"Expected PDF header '%PDF', got {pdf_header}"
    
    print(f"  ✅ PASS: School admin successfully downloaded PDF")
    return True

def test_6_bogus_student_id(token: str):
    """Step 6: Bogus student id (24-char hex that doesn't exist) -> expect 404"""
    print(f"\n[TEST 6] GET /api/parent/psychometry/report with bogus student ID")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Use a valid 24-char hex ObjectId that doesn't exist
    bogus_id = "000000000000000000000000"
    
    resp = requests.get(f"{BASE_URL}/parent/psychometry/report/{bogus_id}", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    # Verify HTTP 404
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    
    data = resp.json()
    assert 'detail' in data, "Expected 'detail' field in error response"
    print(f"  Error detail: {data.get('detail')}")
    
    print(f"  ✅ PASS: Bogus student ID correctly returned 404")
    return True

def test_7_malformed_student_id(token: str):
    """Step 7: Malformed student id (e.g. 'abc') -> report what happens"""
    print(f"\n[TEST 7] GET /api/parent/psychometry/report with malformed student ID")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Use a malformed ID
    malformed_id = "abc"
    
    resp = requests.get(f"{BASE_URL}/parent/psychometry/report/{malformed_id}", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    # Report what happens (could be 400, 404, or 500)
    print(f"  ℹ️  INFO: Malformed ID returned HTTP {resp.status_code}")
    
    if resp.status_code in [400, 404, 422, 500]:
        print(f"  ✅ PASS: Malformed ID handled with error response (HTTP {resp.status_code})")
    else:
        print(f"  ⚠️  WARNING: Unexpected status code {resp.status_code} for malformed ID")
    
    return True

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all psychometry report PDF tests"""
    print("=" * 80)
    print("PSYCHOMETRY REPORT PDF ENDPOINT TESTING")
    print("=" * 80)
    
    try:
        # Test 1: Login as parent and get child
        parent_token, student_id = test_1_parent_login_and_get_child()
        
        # Test 2: Get PDF report with authentication
        test_2_get_pdf_report_authenticated(parent_token, student_id)
        
        # Test 3: Unauthenticated request
        test_3_unauthenticated_request(student_id)
        
        # Test 4: Finance role forbidden
        test_4_finance_role_forbidden(student_id)
        
        # Test 5: School admin allowed
        test_5_school_admin_allowed(student_id)
        
        # Test 6: Bogus student ID
        test_6_bogus_student_id(parent_token)
        
        # Test 7: Malformed student ID
        test_7_malformed_student_id(parent_token)
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
