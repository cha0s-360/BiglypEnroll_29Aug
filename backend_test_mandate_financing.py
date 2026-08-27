"""
BiglypEnroll - Auto-Debit Mandate & EMI Financing Testing
Tests POST /api/parent/mandate and POST /api/parent/pay-financing endpoints.
"""
import os
import requests
import math

# Use the production URL from frontend/.env
BASE_URL = "https://github-preview-63.preview.emergentagent.com"
API = f"{BASE_URL}/api"

# Test credentials from test_credentials.md
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"


def login(email, password):
    """Login and return bearer token."""
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        raise Exception(f"Login failed for {email}: {r.status_code} {r.text}")
    return r.json()["token"]


def auth_header(token):
    """Return Authorization header with bearer token."""
    return {"Authorization": f"Bearer {token}"}


def get_sara_sharma_unpaid_academic_fees(token):
    """
    Get Sara Sharma's student ID and unpaid academic fee heads.
    If Sara has no unpaid fees, try other children.
    Returns: (student_id, student_name, list of unpaid academic fee_head_ids)
    """
    print("\n" + "="*80)
    print("SETUP: Finding Sara Sharma and unpaid academic fees")
    print("="*80)
    
    # Get children
    print("\n1. GET /api/parent/children")
    r = requests.get(f"{API}/parent/children", headers=auth_header(token), timeout=20)
    if r.status_code != 200:
        raise Exception(f"Failed to get children: {r.status_code} {r.text}")
    
    children = r.json()
    print(f"✅ Found {len(children)} child(ren)")
    for child in children:
        print(f"  - {child['name']} (ID: {child['id']})")
    
    # Find Sara Sharma first
    sara = None
    for child in children:
        if "Sara" in child["name"] and "Sharma" in child["name"]:
            sara = child
            break
    
    # If Sara not found, use first child
    if not sara:
        print(f"\n⚠️  Sara Sharma not found, using first child: {children[0]['name']}")
        sara = children[0]
    else:
        print(f"\n✅ Found Sara Sharma: ID={sara['id']}")
    
    # Get fees for Sara
    print(f"\n2. GET /api/parent/fees/{sara['id']}")
    r = requests.get(f"{API}/parent/fees/{sara['id']}", headers=auth_header(token), timeout=20)
    if r.status_code != 200:
        raise Exception(f"Failed to get fees: {r.status_code} {r.text}")
    
    fees_data = r.json()
    items = fees_data.get("items", [])
    print(f"✅ Found {len(items)} fee item(s)")
    
    # Filter unpaid academic fees (non-transport)
    unpaid_academic = []
    for item in items:
        status = "PAID" if item.get("paid") else "UNPAID"
        fee_type = "TRANSPORT" if "transport" in item["name"].lower() or "bus" in item["name"].lower() else "ACADEMIC"
        print(f"  - {item['name']}: ₹{item['amount']} ({item['frequency']}) [{status}] [{fee_type}]")
        
        if not item.get("paid") and fee_type == "ACADEMIC":
            unpaid_academic.append({
                "fee_head_id": item["fee_head_id"],
                "name": item["name"],
                "amount": item["amount"]
            })
    
    # If Sara has no unpaid academic fees, try other children
    if not unpaid_academic:
        print(f"\n⚠️  {sara['name']} has no unpaid academic fees, checking other children...")
        for child in children:
            if child["id"] == sara["id"]:
                continue
            
            print(f"\nChecking {child['name']} (ID: {child['id']})")
            r = requests.get(f"{API}/parent/fees/{child['id']}", headers=auth_header(token), timeout=20)
            if r.status_code != 200:
                continue
            
            fees_data = r.json()
            items = fees_data.get("items", [])
            
            for item in items:
                status = "PAID" if item.get("paid") else "UNPAID"
                fee_type = "TRANSPORT" if "transport" in item["name"].lower() or "bus" in item["name"].lower() else "ACADEMIC"
                print(f"  - {item['name']}: ₹{item['amount']} ({item['frequency']}) [{status}] [{fee_type}]")
                
                if not item.get("paid") and fee_type == "ACADEMIC":
                    unpaid_academic.append({
                        "fee_head_id": item["fee_head_id"],
                        "name": item["name"],
                        "amount": item["amount"]
                    })
            
            if unpaid_academic:
                sara = child
                print(f"\n✅ Using {child['name']} with {len(unpaid_academic)} unpaid academic fee(s)")
                break
    
    if not unpaid_academic:
        raise Exception("No unpaid academic fees found for any child")
    
    print(f"\n✅ Found {len(unpaid_academic)} unpaid academic fee(s) for {sara['name']}")
    for fee in unpaid_academic:
        print(f"  - {fee['name']}: ₹{fee['amount']} (ID: {fee['fee_head_id']})")
    
    return sara["id"], sara["name"], unpaid_academic


