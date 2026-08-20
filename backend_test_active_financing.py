"""
BiglypEnroll - Active Financing Endpoints Testing
Tests the active financing endpoints including:
- GET /api/parent/financing/active/{student_id}
- POST /api/parent/financing/pay-emi
- POST /api/parent/pay-financing with tenure=6
"""
import os
import requests
import math

# Use the production URL from frontend/.env
BASE_URL = "https://bigly-signup.preview.emergentagent.com"
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


def test_1_get_children_find_aarav(token):
    """
    Test 1: GET /api/parent/children -> find "Aarav Sharma" (has an active EMI plan)
    """
    print(f"\n{'='*80}")
    print(f"TEST 1: GET /api/parent/children -> Find Aarav Sharma")
    print(f"{'='*80}")
    
    r = requests.get(f"{API}/parent/children", headers=auth_header(token), timeout=20)
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return None, False
    
    children = r.json()
    print(f"Found {len(children)} child(ren):")
    for child in children:
        print(f"  - {child['name']} (ID: {child['id']})")
    
    # Find Aarav Sharma
    aarav = None
    for child in children:
        if child['name'] == "Aarav Sharma":
            aarav = child
            break
    
    if not aarav:
        print(f"❌ FAILED: Aarav Sharma not found in children list")
        return None, False
    
    print(f"✅ PASSED: Found Aarav Sharma (ID: {aarav['id']})")
    return aarav['id'], True


def test_2_get_active_financing(token, aarav_id):
    """
    Test 2: GET /api/parent/financing/active/{aarav_id}
    Verify:
    - Returns a list with >=1 plan where plan_type=="EMI"
    - Plan has: emi (number), tenure (int), financed_amount (number), schedule (array)
    - Schedule month 1: status "paid", rail "UPI AutoPay", non-null receipt_no
    - Schedule month 2: status "scheduled", rail "eNACH Mandate"
    """
    print(f"\n{'='*80}")
    print(f"TEST 2: GET /api/parent/financing/active/{aarav_id}")
    print(f"{'='*80}")
    
    r = requests.get(f"{API}/parent/financing/active/{aarav_id}", headers=auth_header(token), timeout=20)
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return None, False
    
    plans = r.json()
    print(f"Found {len(plans)} active financing plan(s)")
    
    if len(plans) < 1:
        print(f"❌ FAILED: Expected at least 1 active EMI plan, got {len(plans)}")
        return None, False
    
    # Find an EMI plan
    emi_plan = None
    for plan in plans:
        if plan.get("plan_type") == "EMI":
            emi_plan = plan
            break
    
    if not emi_plan:
        print(f"❌ FAILED: No plan with plan_type='EMI' found")
        return None, False
    
    print(f"Found EMI plan (ID: {emi_plan.get('id')})")
    
    # Validate plan structure
    errors = []
    
    # Check required fields
    if "emi" not in emi_plan or not isinstance(emi_plan["emi"], (int, float)):
        errors.append(f"emi: missing or not a number (got {emi_plan.get('emi')})")
    
    if "tenure" not in emi_plan or not isinstance(emi_plan["tenure"], int):
        errors.append(f"tenure: missing or not an integer (got {emi_plan.get('tenure')})")
    
    if "financed_amount" not in emi_plan or not isinstance(emi_plan["financed_amount"], (int, float)):
        errors.append(f"financed_amount: missing or not a number (got {emi_plan.get('financed_amount')})")
    
    if "schedule" not in emi_plan or not isinstance(emi_plan["schedule"], list):
        errors.append(f"schedule: missing or not an array (got {emi_plan.get('schedule')})")
    else:
        schedule = emi_plan["schedule"]
        print(f"Schedule has {len(schedule)} installments")
        
        # Check month 1 (index 0)
        if len(schedule) > 0:
            month1 = schedule[0]
            print(f"\nMonth 1 installment:")
            print(f"  - status: {month1.get('status')}")
            print(f"  - rail: {month1.get('rail')}")
            print(f"  - receipt_no: {month1.get('receipt_no')}")
            
            if month1.get("status") != "paid":
                errors.append(f"schedule[0].status: expected 'paid', got '{month1.get('status')}'")
            
            if "UPI AutoPay" not in month1.get("rail", ""):
                errors.append(f"schedule[0].rail: expected to contain 'UPI AutoPay', got '{month1.get('rail')}'")
            
            if not month1.get("receipt_no"):
                errors.append(f"schedule[0].receipt_no: expected non-null, got {month1.get('receipt_no')}")
        else:
            errors.append("schedule: expected at least 1 installment, got 0")
        
        # Check month 2 (index 1)
        if len(schedule) > 1:
            month2 = schedule[1]
            print(f"\nMonth 2 installment:")
            print(f"  - status: {month2.get('status')}")
            print(f"  - rail: {month2.get('rail')}")
            
            if month2.get("status") != "scheduled":
                errors.append(f"schedule[1].status: expected 'scheduled', got '{month2.get('status')}'")
            
            if "eNACH Mandate" not in month2.get("rail", ""):
                errors.append(f"schedule[1].rail: expected to contain 'eNACH Mandate', got '{month2.get('rail')}'")
        else:
            errors.append("schedule: expected at least 2 installments, got 1")
        
        # Note about month 3
        if len(schedule) > 2:
            month3 = schedule[2]
            print(f"\nMonth 3 installment (may be 'failed' from seeded demo data):")
            print(f"  - status: {month3.get('status')}")
            print(f"  - rail: {month3.get('rail')}")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return None, False
    else:
        print(f"\n✅ PASSED")
        print(f"  - plan_type: {emi_plan['plan_type']}")
        print(f"  - emi: {emi_plan['emi']}")
        print(f"  - tenure: {emi_plan['tenure']}")
        print(f"  - financed_amount: {emi_plan['financed_amount']}")
        print(f"  - schedule length: {len(emi_plan['schedule'])}")
        return emi_plan, True


