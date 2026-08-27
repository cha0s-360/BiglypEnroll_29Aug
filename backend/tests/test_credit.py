"""Backend tests for BiglypEnroll — Credit Assessment & Loan Origination module.

Uses pytest. Requires the app to be running via supervisor at REACT_APP_BACKEND_URL.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://github-preview-63.preview.emergentagent.com").rstrip("/")
API = BASE_URL + "/api"

CREDENTIALS = {
    "super_admin": ("admin@biglyp.com", "admin123"),
    "credit_ops": ("creditops@biglyp.com", "creditops123"),
    "lender": ("lender@biglyp.com", "lender123"),
    "school_admin": ("school@biglyp.com", "school123"),
    "parent": ("parent@biglyp.com", "parent123"),
}


# -------------------------------------------------- helpers --------------------
def login(role):
    email, pw = CREDENTIALS[role]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"login failed for {role}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def hdrs(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens():
    # Prime the seed by hitting a credit endpoint
    admin_tok = login("super_admin")
    requests.get(f"{API}/credit/lenders", headers=hdrs(admin_tok))
    return {r: login(r) for r in CREDENTIALS}


# --------------------------------------------------- auth / rbac ---------------
class TestCreditRBAC:
    def test_all_roles_login(self, tokens):
        assert all(tokens[r] for r in CREDENTIALS)

    def test_parent_forbidden_on_credit(self, tokens):
        for path in ["/credit/lenders", "/credit/applications", "/credit/dashboard", "/credit/config"]:
            r = requests.get(f"{API}{path}", headers=hdrs(tokens["parent"]))
            assert r.status_code == 403, f"{path} should be 403 for parent, got {r.status_code}"

    def test_lender_can_list_lenders_and_apps(self, tokens):
        r = requests.get(f"{API}/credit/lenders", headers=hdrs(tokens["lender"]))
        assert r.status_code == 200
        r = requests.get(f"{API}/credit/applications", headers=hdrs(tokens["lender"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# -------------------------------------------------- lenders / config -----------
class TestLendersConfig:
    def test_four_default_lenders(self, tokens):
        r = requests.get(f"{API}/credit/lenders", headers=hdrs(tokens["super_admin"]))
        assert r.status_code == 200
        lenders = r.json()
        names = {l["name"] for l in lenders}
        for expected in ["Axis Bank", "HDFC Bank", "ICICI Bank"]:
            assert expected in names, f"missing lender {expected}"
        assert any("Aditya Birla" in n for n in names)
        assert len(lenders) >= 4

    def test_update_hdfc_min_cibil_persists(self, tokens):
        r = requests.get(f"{API}/credit/lenders", headers=hdrs(tokens["super_admin"]))
        hdfc = next(l for l in r.json() if l["name"] == "HDFC Bank")
        original = hdfc["policy"]["min_cibil"]
        new_val = 740
        hdfc["policy"]["min_cibil"] = new_val
        body = {"name": hdfc["name"], "type": hdfc["type"], "color": hdfc["color"],
                "active": hdfc["active"], "policy": hdfc["policy"]}
        u = requests.put(f"{API}/credit/lenders/{hdfc['id']}", json=body, headers=hdrs(tokens["super_admin"]))
        assert u.status_code == 200
        assert u.json()["policy"]["min_cibil"] == new_val
        # revert
        hdfc["policy"]["min_cibil"] = original
        body["policy"] = hdfc["policy"]
        requests.put(f"{API}/credit/lenders/{hdfc['id']}", json=body, headers=hdrs(tokens["super_admin"]))

    def test_lender_update_forbidden_for_school_admin(self, tokens):
        r = requests.get(f"{API}/credit/lenders", headers=hdrs(tokens["super_admin"]))
        hdfc = next(l for l in r.json() if l["name"] == "HDFC Bank")
        body = {"name": hdfc["name"], "type": hdfc["type"], "color": hdfc["color"],
                "active": hdfc["active"], "policy": hdfc["policy"]}
        u = requests.put(f"{API}/credit/lenders/{hdfc['id']}", json=body, headers=hdrs(tokens["school_admin"]))
        assert u.status_code == 403

    def test_config_weights_get_put(self, tokens):
        r = requests.get(f"{API}/credit/config", headers=hdrs(tokens["super_admin"]))
        assert r.status_code == 200
        cfg = r.json()
        weights = cfg["internal_score_weights"]
        s = sum(weights.values())
        assert 0.99 <= s <= 1.01, f"weights should sum ~1.0 got {s}"

        # Update commission and put back
        new_body = {"internal_score_weights": weights, "biglyp_commission_pct": 1.75}
        u = requests.put(f"{API}/credit/config", json=new_body, headers=hdrs(tokens["super_admin"]))
        assert u.status_code == 200
        assert u.json()["biglyp_commission_pct"] == 1.75
        # revert
        requests.put(f"{API}/credit/config", json={"internal_score_weights": weights,
                     "biglyp_commission_pct": cfg.get("biglyp_commission_pct", 1.5)},
                     headers=hdrs(tokens["super_admin"]))


# -------------------------------------------------- application pipeline -------
def _mk_app(token, applicant_over=None, fee_over=None):
    applicant = {
        "name": "TEST Strong Applicant",
        "pan": "TESTS" + uuid.uuid4().hex[:4].upper() + "K",
        "aadhaar": "123412341234",
        "monthly_income": 90000,
        "employment_type": "salaried",
        "age": 38,
        "geography": "Metro",
        "mobile": "9" + uuid.uuid4().hex[:9],
    }
    if applicant_over:
        applicant.update(applicant_over)
    fee = {"loan_amount": 200000, "tenure_months": 12, "subvention_model": "parent_100"}
    if fee_over:
        fee.update(fee_over)
    body = {
        "student": {"name": "TEST Kid", "grade": "Grade 10"},
        "applicant": applicant,
        "co_applicant": {},
        "fee": fee,
    }
    r = requests.post(f"{API}/credit/applications", json=body, headers=hdrs(token))
    assert r.status_code == 200, r.text
    return r.json()


class TestApplicationJourney:
    def test_create_application_and_consent(self, tokens):
        tok = tokens["super_admin"]
        app = _mk_app(tok)
        assert app["app_no"].startswith("BLP-LN-")
        assert app["status"] == "draft"
        assert app["applicant"]["pan"].startswith("TE")

        # capture consent
        r = requests.post(f"{API}/credit/applications/{app['id']}/consent",
                          json={"bureau_consent": True, "dpdp_consent": True}, headers=hdrs(tok))
        assert r.status_code == 200
        assert r.json()["consent"]["bureau_consent"] is True

    def test_bureau_pull_requires_consent(self, tokens):
        tok = tokens["super_admin"]
        app = _mk_app(tok)
        r = requests.post(f"{API}/credit/applications/{app['id']}/bureau", headers=hdrs(tok))
        assert r.status_code == 400, f"expected 400 no-consent, got {r.status_code}"

    def test_full_run_all_pipeline_strong(self, tokens):
        tok = tokens["super_admin"]
        app = _mk_app(tok, applicant_over={
            "pan": "AAAPS9999Z", "monthly_income": 120000, "age": 40,
            "employment_type": "salaried", "geography": "Metro",
        }, fee_over={"loan_amount": 300000, "tenure_months": 18, "subvention_model": "parent_100"})
        r = requests.post(f"{API}/credit/applications/{app['id']}/run-all", headers=hdrs(tok))
        assert r.status_code == 200, r.text
        a = r.json()
        # sections populated
        assert a["kyc"]["status"] in ("verified", "partial")
        b = a["bureau"]
        assert 300 <= b["score"] <= 900
        assert "accounts" in b and "dpd_max" in b and "utilization_pct" in b
        assert a["bank_analysis"]["months_analysed"] == 6
        ia = a["income_assessment"]
        assert ia["eligible_income"] > 0
        foir = a["foir"]
        # FOIR coherence: (existing + proposed) / income * 100
        expected_foir = round((foir["existing_emi"] + foir["proposed_emi"]) / max(1, foir["monthly_income"]) * 100, 1)
        assert abs(foir["foir_pct"] - expected_foir) < 0.5
        s = a["internal_score"]
        assert 0 <= s["score"] <= 1000
        assert s["band"] in ("Excellent", "Good", "Fair", "Poor")
        assert set(s["breakdown"].keys()) >= {"cibil", "foir"}
        d = a["decision"]
        assert d["status"] in ("Approved", "Conditional Approval", "Refer", "Reject")
        assert isinstance(d["per_lender"], list) and len(d["per_lender"]) >= 4
        for pl in d["per_lender"]:
            assert "passed" in pl and "failed_rules" in pl and "approval_probability" in pl
        p = a["pricing"]
        assert p["loan_amount"] == 300000
        assert p["full_emi"] > 0
        assert "biglyp_revenue" in p
        assert a["fraud"]["risk_level"] in ("Low", "Medium", "High")

    def test_weak_applicant_leads_to_refer_or_reject(self, tokens):
        tok = tokens["super_admin"]
        # Try a few weak PANs to find deterministic weak bureau
        best = None
        for pan in ["ZZZZW0001Z", "ZZZZW0002Z", "ZZZZW0003Z", "ZZZZW0004Z"]:
            app = _mk_app(tok, applicant_over={
                "pan": pan, "monthly_income": 15000, "age": 20,
                "employment_type": "self_employed", "geography": "Rural",
            }, fee_over={"loan_amount": 10000, "tenure_months": 3, "subvention_model": "parent_100"})
            r = requests.post(f"{API}/credit/applications/{app['id']}/run-all", headers=hdrs(tok))
            assert r.status_code == 200
            d = r.json()["decision"]
            best = d["status"]
            if d["status"] in ("Refer", "Reject"):
                # at least one lender should have failed_rules
                any_fail = any(pl["failed_rules"] for pl in d["per_lender"])
                assert any_fail
                return
        pytest.fail(f"weak applicant did not produce Refer/Reject over 4 PANs, last={best}")

    def test_subvention_models(self, tokens):
        tok = tokens["super_admin"]
        results = {}
        for model, split in [("school_100", None), ("parent_100", None), ("shared", 50)]:
            fee = {"loan_amount": 240000, "tenure_months": 12, "subvention_model": model}
            if split is not None:
                fee["subvention_split"] = split
            app = _mk_app(tok, applicant_over={"pan": "SUBVN0001Z"}, fee_over=fee)
            r = requests.post(f"{API}/credit/applications/{app['id']}/run-all", headers=hdrs(tok))
            assert r.status_code == 200, r.text
            results[model] = r.json()["pricing"]

        # school_100: subvention_cost > 0 (full interest), parent_emi ~ principal/tenure
        s = results["school_100"]
        assert s["subvention_cost"] > 0
        assert abs(s["parent_emi"] - (s["loan_amount"] / s["tenure_months"])) < 1500

        # parent_100: subvention_cost == 0
        p = results["parent_100"]
        assert p["subvention_cost"] == 0

        # shared: subvention between 0 and full
        sh = results["shared"]
        assert 0 < sh["subvention_cost"] < s["subvention_cost"] + 5000

        # biglyp_revenue = loan_amount * commission%
        cfg = requests.get(f"{API}/credit/config", headers=hdrs(tok)).json()
        pct = cfg["biglyp_commission_pct"]
        expected = round(240000 * pct / 100)
        for pr in results.values():
            assert abs(pr["biglyp_revenue"] - expected) <= 1

    def test_bank_statement_upload_and_manual(self, tokens):
        tok = tokens["super_admin"]
        app = _mk_app(tok)
        # upload a tiny text statement
        files = {"file": ("stmt.csv", b"date,amount\n2024-01-01,50000\n", "text/csv")}
        r = requests.post(f"{API}/credit/applications/{app['id']}/bank-statement",
                          headers={"Authorization": f"Bearer {tok}"}, files=files, timeout=60)
        assert r.status_code == 200, r.text
        ba = r.json()["bank_analysis"]
        assert "months_analysed" in ba

        # manual
        m = requests.post(f"{API}/credit/applications/{app['id']}/bank-statement/manual",
                         json={"salary": 50000, "business_income": 0, "existing_emi": 5000,
                               "cheque_bounces": 0, "avg_monthly_balance": 30000,
                               "income_consistency": 90}, headers=hdrs(tok))
        assert m.status_code == 200
        assert m.json()["bank_analysis"]["salary"] == 50000
        assert m.json()["bank_analysis"]["source"] == "Manual entry"

    def test_document_upload_with_ocr(self, tokens):
        tok = tokens["super_admin"]
        app = _mk_app(tok)
        files = {"file": ("id.jpg", b"\xff\xd8\xff\xe0dummy", "image/jpeg")}
        r = requests.post(f"{API}/credit/applications/{app['id']}/documents?doc_type=pan",
                          headers={"Authorization": f"Bearer {tok}"}, files=files, timeout=60)
        assert r.status_code == 200, r.text
        assert "ocr_data" in r.json()["document"]


# -------------------------------------------------- fraud ---------------------
class TestFraud:
    def test_duplicate_pan_triggers_flag(self, tokens):
        tok = tokens["super_admin"]
        pan = "FRAUD9999D"
        # first
        a1 = _mk_app(tok, applicant_over={"pan": pan})
        r1 = requests.post(f"{API}/credit/applications/{a1['id']}/run-all", headers=hdrs(tok))
        assert r1.status_code == 200
        risk1 = r1.json()["fraud"]["risk_level"]

        # second with same PAN
        a2 = _mk_app(tok, applicant_over={"pan": pan})
        r2 = requests.post(f"{API}/credit/applications/{a2['id']}/run-all", headers=hdrs(tok))
        assert r2.status_code == 200
        flags = r2.json()["fraud"]["flags"]
        assert any("PAN" in f or "pan" in f.lower() for f in flags), f"expected PAN duplicate flag, got {flags}"
        assert r2.json()["fraud"]["risk_level"] in ("Medium", "High")


# -------------------------------------------------- maker-checker --------------
class TestMakerChecker:
    def test_maker_checker_lender_flow(self, tokens):
        tok = tokens["super_admin"]
        ops = tokens["credit_ops"]
        school = tokens["school_admin"]

        app = _mk_app(tok, applicant_over={"pan": "MCFLW0001Z", "monthly_income": 100000})
        requests.post(f"{API}/credit/applications/{app['id']}/run-all", headers=hdrs(tok))

        # maker-submit
        m = requests.post(f"{API}/credit/applications/{app['id']}/maker-submit", headers=hdrs(tok))
        assert m.status_code == 200
        assert m.json()["workflow"]["stage"] == "checker"

        # school_admin cannot checker-decision
        bad = requests.post(f"{API}/credit/applications/{app['id']}/checker-decision",
                            json={"decision": "approve"}, headers=hdrs(school))
        assert bad.status_code == 403

        # credit_ops can
        c = requests.post(f"{API}/credit/applications/{app['id']}/checker-decision",
                          json={"decision": "approve", "remark": "ok"}, headers=hdrs(ops))
        assert c.status_code == 200
        assert c.json()["workflow"]["stage"] == "lender_submission"

        # pick a lender and submit
        lenders = requests.get(f"{API}/credit/lenders", headers=hdrs(tok)).json()
        hdfc = next(l for l in lenders if l["name"] == "HDFC Bank")
        s = requests.post(f"{API}/credit/applications/{app['id']}/submit-lender?lender_id={hdfc['id']}",
                          headers=hdrs(tok))
        assert s.status_code == 200
        assert s.json()["workflow"]["submitted_lender"] == hdfc["id"]

        # lender should now see this app
        ll = requests.get(f"{API}/credit/applications", headers=hdrs(tokens["lender"]))
        assert ll.status_code == 200
        ids = [x["id"] for x in ll.json()]
        assert app["id"] in ids


# -------------------------------------------------- dashboard + audit ---------
class TestDashboardAudit:
    def test_dashboard_kpis(self, tokens):
        r = requests.get(f"{API}/credit/dashboard", headers=hdrs(tokens["super_admin"]))
        assert r.status_code == 200
        j = r.json()
        for k in ("kpis", "decision_dist", "lender_performance", "school_distribution"):
            assert k in j
        for kp in ("total", "approved", "approval_rate", "sanction_amount", "avg_internal_score"):
            assert kp in j["kpis"]

    def test_lender_dashboard_scoped(self, tokens):
        r = requests.get(f"{API}/credit/dashboard", headers=hdrs(tokens["lender"]))
        assert r.status_code == 200

    def test_audit_and_pii_masking(self, tokens):
        tok = tokens["super_admin"]
        app = _mk_app(tok, applicant_over={"pan": "AUDIT0001Z"})
        requests.post(f"{API}/credit/applications/{app['id']}/consent",
                      json={"bureau_consent": True, "dpdp_consent": True}, headers=hdrs(tok))
        # audit trail
        a = requests.get(f"{API}/credit/applications/{app['id']}/audit", headers=hdrs(tok))
        assert a.status_code == 200
        actions = [e["action"] for e in a.json()]
        assert "application_created" in actions
        assert "consent_captured" in actions

        # PII masking: super_admin gets full
        full = requests.get(f"{API}/credit/applications/{app['id']}", headers=hdrs(tok)).json()
        assert full["applicant"]["pan"] == "AUDIT0001Z"

        # school_admin: masked (may or may not see if school_id filter — test raw endpoint)
        sr = requests.get(f"{API}/credit/applications/{app['id']}", headers=hdrs(tokens["school_admin"]))
        # school_admin can view any app (STAFF role); pan must be masked
        if sr.status_code == 200:
            assert "XXXX" in sr.json()["applicant"]["pan"], f"pan should be masked, got {sr.json()['applicant']['pan']}"