def test_mandate_quarterly(token, student_id, fee_head_id, fee_name, fee_amount):
    """
    Test POST /api/parent/mandate with quarterly frequency.
    Verifies:
    - installments == 4
    - schedule length == 4
    - schedule[0].status == "paid", rest == "upcoming"
    - upfront_amount + installment_amount*3 == total
    - account_masked shows only last 4 digits
    - payment.plan_type == "AutoDebit"
    - payment.mode contains "Auto-Debit"
    - GET /api/parent/payments/{id} returns schedule and plan_type
    """
    print("\n" + "="*80)
    print("TEST: POST /api/parent/mandate - Quarterly Frequency")
    print("="*80)
    print(f"Student ID: {student_id}")
    print(f"Fee Head: {fee_name} (₹{fee_amount})")
    
    payload = {
        "student_id": student_id,
        "fee_head_ids": [fee_head_id],
        "frequency": "quarterly",
        "rail": "UPI AutoPay",
        "bank_name": "HDFC Bank",
        "account_holder": "Anjali Sharma",
        "account_number": "123456789012",
        "ifsc": "HDFC0001234"
    }
    
    print(f"\nPayload: {payload}")
    
    r = requests.post(
        f"{API}/parent/mandate",
        json=payload,
        headers=auth_header(token),
        timeout=20
    )
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False, None
    
    data = r.json()
    print(f"\nResponse received with keys: {list(data.keys())}")
    
    errors = []
    
    # Verify response structure
    if "mandate" not in data:
        errors.append("Response missing 'mandate' key")
        print(f"❌ FAILED: Response missing 'mandate' key")
        return False, None
    
    if "payment" not in data:
        errors.append("Response missing 'payment' key")
        print(f"❌ FAILED: Response missing 'payment' key")
        return False, None
    
    mandate = data["mandate"]
    payment = data["payment"]
    
    print(f"\nMandate: {mandate}")
    print(f"\nPayment: {payment}")
    
    # Verify mandate.installments == 4
    if mandate.get("installments") != 4:
        errors.append(f"mandate.installments: expected 4, got {mandate.get('installments')}")
    
    # Verify mandate.schedule length == 4
    schedule = mandate.get("schedule", [])
    if len(schedule) != 4:
        errors.append(f"mandate.schedule length: expected 4, got {len(schedule)}")
    
    # Verify schedule[0].status == "paid", rest == "upcoming"
    if len(schedule) >= 1:
        if schedule[0].get("status") != "paid":
            errors.append(f"schedule[0].status: expected 'paid', got {schedule[0].get('status')}")
    
    for i in range(1, len(schedule)):
        if schedule[i].get("status") != "upcoming":
            errors.append(f"schedule[{i}].status: expected 'upcoming', got {schedule[i].get('status')}")
    
    # Verify upfront_amount + installment_amount*3 == total
    upfront = mandate.get("upfront_amount", 0)
    installment = mandate.get("installment_amount", 0)
    total = mandate.get("total", 0)
    calculated_total = upfront + (installment * 3)
    
    if calculated_total != total:
        errors.append(f"Sum check: upfront({upfront}) + installment({installment})*3 = {calculated_total}, but total = {total}")
    
    # Verify account_masked shows only last 4 digits
    account_masked = mandate.get("account_masked", "")
    if not account_masked.endswith("9012"):
        errors.append(f"account_masked: expected to end with '9012', got '{account_masked}'")
    
    if "123456789012" in account_masked:
        errors.append(f"account_masked: should not contain full account number, got '{account_masked}'")
    
    # Verify payment.plan_type == "AutoDebit"
    if payment.get("plan_type") != "AutoDebit":
        errors.append(f"payment.plan_type: expected 'AutoDebit', got {payment.get('plan_type')}")
    
    # Verify payment.mode contains "Auto-Debit"
    mode = payment.get("mode", "")
    if "Auto-Debit" not in mode:
        errors.append(f"payment.mode: expected to contain 'Auto-Debit', got '{mode}'")
    
    # Verify payment has schedule
    payment_schedule = payment.get("schedule", [])
    if not payment_schedule:
        errors.append("payment.schedule: missing or empty")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False, None
    
    print(f"\n✅ PASSED - Mandate created successfully")
    print(f"  - mandate.installments: {mandate['installments']}")
    print(f"  - mandate.schedule length: {len(schedule)}")
    print(f"  - schedule[0].status: {schedule[0]['status']}")
    print(f"  - schedule[1-3].status: {[s['status'] for s in schedule[1:]]}")
    print(f"  - upfront_amount: {upfront}")
    print(f"  - installment_amount: {installment}")
    print(f"  - total: {total}")
    print(f"  - sum check: {upfront} + {installment}*3 = {calculated_total} ✓")
    print(f"  - account_masked: {account_masked}")
    print(f"  - payment.plan_type: {payment['plan_type']}")
    print(f"  - payment.mode: {mode}")
    print(f"  - payment.schedule length: {len(payment_schedule)}")
    
    return True, payment.get("id")


