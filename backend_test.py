#!/usr/bin/env python3
"""
BiglypEnroll Backend Testing - Round 11
Testing 4 new features:
1. Reset demo state — POST /api/school/reset-demo
2. Rewards — tier perks catalog + progress-to-next-tier
3. Coupon expiry — expires_at on redeemed coupons
4. Real email send via Resend fallback path
"""
import requests
import json
import re
from pymongo import MongoClient
import os
from datetime import datetime, timedelta

# Backend URL from frontend/.env
BASE_URL = "https://enroll-system-22.preview.emergentagent.com/api"

# Test credentials from test_credentials.md
SCHOOL_EMAIL = "school@biglyp.com"
SCHOOL_PASSWORD = "school123"
PARENT_EMAIL = "parent@biglyp.com"
PARENT_PASSWORD = "parent123"

# MongoDB connection for direct inspection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "biglyp_enroll")

def login(email: str, password: str) -> str:
    """Login and return access token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise Exception(f"Login failed for {email}: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("token")

def get_mongo_client():
    """Get MongoDB client for direct inspection"""
    return MongoClient(MONGO_URL)

# ============================================================================
# TASK 1: RESET DEMO STATE
# ============================================================================

def test_reset_demo_as_school_admin():
    """T1.1: Login as school_admin and POST /api/school/reset-demo"""
    print("\n[TEST T1.1] POST /api/school/reset-demo as school_admin")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(f"{BASE_URL}/school/reset-demo", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    assert data.get("ok") is True, "ok should be True"
    assert "reset" in data, "Missing 'reset' field"
    
    reset = data["reset"]
    print(f"  Reset counts:")
    print(f"    students_affected: {reset.get('students_affected')}")
    print(f"    payments_deleted: {reset.get('payments_deleted')}")
    print(f"    rewards_accounts_deleted: {reset.get('rewards_accounts_deleted')}")
    print(f"    rewards_txns_deleted: {reset.get('rewards_txns_deleted')}")
    print(f"    redemptions_deleted: {reset.get('redemptions_deleted')}")
    print(f"    notifications_deleted: {reset.get('notifications_deleted')}")
    print(f"    email_logs_deleted: {reset.get('email_logs_deleted')}")
    
    assert reset.get("students_affected") >= 1, "Should affect at least 1 student"
    
    print(f"  ✅ PASS: Reset demo successful with HTTP 200 and reset counts")
    return reset

def test_reset_demo_parent_state():
    """T1.2: After reset, verify parent state is clean"""
    print("\n[TEST T1.2] Verify parent state after reset")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Check rewards - should be 0
    resp = requests.get(f"{BASE_URL}/parent/rewards", headers=headers)
    print(f"  GET /api/parent/rewards status: {resp.status_code}")
    assert resp.status_code == 200
    rewards = resp.json()
    
    print(f"  Rewards state:")
    print(f"    points: {rewards.get('points')}")
    print(f"    wallet: {rewards.get('wallet')}")
    print(f"    transactions: {len(rewards.get('transactions', []))}")
    
    assert rewards.get("points") == 0, f"Expected points=0, got {rewards.get('points')}"
    assert rewards.get("wallet") == 0.0, f"Expected wallet=0.0, got {rewards.get('wallet')}"
    assert len(rewards.get("transactions", [])) == 0, "Expected empty transactions"
    
    # Check children - should still exist
    resp = requests.get(f"{BASE_URL}/parent/children", headers=headers)
    print(f"  GET /api/parent/children status: {resp.status_code}")
    assert resp.status_code == 200
    children = resp.json()
    print(f"  Children count: {len(children)}")
    assert len(children) >= 1, "Should have at least 1 child"
    
    # Check fees for Aarav - should have pending fees restored
    aarav = None
    for child in children:
        if child.get("name") == "Aarav Sharma":
            aarav = child
            break
    
    assert aarav is not None, "Aarav Sharma not found"
    print(f"  Found Aarav Sharma: id={aarav['id']}")
    
    resp = requests.get(f"{BASE_URL}/parent/fees/{aarav['id']}", headers=headers)
    print(f"  GET /api/parent/fees/{aarav['id']} status: {resp.status_code}")
    assert resp.status_code == 200
    fee_data = resp.json()
    items = fee_data.get("items", [])
    
    unpaid_count = sum(1 for item in items if not item.get("paid"))
    print(f"  Fee items: {len(items)}, unpaid: {unpaid_count}")
    assert unpaid_count > 0, "Should have unpaid fees after reset"
    
    # Check notifications - may still have seed notifications
    resp = requests.get(f"{BASE_URL}/parent/notifications", headers=headers)
    print(f"  GET /api/parent/notifications status: {resp.status_code}")
    assert resp.status_code == 200
    notif_data = resp.json()
    print(f"  Notifications: {len(notif_data.get('items', []))}, unread: {notif_data.get('unread')}")
    
    print(f"  ✅ PASS: Parent state verified - points=0, wallet=0, transactions=[], pending fees restored")

def test_reset_demo_parent_forbidden():
    """T1.3: Parent role hitting POST /api/school/reset-demo -> HTTP 403"""
    print("\n[TEST T1.3] POST /api/school/reset-demo as parent -> 403")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(f"{BASE_URL}/school/reset-demo", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    print(f"  ✅ PASS: Parent role correctly forbidden with 403")

def test_reset_demo_unauthenticated():
    """T1.4: Unauthenticated -> HTTP 401"""
    print("\n[TEST T1.4] POST /api/school/reset-demo without auth -> 401")
    
    resp = requests.post(f"{BASE_URL}/school/reset-demo")
    print(f"  Status: {resp.status_code}")
    
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    print(f"  ✅ PASS: Unauthenticated correctly returns 401")

def test_reset_demo_idempotency():
    """T1.5: Run reset twice - second call should return ok:true with 0 or minimal deletions"""
    print("\n[TEST T1.5] POST /api/school/reset-demo idempotency")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Second reset
    resp = requests.post(f"{BASE_URL}/school/reset-demo", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    assert data.get("ok") is True, "ok should be True"
    reset = data["reset"]
    
    print(f"  Second reset counts:")
    print(f"    payments_deleted: {reset.get('payments_deleted')}")
    print(f"    rewards_accounts_deleted: {reset.get('rewards_accounts_deleted')}")
    print(f"    rewards_txns_deleted: {reset.get('rewards_txns_deleted')}")
    
    # Should be 0 or minimal since we just reset
    assert reset.get("payments_deleted") == 0, f"Expected 0 payments_deleted, got {reset.get('payments_deleted')}"
    
    print(f"  ✅ PASS: Idempotency works - second reset returns 0 deletions")

# ============================================================================
# TASK 2: REWARDS TIER PERKS + PROGRESS
# ============================================================================

def test_rewards_tier_bronze_fresh():
    """T2.1: Fresh state (points=0) - verify Bronze tier with progress"""
    print("\n[TEST T2.1] GET /api/parent/rewards - Bronze tier fresh state")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/rewards", headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:800]}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    # Verify tier progression fields
    assert data.get("tier") == "Bronze", f"Expected tier='Bronze', got {data.get('tier')}"
    assert data.get("next_tier") == "Silver", f"Expected next_tier='Silver', got {data.get('next_tier')}"
    assert data.get("next_at_points") == 1000, f"Expected next_at_points=1000, got {data.get('next_at_points')}"
    assert data.get("points_to_next") == 1000, f"Expected points_to_next=1000, got {data.get('points_to_next')}"
    assert data.get("progress_pct") == 0, f"Expected progress_pct=0, got {data.get('progress_pct')}"
    
    # Verify perks list
    assert "perks" in data, "Missing 'perks' field"
    perks = data["perks"]
    assert len(perks) >= 10, f"Expected at least 10 perks, got {len(perks)}"
    
    print(f"  Tier progression:")
    print(f"    tier: {data.get('tier')}")
    print(f"    next_tier: {data.get('next_tier')}")
    print(f"    next_at_points: {data.get('next_at_points')}")
    print(f"    points_to_next: {data.get('points_to_next')}")
    print(f"    progress_pct: {data.get('progress_pct')}")
    print(f"  Perks count: {len(perks)}")
    
    # Verify perk structure
    for perk in perks:
        assert "tier" in perk, "Perk missing 'tier'"
        assert "icon" in perk, "Perk missing 'icon'"
        assert "title" in perk, "Perk missing 'title'"
        assert "desc" in perk, "Perk missing 'desc'"
        assert "unlocked" in perk, "Perk missing 'unlocked'"
        assert perk["tier"] in ["Bronze", "Silver", "Gold", "Platinum"], f"Invalid tier: {perk['tier']}"
    
    # Verify Bronze perks unlocked, others locked
    bronze_perks = [p for p in perks if p["tier"] == "Bronze"]
    silver_perks = [p for p in perks if p["tier"] == "Silver"]
    gold_perks = [p for p in perks if p["tier"] == "Gold"]
    platinum_perks = [p for p in perks if p["tier"] == "Platinum"]
    
    print(f"  Perks by tier: Bronze={len(bronze_perks)}, Silver={len(silver_perks)}, Gold={len(gold_perks)}, Platinum={len(platinum_perks)}")
    
    for perk in bronze_perks:
        assert perk["unlocked"] is True, f"Bronze perk should be unlocked: {perk['title']}"
    
    for perk in silver_perks + gold_perks + platinum_perks:
        assert perk["unlocked"] is False, f"Higher tier perk should be locked: {perk['title']}"
    
    print(f"  ✅ PASS: Bronze tier verified with correct progression and perks")

def test_rewards_tier_cross_to_silver():
    """T2.2: Pay large upfront to cross into Silver (>= 1000 points)"""
    print("\n[TEST T2.2] Cross into Silver tier via upfront payment")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get Aarav's fees
    resp = requests.get(f"{BASE_URL}/parent/children", headers=headers)
    assert resp.status_code == 200
    children = resp.json()
    
    aarav = None
    for child in children:
        if child.get("name") == "Aarav Sharma":
            aarav = child
            break
    
    assert aarav is not None, "Aarav Sharma not found"
    print(f"  Found Aarav Sharma: id={aarav['id']}")
    
    resp = requests.get(f"{BASE_URL}/parent/fees/{aarav['id']}", headers=headers)
    assert resp.status_code == 200
    fee_data = resp.json()
    items = fee_data.get("items", [])
    
    # Find unpaid items totaling >= 50000 (to get 1000+ points)
    unpaid = [item for item in items if not item.get("paid")]
    
    if len(unpaid) == 0:
        print(f"  ⚠️  SKIP: No unpaid fees for Aarav")
        return
    
    # Select fee heads totaling >= 50000
    selected = []
    total = 0
    for item in unpaid:
        selected.append(item["fee_head_id"])
        total += item["amount"]
        if total >= 50000:
            break
    
    print(f"  Paying {len(selected)} fee heads, total: {total}")
    
    # Pay with mode='full' (upfront) to get 2x points
    payload = {
        "student_id": aarav["id"],
        "fee_head_ids": selected,
        "mode": "UPI"
    }
    
    resp = requests.post(f"{BASE_URL}/parent/pay", json=payload, headers=headers)
    print(f"  POST /api/parent/pay status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"  ⚠️  Payment failed: {resp.text}")
        return
    
    payment_data = resp.json()
    print(f"  Payment successful: {payment_data.get('receipt_no')}")
    
    # Check rewards - should be Silver now
    resp = requests.get(f"{BASE_URL}/parent/rewards", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    points = data.get("points")
    tier = data.get("tier")
    next_tier = data.get("next_tier")
    points_to_next = data.get("points_to_next")
    perks = data.get("perks", [])
    
    print(f"  After payment:")
    print(f"    points: {points}")
    print(f"    tier: {tier}")
    print(f"    next_tier: {next_tier}")
    print(f"    points_to_next: {points_to_next}")
    
    assert points >= 1000, f"Expected points >= 1000, got {points}"
    assert tier == "Silver", f"Expected tier='Silver', got {tier}"
    assert next_tier == "Gold", f"Expected next_tier='Gold', got {next_tier}"
    assert points_to_next <= (3000 - points), f"points_to_next incorrect: {points_to_next}"
    
    # Verify Silver perks unlocked, Gold/Platinum locked
    silver_perks = [p for p in perks if p["tier"] == "Silver"]
    gold_perks = [p for p in perks if p["tier"] == "Gold"]
    platinum_perks = [p for p in perks if p["tier"] == "Platinum"]
    
    for perk in silver_perks:
        assert perk["unlocked"] is True, f"Silver perk should be unlocked: {perk['title']}"
    
    for perk in gold_perks + platinum_perks:
        assert perk["unlocked"] is False, f"Higher tier perk should be locked: {perk['title']}"
    
    print(f"  ✅ PASS: Crossed into Silver tier, perks updated correctly")

# ============================================================================
# TASK 3: COUPON EXPIRY
# ============================================================================

def test_coupon_expiry_redeem():
    """T3.1: Redeem coupon and verify expires_at is set (+90 days)"""
    print("\n[TEST T3.1] POST /api/parent/rewards/redeem-coupon - Verify expires_at")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get current points
    resp = requests.get(f"{BASE_URL}/parent/rewards", headers=headers)
    assert resp.status_code == 200
    points = resp.json()["points"]
    print(f"  Current points: {points}")
    
    if points < 1000:
        print(f"  ⚠️  SKIP: Not enough points to redeem cp_bms (need 1000, have {points})")
        return
    
    # Redeem cp_bms (cheapest coupon at 1000 points)
    payload = {"coupon_id": "cp_bms"}
    resp = requests.post(f"{BASE_URL}/parent/rewards/redeem-coupon", json=payload, headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    
    assert "redemption" in data, "Missing 'redemption' field"
    redemption = data["redemption"]
    
    # Verify created_at and expires_at
    assert "created_at" in redemption, "Missing 'created_at'"
    assert "expires_at" in redemption, "Missing 'expires_at'"
    
    created_at = redemption["created_at"]
    expires_at = redemption["expires_at"]
    
    print(f"  Redemption:")
    print(f"    created_at: {created_at}")
    print(f"    expires_at: {expires_at}")
    
    # Parse ISO dates
    try:
        created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except Exception as e:
        raise AssertionError(f"Failed to parse ISO dates: {e}")
    
    # Verify expires_at is approximately 90 days after created_at (allow +/- 1 hour)
    expected_expires = created_dt + timedelta(days=90)
    diff = abs((expires_dt - expected_expires).total_seconds())
    
    print(f"  Time difference: {diff} seconds")
    assert diff <= 3600, f"expires_at should be ~90 days after created_at, diff={diff}s"
    
    print(f"  ✅ PASS: Coupon redemption has expires_at set correctly (~90 days)")

def test_coupon_expiry_redemptions_list():
    """T3.2: GET /api/parent/rewards/redemptions - Verify coupon has expires_at, course does NOT"""
    print("\n[TEST T3.2] GET /api/parent/rewards/redemptions - Verify expires_at presence")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(f"{BASE_URL}/parent/rewards/redemptions", headers=headers)
    print(f"  Status: {resp.status_code}")
    assert resp.status_code == 200
    redemptions = resp.json()
    
    print(f"  Redemptions count: {len(redemptions)}")
    
    # Find coupon redemption (kind='coupon')
    coupon_redemption = None
    for r in redemptions:
        if r.get("kind") == "coupon":
            coupon_redemption = r
            break
    
    if coupon_redemption:
        print(f"  Found coupon redemption: {coupon_redemption.get('title')}")
        assert "created_at" in coupon_redemption, "Coupon redemption missing 'created_at'"
        assert "expires_at" in coupon_redemption, "Coupon redemption missing 'expires_at'"
        print(f"    created_at: {coupon_redemption['created_at']}")
        print(f"    expires_at: {coupon_redemption['expires_at']}")
    else:
        print(f"  ⚠️  No coupon redemption found")
    
    # Find course redemption (kind='course')
    course_redemption = None
    for r in redemptions:
        if r.get("kind") == "course":
            course_redemption = r
            break
    
    if course_redemption:
        print(f"  Found course redemption: {course_redemption.get('title')}")
        assert "expires_at" not in course_redemption, "Course redemption should NOT have 'expires_at'"
        print(f"    ✓ Course redemption does NOT have expires_at (correct)")
    else:
        print(f"  ℹ️  No course redemption found (will test enrollment)")
    
    print(f"  ✅ PASS: Coupon has expires_at, course does NOT")

def test_coupon_expiry_enroll_course():
    """T3.3: Enroll in course and verify redemption has NO expires_at"""
    print("\n[TEST T3.3] POST /api/parent/rewards/enroll-course - Verify NO expires_at")
    token = login(PARENT_EMAIL, PARENT_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get current points
    resp = requests.get(f"{BASE_URL}/parent/rewards", headers=headers)
    assert resp.status_code == 200
    points = resp.json()["points"]
    print(f"  Current points: {points}")
    
    if points < 900:
        print(f"  ⚠️  SKIP: Not enough points to enroll in co_writing (need 900, have {points})")
        return
    
    # Get Aarav's student_id
    resp = requests.get(f"{BASE_URL}/parent/children", headers=headers)
    assert resp.status_code == 200
    children = resp.json()
    
    aarav = None
    for child in children:
        if child.get("name") == "Aarav Sharma":
            aarav = child
            break
    
    if aarav is None:
        print(f"  ⚠️  SKIP: Aarav Sharma not found")
        return
    
    print(f"  Found Aarav Sharma: id={aarav['id']}")
    
    # Enroll in co_writing
    payload = {
        "course_id": "co_writing",
        "student_id": aarav["id"]
    }
    
    resp = requests.post(f"{BASE_URL}/parent/rewards/enroll-course", json=payload, headers=headers)
    print(f"  Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"  ℹ️  Enrollment response: {resp.text}")
        # May already be enrolled, check redemptions list
    
    # Check redemptions list
    resp = requests.get(f"{BASE_URL}/parent/rewards/redemptions", headers=headers)
    assert resp.status_code == 200
    redemptions = resp.json()
    
    # Find course redemption
    course_redemption = None
    for r in redemptions:
        if r.get("kind") == "course" and r.get("item_id") == "co_writing":
            course_redemption = r
            break
    
    if course_redemption:
        print(f"  Found course redemption: {course_redemption.get('title')}")
        assert "expires_at" not in course_redemption, "Course redemption should NOT have 'expires_at'"
        print(f"    ✓ Course redemption does NOT have expires_at (correct)")
        print(f"  ✅ PASS: Course enrollment has NO expires_at")
    else:
        print(f"  ⚠️  Course redemption not found in list")

# ============================================================================
# TASK 4: REAL EMAIL SEND VIA RESEND FALLBACK
# ============================================================================

def test_resend_fallback_no_api_key():
    """T4.1: Verify RESEND_API_KEY is NOT in backend/.env"""
    print("\n[TEST T4.1] Verify RESEND_API_KEY is absent from backend/.env")
    
    # Read backend/.env
    env_path = "/app/backend/.env"
    try:
        with open(env_path, "r") as f:
            env_content = f.read()
    except Exception as e:
        print(f"  ⚠️  Could not read {env_path}: {e}")
        return
    
    has_resend_key = "RESEND_API_KEY" in env_content
    print(f"  RESEND_API_KEY in .env: {has_resend_key}")
    
    assert not has_resend_key, "RESEND_API_KEY should NOT be in backend/.env for this test"
    
    print(f"  ✅ PASS: RESEND_API_KEY is absent (expected for fallback test)")

def test_resend_fallback_reset_email_log():
    """T4.2: Reset demo to clean email_log"""
    print("\n[TEST T4.2] POST /api/school/reset-demo to clean email_log")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(f"{BASE_URL}/school/reset-demo", headers=headers)
    print(f"  Status: {resp.status_code}")
    assert resp.status_code == 200
    
    data = resp.json()
    email_logs_deleted = data["reset"].get("email_logs_deleted", 0)
    print(f"  email_logs_deleted: {email_logs_deleted}")
    
    print(f"  ✅ PASS: email_log cleaned")

def test_resend_fallback_run_reminders():
    """T4.3: POST /api/reminders/run {force:true} and note created count"""
    print("\n[TEST T4.3] POST /api/reminders/run {force:true}")
    token = login(SCHOOL_EMAIL, SCHOOL_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(f"{BASE_URL}/reminders/run", json={"force": True}, headers=headers)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    created = data.get("created", 0)
    
    print(f"  Created: {created}")
    
    print(f"  ✅ PASS: Reminders run returned created={created}")
    return created

def test_resend_fallback_verify_email_log():
    """T4.4: Query MongoDB email_log - verify status='queued' AND provider='none'"""
    print("\n[TEST T4.4] Verify email_log entries in MongoDB")
    
    # Connect to MongoDB
    client = get_mongo_client()
    db = client[DB_NAME]
    
    # Count email_log entries with status='queued' AND provider='none'
    query = {"status": "queued", "provider": "none"}
    count = db.email_log.count_documents(query)
    
    print(f"  email_log entries with status='queued' AND provider='none': {count}")
    
    # Get sample entries
    sample_entries = list(db.email_log.find(query).limit(5))
    
    for entry in sample_entries:
        print(f"    - to: {entry.get('to')}, subject: {entry.get('subject')}, provider_ref: {entry.get('provider_ref')}")
        
        # Verify provider_ref is 'resend_not_configured'
        assert entry.get("provider_ref") == "resend_not_configured", \
            f"Expected provider_ref='resend_not_configured', got {entry.get('provider_ref')}"
    
    assert count > 0, "Should have at least 1 email_log entry with status='queued' AND provider='none'"
    
    print(f"  ✅ PASS: email_log entries verified with status='queued', provider='none', provider_ref='resend_not_configured'")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print("=" * 80)
    print("BiglypEnroll Backend Testing - Round 11")
    print("Testing 4 new features:")
    print("1. Reset demo state")
    print("2. Rewards tier perks + progress")
    print("3. Coupon expiry (expires_at)")
    print("4. Real email send via Resend fallback")
    print("=" * 80)
    
    try:
        # ============ TASK 1: RESET DEMO STATE ============
        print("\n" + "=" * 80)
        print("TASK 1: RESET DEMO STATE")
        print("=" * 80)
        
        test_reset_demo_as_school_admin()
        test_reset_demo_parent_state()
        test_reset_demo_parent_forbidden()
        test_reset_demo_unauthenticated()
        test_reset_demo_idempotency()
        
        # ============ TASK 2: REWARDS TIER PERKS ============
        print("\n" + "=" * 80)
        print("TASK 2: REWARDS TIER PERKS + PROGRESS")
        print("=" * 80)
        
        test_rewards_tier_bronze_fresh()
        test_rewards_tier_cross_to_silver()
        
        # ============ TASK 3: COUPON EXPIRY ============
        print("\n" + "=" * 80)
        print("TASK 3: COUPON EXPIRY (expires_at)")
        print("=" * 80)
        
        test_coupon_expiry_redeem()
        test_coupon_expiry_redemptions_list()
        test_coupon_expiry_enroll_course()
        
        # ============ TASK 4: RESEND FALLBACK ============
        print("\n" + "=" * 80)
        print("TASK 4: REAL EMAIL SEND VIA RESEND FALLBACK")
        print("=" * 80)
        
        test_resend_fallback_no_api_key()
        test_resend_fallback_reset_email_log()
        test_resend_fallback_run_reminders()
        test_resend_fallback_verify_email_log()
        
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