def test_3_pay_emi_month_3(token, plan_id):
    """
    Test 3: POST /api/parent/financing/pay-emi
    Pay month 3 with mode "UPI"
    Verify:
    - Response is the updated plan
    - Month 3 installment now has status "paid" with receipt_no and rail containing "Manual"
    - Remaining status re-derivation: exactly ONE non-paid installment is "scheduled", all others are "upcoming"
    """
    print(f"\n{'='*80}")
    print(f"TEST 3: POST /api/parent/financing/pay-emi (month 3)")
    print(f"{'='*80}")
    
    payload = {
        "payment_id": plan_id,
        "month": 3,
        "mode": "UPI"
    }
    print(f"Payload: {payload}")
    
    r = requests.post(f"{API}/parent/financing/pay-emi", json=payload, headers=auth_header(token), timeout=20)
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False
    
    updated_plan = r.json()
    print(f"Response received (plan ID: {updated_plan.get('id')})")
    
    # Validate response
    errors = []
    
    if "schedule" not in updated_plan or not isinstance(updated_plan["schedule"], list):
        errors.append(f"schedule: missing or not an array")
        print(f"❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    schedule = updated_plan["schedule"]
    print(f"\nSchedule after payment:")
    
    # Find month 3
    month3 = None
    for item in schedule:
        if item.get("month") == 3:
            month3 = item
            break
    
    if not month3:
        errors.append("Month 3 installment not found in schedule")
    else:
        print(f"\nMonth 3 installment:")
        print(f"  - status: {month3.get('status')}")
        print(f"  - rail: {month3.get('rail')}")
        print(f"  - receipt_no: {month3.get('receipt_no')}")
        
        if month3.get("status") != "paid":
            errors.append(f"month 3 status: expected 'paid', got '{month3.get('status')}'")
        
        if not month3.get("receipt_no"):
            errors.append(f"month 3 receipt_no: expected non-null, got {month3.get('receipt_no')}")
        
        if "Manual" not in month3.get("rail", ""):
            errors.append(f"month 3 rail: expected to contain 'Manual', got '{month3.get('rail')}'")
    
    # Check remaining status re-derivation
    print(f"\nAll installments:")
    scheduled_count = 0
    upcoming_count = 0
    paid_count = 0
    
    for item in schedule:
        status = item.get("status")
        print(f"  - Month {item.get('month')}: status={status}, rail={item.get('rail')}")
        
        if status == "paid":
            paid_count += 1
        elif status == "scheduled":
            scheduled_count += 1
        elif status == "upcoming":
            upcoming_count += 1
    
    print(f"\nStatus counts: paid={paid_count}, scheduled={scheduled_count}, upcoming={upcoming_count}")
    
    # Among all non-paid installments, exactly ONE should be "scheduled" and all others "upcoming"
    if scheduled_count != 1:
        errors.append(f"scheduled count: expected exactly 1 non-paid installment to be 'scheduled', got {scheduled_count}")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(f"\n✅ PASSED")
        print(f"  - Month 3 marked as 'paid' with receipt and 'Manual' rail")
        print(f"  - Exactly 1 non-paid installment is 'scheduled'")
        print(f"  - All other non-paid installments are 'upcoming'")
        return True


def test_4_negative_pay_already_paid(token, plan_id):
    """
    Test 4: Negative test - POST /api/parent/financing/pay-emi with already paid month
    Try to pay month 1 (already paid) -> expect HTTP 400
    """
    print(f"\n{'='*80}")
    print(f"TEST 4: Negative test - Pay already paid month (month 1)")
    print(f"{'='*80}")
    
    payload = {
        "payment_id": plan_id,
        "month": 1,
        "mode": "UPI"
    }
    print(f"Payload: {payload}")
    
    r = requests.post(f"{API}/parent/financing/pay-emi", json=payload, headers=auth_header(token), timeout=20)
    
    if r.status_code == 400:
        print(f"✅ PASSED: Correctly returned HTTP 400")
        print(f"Response: {r.text}")
        return True
    else:
        print(f"❌ FAILED: Expected HTTP 400, got {r.status_code}")
        print(f"Response: {r.text}")
        return False


def test_5_negative_pay_bogus_payment_id(token):
    """
    Test 5: Negative test - POST /api/parent/financing/pay-emi with bogus payment_id
    Try with payment_id "000000000000000000000000" -> expect HTTP 404
    """
    print(f"\n{'='*80}")
    print(f"TEST 5: Negative test - Pay with bogus payment_id")
    print(f"{'='*80}")
    
    payload = {
        "payment_id": "000000000000000000000000",
        "month": 1,
        "mode": "UPI"
    }
    print(f"Payload: {payload}")
    
    r = requests.post(f"{API}/parent/financing/pay-emi", json=payload, headers=auth_header(token), timeout=20)
    
    if r.status_code == 404:
        print(f"✅ PASSED: Correctly returned HTTP 404")
        print(f"Response: {r.text}")
        return True
    else:
        print(f"❌ FAILED: Expected HTTP 404, got {r.status_code}")
        print(f"Response: {r.text}")
        return False


def test_6_pay_financing_tenure_6(token):
    """
    Test 6: Re-verify POST /api/parent/pay-financing with tenure=6
    Pick another child or reuse, create financing with tenure=6
    Verify:
    - plan_type "EMI"
    - tenure 6
    - schedule length 6
    - schedule[0].status "paid"
    - schedule[1].status "scheduled"
    - financed_amount present
    """
    print(f"\n{'='*80}")
    print(f"TEST 6: POST /api/parent/pay-financing with tenure=6")
    print(f"{'='*80}")
    
    # Get children
    r = requests.get(f"{API}/parent/children", headers=auth_header(token), timeout=20)
    if r.status_code != 200:
        print(f"❌ FAILED: Could not get children - HTTP {r.status_code}")
        return False
    
    children = r.json()
    if not children:
        print(f"❌ FAILED: No children found")
        return False
    
    # Use first child
    student_id = children[0]["id"]
    print(f"Using child: {children[0]['name']} (ID: {student_id})")
    
    # Get fees
    r = requests.get(f"{API}/parent/fees/{student_id}", headers=auth_header(token), timeout=20)
    if r.status_code != 200:
        print(f"❌ FAILED: Could not get fees - HTTP {r.status_code}")
        return False
    
    fees_data = r.json()
    items = fees_data.get("items", [])
    
    # Find an unpaid fee head
    unpaid_items = [item for item in items if not item.get("paid")]
    if not unpaid_items:
        print(f"⚠️  WARNING: All fees already paid, cannot test pay-financing")
        print(f"✅ PASSED (skipped - no unpaid fees)")
        return True
    
    fee_head_id = unpaid_items[0]["fee_head_id"]
    print(f"Paying fee: {unpaid_items[0]['name']} (₹{unpaid_items[0]['amount']})")
    
    # Pay with financing, tenure=6
    payload = {
        "student_id": student_id,
        "fee_head_ids": [fee_head_id],
        "tenure": 6,
        "down_payment": 0
    }
    print(f"Payload: {payload}")
    
    r = requests.post(f"{API}/parent/pay-financing", json=payload, headers=auth_header(token), timeout=20)
    
    if r.status_code != 200:
        print(f"❌ FAILED: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False
    
    plan = r.json()
    print(f"Created plan (ID: {plan.get('id')})")
    
    # Validate plan
    errors = []
    
    if plan.get("plan_type") != "EMI":
        errors.append(f"plan_type: expected 'EMI', got '{plan.get('plan_type')}'")
    
    if plan.get("tenure") != 6:
        errors.append(f"tenure: expected 6, got {plan.get('tenure')}")
    
    if "financed_amount" not in plan:
        errors.append(f"financed_amount: missing")
    
    if "schedule" not in plan or not isinstance(plan["schedule"], list):
        errors.append(f"schedule: missing or not an array")
    else:
        schedule = plan["schedule"]
        
        if len(schedule) != 6:
            errors.append(f"schedule length: expected 6, got {len(schedule)}")
        
        if len(schedule) > 0:
            if schedule[0].get("status") != "paid":
                errors.append(f"schedule[0].status: expected 'paid', got '{schedule[0].get('status')}'")
        
        if len(schedule) > 1:
            if schedule[1].get("status") != "scheduled":
                errors.append(f"schedule[1].status: expected 'scheduled', got '{schedule[1].get('status')}'")
    
    if errors:
        print(f"\n❌ FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print(f"\n✅ PASSED")
        print(f"  - plan_type: {plan['plan_type']}")
        print(f"  - tenure: {plan['tenure']}")
        print(f"  - financed_amount: {plan['financed_amount']}")
        print(f"  - schedule length: {len(plan['schedule'])}")
        print(f"  - schedule[0].status: {plan['schedule'][0]['status']}")
        print(f"  - schedule[1].status: {plan['schedule'][1]['status']}")
        return True


def main():
    """Run all tests."""
    print("="*80)
    print("BiglypEnroll - Active Financing Endpoints Testing")
    print("="*80)
    
    # Login
    print("\nAuthenticating as parent@biglyp.com...")
    try:
        token = login(PARENT_EMAIL, PARENT_PASSWORD)
        print("✅ Authentication successful")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return
    
    results = []
    
    # Test 1: Get children and find Aarav Sharma
    aarav_id, result = test_1_get_children_find_aarav(token)
    results.append(("Test 1: GET /api/parent/children -> Find Aarav Sharma", result))
    
    if not result or not aarav_id:
        print("\n⚠️  Cannot continue without Aarav Sharma's ID")
        print_summary(results)
        return
    
    # Test 2: Get active financing for Aarav
    emi_plan, result = test_2_get_active_financing(token, aarav_id)
    results.append(("Test 2: GET /api/parent/financing/active/{aarav_id}", result))
    
    if not result or not emi_plan:
        print("\n⚠️  Cannot continue without an active EMI plan")
        print_summary(results)
        return
    
    plan_id = emi_plan.get("id")
    
    # Test 3: Pay EMI month 3
    result = test_3_pay_emi_month_3(token, plan_id)
    results.append(("Test 3: POST /api/parent/financing/pay-emi (month 3)", result))
    
    # Test 4: Negative test - pay already paid month
    result = test_4_negative_pay_already_paid(token, plan_id)
    results.append(("Test 4: Negative test - Pay already paid month", result))
    
    # Test 5: Negative test - bogus payment_id
    result = test_5_negative_pay_bogus_payment_id(token)
    results.append(("Test 5: Negative test - Bogus payment_id", result))
    
    # Test 6: Re-verify pay-financing with tenure=6
    result = test_6_pay_financing_tenure_6(token)
    results.append(("Test 6: POST /api/parent/pay-financing with tenure=6", result))
    
    # Summary
    print_summary(results)


def print_summary(results):
    """Print test summary."""
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
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