def test_get_payment_by_id(token, student_id, payment_id):
    """
    Test GET /api/parent/payments/{student_id} to verify AutoDebit payment includes schedule and plan_type.
    Must be JSON-serializable (no 500 error).
    """
    print("\n" + "="*80)
    print(f"TEST: GET /api/parent/payments/{student_id} (verify payment {payment_id})")
    print("="*80)
    
    r = requests.get(
        f"{API}/parent/payments/{student_id}",
        headers=auth_header(token),
        timeout=20
    )
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False
    
    try:
        payments = r.json()
        print(f"\n✅ Response is JSON-serializable")
        print(f"Found {len(payments)} payment(s)")
        
        # Find the AutoDebit payment
        autodebit_payment = None
        for p in payments:
            if p.get("id") == payment_id or p.get("plan_type") == "AutoDebit":
                autodebit_payment = p
                break
        
        if not autodebit_payment:
            print(f"❌ FAILED: AutoDebit payment not found in response")
            return False
        
        errors = []
        
        # Verify schedule exists
        if "schedule" not in autodebit_payment:
            errors.append("AutoDebit payment missing 'schedule' field")
        
        # Verify plan_type exists
        if "plan_type" not in autodebit_payment:
            errors.append("AutoDebit payment missing 'plan_type' field")
        
        if errors:
            print(f"\n❌ FAILED:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        print(f"\n✅ PASSED - AutoDebit payment includes schedule and plan_type")
        print(f"  - plan_type: {autodebit_payment['plan_type']}")
        print(f"  - schedule length: {len(autodebit_payment.get('schedule', []))}")
        print(f"  - mode: {autodebit_payment.get('mode')}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: Error parsing JSON response: {e}")
        return False


def test_mandate_semi(token, student_id, fee_head_id, fee_name, fee_amount):
    """
    Test POST /api/parent/mandate with semi frequency.
    Verifies:
    - installments == 2
    - schedule length == 2
    """
    print("\n" + "="*80)
    print("TEST: POST /api/parent/mandate - Semi Frequency")
    print("="*80)
    print(f"Student ID: {student_id}")
    print(f"Fee Head: {fee_name} (₹{fee_amount})")
    
    payload = {
        "student_id": student_id,
        "fee_head_ids": [fee_head_id],
        "frequency": "semi",
        "rail": "UPI AutoPay",
        "bank_name": "HDFC Bank",
        "account_holder": "Anjali Sharma",
        "account_number": "987654321098",
        "ifsc": "HDFC0001234"
    }
    
    print(f"\nPayload: {payload}")
    
    r = requests.post(
        f"{API}/parent/mandate",
        json=payload,
        headers=auth_header(token),
        timeout=20
    )
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False
    
    data = r.json()
    mandate = data.get("mandate", {})
    
    errors = []
    
    # Verify mandate.installments == 2
    if mandate.get("installments") != 2:
        errors.append(f"mandate.installments: expected 2, got {mandate.get('installments')}")
    
    # Verify mandate.schedule length == 2
    schedule = mandate.get("schedule", [])
    if len(schedule) != 2:
        errors.append(f"mandate.schedule length: expected 2, got {len(schedule)}")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print(f"\n✅ PASSED - Semi-annual mandate created successfully")
    print(f"  - mandate.installments: {mandate['installments']}")
    print(f"  - mandate.schedule length: {len(schedule)}")
    print(f"  - schedule: {schedule}")
    
    return True


def test_mandate_negative_empty_fee_heads(token, student_id):
    """
    Test POST /api/parent/mandate with empty fee_head_ids.
    Should return 400.
    """
    print("\n" + "="*80)
    print("TEST: POST /api/parent/mandate - Negative: Empty fee_head_ids")
    print("="*80)
    
    payload = {
        "student_id": student_id,
        "fee_head_ids": [],
        "frequency": "quarterly",
        "rail": "UPI AutoPay",
        "bank_name": "HDFC Bank",
        "account_holder": "Anjali Sharma",
        "account_number": "123456789012",
        "ifsc": "HDFC0001234"
    }
    
    r = requests.post(
        f"{API}/parent/mandate",
        json=payload,
        headers=auth_header(token),
        timeout=20
    )
    
    if r.status_code == 400:
        print(f"✅ PASSED - Correctly returned 400 for empty fee_head_ids")
        print(f"  - Response: {r.text}")
        return True
    else:
        print(f"❌ FAILED: Expected 400, got {r.status_code}")
        print(f"  - Response: {r.text}")
        return False


def test_pay_financing_tenure_3(token, student_id, fee_head_id, fee_name, fee_amount):
    """
    Test POST /api/parent/pay-financing with tenure=3, down_payment=0.
    Verifies:
    - plan_type == "EMI"
    - tenure == 3
    - emi == ceil(amount/3)
    - schedule length == 3
    - all schedule items have status "upcoming"
    - financing == true
    """
    print("\n" + "="*80)
    print("TEST: POST /api/parent/pay-financing - tenure=3, down_payment=0")
    print("="*80)
    print(f"Student ID: {student_id}")
    print(f"Fee Head: {fee_name} (₹{fee_amount})")
    
    payload = {
        "student_id": student_id,
        "fee_head_ids": [fee_head_id],
        "tenure": 3,
        "down_payment": 0
    }
    
    print(f"\nPayload: {payload}")
    
    r = requests.post(
        f"{API}/parent/pay-financing",
        json=payload,
        headers=auth_header(token),
        timeout=20
    )
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False
    
    data = r.json()
    print(f"\nResponse: {data}")
    
    errors = []
    
    # Verify plan_type == "EMI"
    if data.get("plan_type") != "EMI":
        errors.append(f"plan_type: expected 'EMI', got {data.get('plan_type')}")
    
    # Verify tenure == 3
    if data.get("tenure") != 3:
        errors.append(f"tenure: expected 3, got {data.get('tenure')}")
    
    # Verify emi == ceil(amount/3)
    expected_emi = math.ceil(fee_amount / 3)
    if data.get("emi") != expected_emi:
        errors.append(f"emi: expected {expected_emi}, got {data.get('emi')}")
    
    # Verify schedule length == 3
    schedule = data.get("schedule", [])
    if len(schedule) != 3:
        errors.append(f"schedule length: expected 3, got {len(schedule)}")
    
    # Verify all schedule items have status "upcoming"
    for i, item in enumerate(schedule):
        if item.get("status") != "upcoming":
            errors.append(f"schedule[{i}].status: expected 'upcoming', got {item.get('status')}")
    
    # Verify financing == true
    if data.get("financing") != True:
        errors.append(f"financing: expected True, got {data.get('financing')}")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print(f"\n✅ PASSED - EMI financing created successfully")
    print(f"  - plan_type: {data['plan_type']}")
    print(f"  - tenure: {data['tenure']}")
    print(f"  - emi: {data['emi']} (expected: {expected_emi})")
    print(f"  - schedule length: {len(schedule)}")
    print(f"  - all schedule items status: {[s['status'] for s in schedule]}")
    print(f"  - financing: {data['financing']}")
    
    return True


def test_pay_financing_tenure_12_with_down(token, student_id, fee_head_id, fee_name, fee_amount):
    """
    Test POST /api/parent/pay-financing with tenure=12 and down_payment.
    Verifies:
    - tenure == 12
    - schedule length == 12
    - emi == ceil((amount - down_payment) / 12)
    """
    print("\n" + "="*80)
    print("TEST: POST /api/parent/pay-financing - tenure=12 with down_payment")
    print("="*80)
    print(f"Student ID: {student_id}")
    print(f"Fee Head: {fee_name} (₹{fee_amount})")
    
    down_payment = min(fee_amount * 0.2, 10000)  # 20% or 10000, whichever is smaller
    
    payload = {
        "student_id": student_id,
        "fee_head_ids": [fee_head_id],
        "tenure": 12,
        "down_payment": down_payment
    }
    
    print(f"\nPayload: {payload}")
    
    r = requests.post(
        f"{API}/parent/pay-financing",
        json=payload,
        headers=auth_header(token),
        timeout=20
    )
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False
    
    data = r.json()
    print(f"\nResponse: {data}")
    
    errors = []
    
    # Verify tenure == 12
    if data.get("tenure") != 12:
        errors.append(f"tenure: expected 12, got {data.get('tenure')}")
    
    # Verify schedule length == 12
    schedule = data.get("schedule", [])
    if len(schedule) != 12:
        errors.append(f"schedule length: expected 12, got {len(schedule)}")
    
    # Verify emi == ceil((amount - down_payment) / 12)
    financed_amount = fee_amount - down_payment
    expected_emi = math.ceil(financed_amount / 12)
    if data.get("emi") != expected_emi:
        errors.append(f"emi: expected {expected_emi}, got {data.get('emi')}")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print(f"\n✅ PASSED - EMI financing with down payment created successfully")
    print(f"  - tenure: {data['tenure']}")
    print(f"  - down_payment: {down_payment}")
    print(f"  - financed_amount: {financed_amount}")
    print(f"  - emi: {data['emi']} (expected: {expected_emi})")
    print(f"  - schedule length: {len(schedule)}")
    
    return True


def main():
    """Run all tests."""
    print("="*80)
    print("BiglypEnroll - Auto-Debit Mandate & EMI Financing Testing")
    print("="*80)
    
    # Login
    print("\nAuthenticating as parent@biglyp.com...")
    try:
        token = login(PARENT_EMAIL, PARENT_PASSWORD)
        print("✅ Authentication successful")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return
    
    # Get Sara Sharma and unpaid academic fees
    try:
        student_id, student_name, unpaid_fees = get_sara_sharma_unpaid_academic_fees(token)
        print(f"\n✅ Using student: {student_name} (ID: {student_id})")
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return
    
    if len(unpaid_fees) < 4:
        print(f"\n⚠️  WARNING: Need at least 4 unpaid academic fees for all tests, found {len(unpaid_fees)}")
        print("Some tests may be skipped.")
    
    results = []
    
    # FEATURE 1: Auto-Debit Mandate Tests
    print("\n" + "="*80)
    print("FEATURE 1: AUTO-DEBIT MANDATE TESTS")
    print("="*80)
    
    # Test 1: Quarterly mandate
    if len(unpaid_fees) >= 1:
        fee = unpaid_fees[0]
        success, payment_id = test_mandate_quarterly(
            token, student_id, fee["fee_head_id"], fee["name"], fee["amount"]
        )
        results.append(("Mandate - Quarterly frequency", success))
        
        # Test GET /api/parent/payments/{student_id}
        if success and payment_id:
            success = test_get_payment_by_id(token, student_id, payment_id)
            results.append(("GET /api/parent/payments/{student_id} - AutoDebit payment", success))
    else:
        print("\n⚠️  Skipping quarterly mandate test - no unpaid fees available")
    
    # Test 2: Semi mandate
    if len(unpaid_fees) >= 2:
        fee = unpaid_fees[1]
        success = test_mandate_semi(
            token, student_id, fee["fee_head_id"], fee["name"], fee["amount"]
        )
        results.append(("Mandate - Semi frequency", success))
    else:
        print("\n⚠️  Skipping semi mandate test - no unpaid fees available")
    
    # Test 3: Negative test - empty fee_head_ids
    success = test_mandate_negative_empty_fee_heads(token, student_id)
    results.append(("Mandate - Negative: empty fee_head_ids", success))
    
    # FEATURE 2: EMI Financing Tests
    print("\n" + "="*80)
    print("FEATURE 2: EMI FINANCING TESTS")
    print("="*80)
    
    # Test 4: tenure=3, down_payment=0
    if len(unpaid_fees) >= 3:
        fee = unpaid_fees[2]
        success = test_pay_financing_tenure_3(
            token, student_id, fee["fee_head_id"], fee["name"], fee["amount"]
        )
        results.append(("Pay-Financing - tenure=3, down_payment=0", success))
    else:
        print("\n⚠️  Skipping tenure=3 test - no unpaid fees available")
    
    # Test 5: tenure=12 with down_payment
    if len(unpaid_fees) >= 4:
        fee = unpaid_fees[3]
        success = test_pay_financing_tenure_12_with_down(
            token, student_id, fee["fee_head_id"], fee["name"], fee["amount"]
        )
        results.append(("Pay-Financing - tenure=12 with down_payment", success))
    else:
        print("\n⚠️  Skipping tenure=12 test - no unpaid fees available")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for description, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {description}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
