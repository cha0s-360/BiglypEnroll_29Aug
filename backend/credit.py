"""BiglypEnroll — Credit Assessment & Loan Origination (GrayQuest-inspired).
Self-contained FastAPI router. External bureaus/KYC/AA are realistically simulated;
all downstream engines (FOIR, internal score, policy, eligibility, best-lender,
pricing, subvention, fraud) are fully functional. AI (Emergent LLM) powers
bank-statement analysis and document OCR with graceful fallback.
"""
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).parent / ".env")

import uuid
import math
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional, Annotated

import jwt
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from bson import ObjectId

logger = logging.getLogger("biglyp.credit")

_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = _client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

credit_router = APIRouter(prefix="/api/credit")

ADMIN_ROLES = ["super_admin", "credit_ops"]
STAFF = ["super_admin", "credit_ops", "school_admin", "finance", "counsellor", "manager"]


# --------------------------------------------------------------- auth ---------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            token = h[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean(doc):
    if doc:
        doc.pop("_id", None)
    return doc


def mask_pan(pan: str) -> str:
    if not pan or len(pan) < 5:
        return pan or ""
    return pan[:2] + "XXXX" + pan[-2:]


def mask_aadhaar(a: str) -> str:
    a = (a or "").replace(" ", "")
    if len(a) < 4:
        return "XXXX"
    return "XXXX XXXX " + a[-4:]


async def audit(app_id, actor, action, meta=None):
    await db.credit_audit.insert_one({
        "id": str(uuid.uuid4()), "application_id": app_id,
        "actor": actor.get("email") if isinstance(actor, dict) else actor,
        "action": action, "meta": meta or {}, "timestamp": now_iso(),
    })


# ------------------------------------------------------------ seeding ---------
DEFAULT_WEIGHTS = {
    "cibil": 0.30, "foir": 0.20, "income_stability": 0.12,
    "employment_stability": 0.10, "banking_behaviour": 0.13,
    "credit_utilization": 0.07, "repayment_history": 0.08,
}

DEFAULT_LENDERS = [
    {"name": "Axis Bank", "type": "Bank", "color": "#97144D", "active": True, "policy": {
        "min_cibil": 700, "max_foir": 50, "min_income": 30000, "employment_types": ["salaried", "self_employed"],
        "min_age": 23, "max_age": 60, "min_ticket": 25000, "max_ticket": 1500000,
        "min_tenure": 3, "max_tenure": 24, "geographies": ["Metro", "Urban", "Semi-Urban"],
        "occupations": ["any"], "interest_rate": 13.5, "processing_fee_pct": 1.5, "max_ltv": 100}},
    {"name": "HDFC Bank", "type": "Bank", "color": "#004C8F", "active": True, "policy": {
        "min_cibil": 720, "max_foir": 45, "min_income": 35000, "employment_types": ["salaried"],
        "min_age": 24, "max_age": 58, "min_ticket": 50000, "max_ticket": 2000000,
        "min_tenure": 6, "max_tenure": 24, "geographies": ["Metro", "Urban"],
        "occupations": ["any"], "interest_rate": 12.9, "processing_fee_pct": 1.0, "max_ltv": 100}},
    {"name": "ICICI Bank", "type": "Bank", "color": "#F37E20", "active": True, "policy": {
        "min_cibil": 690, "max_foir": 50, "min_income": 28000, "employment_types": ["salaried", "self_employed"],
        "min_age": 23, "max_age": 60, "min_ticket": 25000, "max_ticket": 1800000,
        "min_tenure": 3, "max_tenure": 24, "geographies": ["Metro", "Urban", "Semi-Urban"],
        "occupations": ["any"], "interest_rate": 13.9, "processing_fee_pct": 1.25, "max_ltv": 100}},
    {"name": "Aditya Birla Finance (NBFC)", "type": "NBFC", "color": "#E4002B", "active": True, "policy": {
        "min_cibil": 650, "max_foir": 55, "min_income": 20000, "employment_types": ["salaried", "self_employed"],
        "min_age": 21, "max_age": 62, "min_ticket": 15000, "max_ticket": 1000000,
        "min_tenure": 3, "max_tenure": 18, "geographies": ["Metro", "Urban", "Semi-Urban", "Rural"],
        "occupations": ["any"], "interest_rate": 16.5, "processing_fee_pct": 2.0, "max_ltv": 100}},
]

# ---- Phase 1: financing-bank configuration (drives the parent financing flow) ----
# Default income-proof requirement matrix, keyed by (CIBIL vs threshold) x (income vs threshold).
DEFAULT_INCOME_PROOF_MATRIX = {
    "high_cibil_high_income": False,  # CIBIL >= threshold AND income >= threshold
    "high_cibil_low_income": True,    # CIBIL >= threshold AND income <  threshold
    "low_cibil_high_income": True,    # CIBIL <  threshold AND income >= threshold
    "low_cibil_low_income": True,     # CIBIL <  threshold AND income <  threshold
}

DEFAULT_FINANCING_BANKS = [
    {
        "name": "CSB Bank Limited",
        "active": True,
        "advance_emi": True,
        "min_loan_amount": 25000,
        "location_match_aadhaar": True,
        "name_match_rule": "aadhaar",  # profile | pan | aadhaar
        "income_proof": {
            "cibil_threshold": 750,
            "income_threshold": 750000,
            "required_matrix": dict(DEFAULT_INCOME_PROOF_MATRIX),
        },
        "fund_release": {
            "multi_account_allowed": False,
            "vendor_external_allowed": False,
        },
    },
]

_seeded = False


async def ensure_seed():
    global _seeded
    if _seeded:
        return
    if await db.credit_config.count_documents({}) == 0:
        await db.credit_config.insert_one({
            "id": "global", "internal_score_weights": DEFAULT_WEIGHTS,
            "biglyp_commission_pct": 1.5, "updated_at": now_iso()})
    if await db.lenders.count_documents({}) == 0:
        for l in DEFAULT_LENDERS:
            await db.lenders.insert_one({"id": str(uuid.uuid4()), **l, "created_at": now_iso()})
    # demo lender user (bound to HDFC)
    import bcrypt
    lender_doc = await db.lenders.find_one({"name": "HDFC Bank"})
    if lender_doc and not await db.users.find_one({"email": "lender@biglyp.com"}):
        await db.users.insert_one({
            "name": "HDFC Partner", "email": "lender@biglyp.com",
            "password_hash": bcrypt.hashpw(b"lender123", bcrypt.gensalt()).decode(),
            "role": "lender", "school_id": None, "lender_id": lender_doc["id"],
            "created_at": now_iso()})
    if not await db.users.find_one({"email": "creditops@biglyp.com"}):
        await db.users.insert_one({
            "name": "Credit Ops", "email": "creditops@biglyp.com",
            "password_hash": bcrypt.hashpw(b"creditops123", bcrypt.gensalt()).decode(),
            "role": "credit_ops", "school_id": None, "created_at": now_iso()})
    if await db.financing_banks.count_documents({}) == 0:
        for b in DEFAULT_FINANCING_BANKS:
            await db.financing_banks.insert_one({
                "id": str(uuid.uuid4()), **b,
                "created_at": now_iso(), "updated_at": now_iso()})
    _seeded = True


# --------------------------------------------------------------- engines ------
def emi(principal: float, annual_rate: float, tenure_m: int) -> float:
    if tenure_m <= 0:
        return 0.0
    r = annual_rate / 1200.0
    if r == 0:
        return round(principal / tenure_m, 2)
    f = (1 + r) ** tenure_m
    return round(principal * r * f / (f - 1), 2)


def simulate_bureau(applicant: dict, provider: str) -> dict:
    """Deterministic mock bureau report derived from PAN so re-pulls are stable."""
    pan = (applicant.get("pan") or "ABCDE0000F").upper()
    seed = int(hashlib.sha256((pan + provider).encode()).hexdigest(), 16)
    score = 600 + (seed % 250)  # 600-849
    active_loans = seed % 5
    total_emi = round((seed % 40000) / 100) * 100 if active_loans else 0
    dpd_max = [0, 0, 0, 15, 30, 60, 90][seed % 7]
    enquiries = seed % 6
    written_off = 1 if (seed % 17 == 0) else 0
    utilization = 15 + (seed % 80)
    repayment_history = max(40, 100 - dpd_max // 2 - written_off * 20)
    mixes = ["Secured heavy", "Balanced", "Unsecured heavy"]
    accounts = []
    kinds = ["Personal Loan", "Credit Card", "Auto Loan", "Consumer Durable", "Home Loan"]
    for i in range(active_loans):
        accounts.append({
            "type": kinds[(seed >> (i + 1)) % len(kinds)],
            "sanctioned": (((seed >> i) % 500) + 50) * 1000,
            "outstanding": (((seed >> i) % 300) + 10) * 1000,
            "emi": round(((seed >> i) % 15000) / 100) * 100,
            "dpd": [0, 0, 0, 15, 30][(seed >> i) % 5],
            "status": "Active",
        })
    return {
        "provider": provider, "score": score, "pulled_at": now_iso(),
        "active_loans": active_loans, "total_emi": total_emi, "dpd_max": dpd_max,
        "enquiries_6m": enquiries, "written_off": written_off,
        "utilization_pct": utilization, "credit_mix": mixes[seed % 3],
        "repayment_history_pct": repayment_history, "accounts": accounts,
    }


def simulate_bank_analysis(applicant: dict) -> dict:
    pan = (applicant.get("pan") or "ABCDE0000F").upper()
    seed = int(hashlib.sha256((pan + "bank").encode()).hexdigest(), 16)
    income = float(applicant.get("monthly_income") or (25000 + seed % 90000))
    salaried = applicant.get("employment_type", "salaried") == "salaried"
    bounces = seed % 4
    avg_bal = round(income * (0.4 + (seed % 60) / 100.0))
    consistency = max(50, 100 - bounces * 12 - (seed % 20))
    return {
        "source": "Simulated (PDF/AA)", "months_analysed": 6,
        "salary": income if salaried else 0,
        "business_income": 0 if salaried else income,
        "existing_emi": round((seed % 25000) / 100) * 100,
        "cheque_bounces": bounces,
        "cash_deposits": 0 if salaried else round(income * 0.3),
        "avg_monthly_balance": avg_bal,
        "income_consistency": consistency,
        "repayment_behaviour": "Good" if bounces == 0 else ("Fair" if bounces < 3 else "Poor"),
    }


def compute_income_assessment(app: dict) -> dict:
    ba = app.get("bank_analysis", {})
    bureau = app.get("bureau", {})
    applicant = app.get("applicant", {})
    salaried = applicant.get("employment_type", "salaried") == "salaried"
    eligible_income = ba.get("salary") or ba.get("business_income") or float(applicant.get("monthly_income") or 0)
    if not salaried and eligible_income:
        eligible_income = round(eligible_income * 0.75)  # haircut for self-employed
    existing_obligations = max(ba.get("existing_emi", 0), bureau.get("total_emi", 0))
    disposable = max(0, eligible_income - existing_obligations)
    repayment_capacity = max(0, round(eligible_income * 0.5) - existing_obligations)
    return {
        "eligible_income": round(eligible_income),
        "existing_obligations": round(existing_obligations),
        "disposable_income": round(disposable),
        "repayment_capacity": round(repayment_capacity),
    }


def compute_foir(app: dict, proposed_emi: float) -> dict:
    ia = app.get("income_assessment", {})
    income = ia.get("eligible_income", 0) or 1
    existing = ia.get("existing_obligations", 0)
    foir = round((existing + proposed_emi) / income * 100, 1)
    return {"existing_emi": existing, "proposed_emi": round(proposed_emi),
            "monthly_income": round(income), "foir_pct": foir,
            "monthly_surplus": round(income - existing - proposed_emi)}


def _band(score):
    if score >= 750:
        return "Excellent"
    if score >= 650:
        return "Good"
    if score >= 550:
        return "Fair"
    return "Poor"


def compute_internal_score(app: dict, weights: dict) -> dict:
    bureau = app.get("bureau", {})
    ba = app.get("bank_analysis", {})
    foir = app.get("foir", {})
    applicant = app.get("applicant", {})

    cibil = bureau.get("score", 650)
    c_cibil = max(0, min(100, (cibil - 300) / 6.0))  # 300..900 -> 0..100
    f = foir.get("foir_pct", 50)
    c_foir = max(0, min(100, (70 - f) / 30 * 100))
    c_income_stab = ba.get("income_consistency", 70)
    emp = applicant.get("employment_type", "salaried")
    c_emp = 85 if emp == "salaried" else 65
    bounces = ba.get("cheque_bounces", 0)
    c_bank = max(0, 100 - bounces * 18)
    util = bureau.get("utilization_pct", 40)
    c_util = max(0, min(100, (90 - util) / 60 * 100))
    c_repay = bureau.get("repayment_history_pct", 80)

    comps = {
        "cibil": round(c_cibil), "foir": round(c_foir),
        "income_stability": round(c_income_stab), "employment_stability": round(c_emp),
        "banking_behaviour": round(c_bank), "credit_utilization": round(c_util),
        "repayment_history": round(c_repay),
    }
    total = sum(comps[k] * weights.get(k, 0) for k in comps)
    score = round(total * 10)  # 0..1000
    return {"score": score, "band": _band(score), "breakdown": comps, "weights": weights}


def eval_policy(app: dict, lender: dict, proposed_emi: float) -> dict:
    p = lender["policy"]
    applicant = app.get("applicant", {})
    bureau = app.get("bureau", {})
    ia = app.get("income_assessment", {})
    foir = app.get("foir", {}).get("foir_pct", 100)
    loan_amount = app.get("fee", {}).get("loan_amount", 0)
    tenure = app.get("fee", {}).get("tenure_months", 12)
    fails = []

    if bureau.get("score", 0) < p["min_cibil"]:
        fails.append(f"CIBIL {bureau.get('score',0)} < {p['min_cibil']}")
    if foir > p["max_foir"]:
        fails.append(f"FOIR {foir}% > {p['max_foir']}%")
    if ia.get("eligible_income", 0) < p["min_income"]:
        fails.append(f"Income ₹{ia.get('eligible_income',0):,} < ₹{p['min_income']:,}")
    if applicant.get("employment_type") not in p["employment_types"]:
        fails.append(f"Employment '{applicant.get('employment_type')}' not allowed")
    age = applicant.get("age", 35)
    if age < p["min_age"] or age > p["max_age"]:
        fails.append(f"Age {age} outside {p['min_age']}-{p['max_age']}")
    if loan_amount < p["min_ticket"] or loan_amount > p["max_ticket"]:
        fails.append(f"Ticket ₹{loan_amount:,} outside ₹{p['min_ticket']:,}-₹{p['max_ticket']:,}")
    if tenure < p["min_tenure"] or tenure > p["max_tenure"]:
        fails.append(f"Tenure {tenure}m outside {p['min_tenure']}-{p['max_tenure']}m")
    geo = applicant.get("geography", "Urban")
    if geo not in p["geographies"]:
        fails.append(f"Geography '{geo}' not served")
    if bureau.get("written_off", 0) > 0:
        fails.append("Written-off account on bureau")

    passed = len(fails) == 0
    # approval probability heuristic
    score = app.get("internal_score", {}).get("score", 600)
    cibil_margin = max(0, bureau.get("score", 0) - p["min_cibil"])
    foir_margin = max(0, p["max_foir"] - foir)
    prob = 0.0
    if passed:
        prob = 0.55 + min(0.20, cibil_margin / 500) + min(0.15, foir_margin / 100) + min(0.10, (score - 600) / 1000)
    else:
        prob = max(0.05, 0.40 - 0.10 * len(fails))
    prob = round(min(0.98, max(0.02, prob)), 2)
    return {"lender_id": lender["id"], "lender_name": lender["name"],
            "lender_type": lender["type"], "color": lender.get("color"),
            "interest_rate": p["interest_rate"], "passed": passed,
            "failed_rules": fails, "approval_probability": prob}


# --------------------------------------------------------------- models -------
class ApplicationIn(BaseModel):
    student: dict = {}
    applicant: dict = {}
    co_applicant: dict = {}
    fee: dict = {}
    school_id: Optional[str] = None


class ConsentIn(BaseModel):
    bureau_consent: bool = True
    dpdp_consent: bool = True


class BankManualIn(BaseModel):
    salary: float = 0
    business_income: float = 0
    existing_emi: float = 0
    cheque_bounces: int = 0
    avg_monthly_balance: float = 0
    income_consistency: int = 80


class WeightsIn(BaseModel):
    internal_score_weights: dict
    biglyp_commission_pct: float = 1.5


class LenderIn(BaseModel):
    name: str
    type: str = "Bank"
    color: str = "#004C8F"
    active: bool = True
    policy: dict


# ---- Phase 1: financing-bank configuration models ----
class IncomeProofMatrix(BaseModel):
    # For each (CIBIL vs threshold) x (income vs threshold) combination:
    # is income proof REQUIRED?
    high_cibil_high_income: bool = False
    high_cibil_low_income: bool = True
    low_cibil_high_income: bool = True
    low_cibil_low_income: bool = True


class IncomeProofCriteria(BaseModel):
    cibil_threshold: int = 750
    income_threshold: float = 750000
    required_matrix: IncomeProofMatrix = Field(default_factory=IncomeProofMatrix)


class FundReleaseRules(BaseModel):
    multi_account_allowed: bool = False
    vendor_external_allowed: bool = False


class FinancingBankIn(BaseModel):
    name: str
    active: bool = True
    advance_emi: bool = False
    min_loan_amount: float = 25000
    location_match_aadhaar: bool = False
    name_match_rule: str = "aadhaar"  # profile | pan | aadhaar
    income_proof: IncomeProofCriteria = Field(default_factory=IncomeProofCriteria)
    fund_release: FundReleaseRules = Field(default_factory=FundReleaseRules)


class CheckerIn(BaseModel):
    decision: str  # approve | reject
    remark: str = ""


class DeficiencyIn(BaseModel):
    text: str


# --------------------------------------------------------------- config -------
@credit_router.get("/config")
async def get_config(user: dict = Depends(require_roles(*STAFF))):
    await ensure_seed()
    return clean(await db.credit_config.find_one({"id": "global"}))


@credit_router.put("/config")
async def update_config(body: WeightsIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    await ensure_seed()
    await db.credit_config.update_one({"id": "global"}, {"$set": {
        "internal_score_weights": body.internal_score_weights,
        "biglyp_commission_pct": body.biglyp_commission_pct, "updated_at": now_iso()}})
    return clean(await db.credit_config.find_one({"id": "global"}))


# --------------------------------------------------------------- lenders ------
@credit_router.get("/lenders")
async def list_lenders(user: dict = Depends(require_roles(*STAFF, "lender"))):
    await ensure_seed()
    out = []
    async for l in db.lenders.find():
        out.append(clean(l))
    return out


@credit_router.post("/lenders")
async def create_lender(body: LenderIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    doc = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": now_iso()}
    await db.lenders.insert_one(doc)
    return clean(doc)


@credit_router.put("/lenders/{lid}")
async def update_lender(lid: str, body: LenderIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    await db.lenders.update_one({"id": lid}, {"$set": body.model_dump()})
    return clean(await db.lenders.find_one({"id": lid}))


@credit_router.delete("/lenders/{lid}")
async def delete_lender(lid: str, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    await db.lenders.delete_one({"id": lid})
    return {"ok": True}


# --------------------------------------------------- financing banks (Phase 1) -
# Pure CRUD for banks that fund the parent 0% EMI financing flow. The full config
# per bank is looked up by later flow buckets via GET /financing-banks/{bid}.
@credit_router.get("/financing-banks")
async def list_financing_banks(user: dict = Depends(require_roles(*ADMIN_ROLES))):
    await ensure_seed()
    out = []
    async for b in db.financing_banks.find():
        out.append(clean(b))
    return out


@credit_router.post("/financing-banks")
async def create_financing_bank(body: FinancingBankIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    await ensure_seed()
    doc = {"id": str(uuid.uuid4()), **body.model_dump(),
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.financing_banks.insert_one(doc)
    return clean(doc)


@credit_router.get("/financing-banks/{bid}")
async def get_financing_bank(bid: str, user: dict = Depends(get_current_user)):
    """Full config lookup for a single bank — consumed by later flow buckets."""
    await ensure_seed()
    doc = await db.financing_banks.find_one({"id": bid})
    if not doc:
        raise HTTPException(status_code=404, detail="Financing bank not found")
    return clean(doc)


@credit_router.put("/financing-banks/{bid}")
async def update_financing_bank(bid: str, body: FinancingBankIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    existing = await db.financing_banks.find_one({"id": bid})
    if not existing:
        raise HTTPException(status_code=404, detail="Financing bank not found")
    await db.financing_banks.update_one(
        {"id": bid}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    return clean(await db.financing_banks.find_one({"id": bid}))


@credit_router.delete("/financing-banks/{bid}")
async def delete_financing_bank(bid: str, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    res = await db.financing_banks.delete_one({"id": bid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Financing bank not found")
    return {"ok": True}


# ---------------------------------- school ↔ bank financing management --------
# Self-contained admin module. Uses a HARDCODED/DUMMY bank list (does not depend
# on Bucket 1's real bank API). Each school can attach multiple banks, each with
# an INDEPENDENT interest rate (per bank-school pair) and a priority/ranking used
# for auto-selection, plus a per-school financing on/off toggle.
DUMMY_BANKS = [
    {"id": "hdfc", "name": "HDFC Bank"},
    {"id": "icici", "name": "ICICI Bank"},
    {"id": "axis", "name": "Axis Bank"},
    {"id": "sbi", "name": "State Bank of India"},
    {"id": "kotak", "name": "Kotak Mahindra Bank"},
    {"id": "csb", "name": "CSB Bank Limited"},
    {"id": "idfc", "name": "IDFC First Bank"},
    {"id": "yes", "name": "YES Bank"},
    {"id": "federal", "name": "Federal Bank"},
    {"id": "bajaj", "name": "Bajaj Finserv"},
]
_DUMMY_BANK_NAMES = {b["id"]: b["name"] for b in DUMMY_BANKS}


class SchoolBankIn(BaseModel):
    bank_id: str
    bank_name: str = ""
    interest_rate: float = 0.0        # independent per bank-school pair
    priority: int = 1                 # 1 = highest priority for auto-selection


class FinSchoolIn(BaseModel):
    name: str
    financing_enabled: bool = True    # product control toggle for this school
    banks: List[SchoolBankIn] = Field(default_factory=list)


def _normalise_fin_school_banks(banks: List[dict]) -> List[dict]:
    """Fill bank_name from the dummy list and sort by priority (auto-selection order)."""
    out = []
    for b in banks:
        bid = b.get("bank_id")
        out.append({
            "bank_id": bid,
            "bank_name": b.get("bank_name") or _DUMMY_BANK_NAMES.get(bid, bid or ""),
            "interest_rate": float(b.get("interest_rate") or 0),
            "priority": int(b.get("priority") or 1),
        })
    out.sort(key=lambda x: (x["priority"], x["bank_name"]))
    return out


@credit_router.get("/dummy-banks")
async def list_dummy_banks(user: dict = Depends(get_current_user)):
    """Hardcoded/dummy bank catalogue for attaching to schools."""
    return DUMMY_BANKS


@credit_router.get("/fin-schools")
async def list_fin_schools(user: dict = Depends(require_roles(*ADMIN_ROLES))):
    out = []
    async for s in db.fin_schools.find():
        s = clean(s)
        s["banks"] = _normalise_fin_school_banks(s.get("banks", []))
        out.append(s)
    out.sort(key=lambda x: (x.get("name") or "").lower())
    return out


@credit_router.post("/fin-schools")
async def create_fin_school(body: FinSchoolIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="School name is required")
    doc = {
        "id": str(uuid.uuid4()),
        "name": body.name.strip(),
        "financing_enabled": body.financing_enabled,
        "banks": _normalise_fin_school_banks([b.model_dump() for b in body.banks]),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.fin_schools.insert_one(doc)
    return clean(doc)


@credit_router.get("/fin-schools/{sid}")
async def get_fin_school(sid: str, user: dict = Depends(get_current_user)):
    """GET-by-school-ID lookup: attached banks (with independent rates + priority
    order) and the financing toggle state. Consumed by later financing buckets."""
    doc = await db.fin_schools.find_one({"id": sid})
    if not doc:
        raise HTTPException(status_code=404, detail="School not found")
    doc = clean(doc)
    doc["banks"] = _normalise_fin_school_banks(doc.get("banks", []))
    return doc


@credit_router.put("/fin-schools/{sid}")
async def update_fin_school(sid: str, body: FinSchoolIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    existing = await db.fin_schools.find_one({"id": sid})
    if not existing:
        raise HTTPException(status_code=404, detail="School not found")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="School name is required")
    await db.fin_schools.update_one({"id": sid}, {"$set": {
        "name": body.name.strip(),
        "financing_enabled": body.financing_enabled,
        "banks": _normalise_fin_school_banks([b.model_dump() for b in body.banks]),
        "updated_at": now_iso(),
    }})
    doc = clean(await db.fin_schools.find_one({"id": sid}))
    doc["banks"] = _normalise_fin_school_banks(doc.get("banks", []))
    return doc


@credit_router.delete("/fin-schools/{sid}")
async def delete_fin_school(sid: str, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    res = await db.fin_schools.delete_one({"id": sid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="School not found")
    return {"ok": True}



# --------------------------------------------------------- applications -------
def _public_app(app: dict, role: str):
    """Return app with PII masked for non-admin roles."""
    app = clean(dict(app))
    ap = app.get("applicant", {})
    if role not in ("super_admin", "credit_ops"):
        if ap.get("pan"):
            ap = dict(ap); ap["pan"] = mask_pan(ap["pan"])
        if ap.get("aadhaar"):
            ap["aadhaar"] = mask_aadhaar(ap["aadhaar"])
        app["applicant"] = ap
    return app


@credit_router.get("/applications")
async def list_applications(user: dict = Depends(require_roles(*STAFF, "lender"))):
    await ensure_seed()
    q = {}
    role = user["role"]
    if role in ("school_admin", "finance", "counsellor", "manager") and user.get("school_id"):
        q["school_id"] = user["school_id"]
    elif role == "lender":
        q["workflow.submitted_lender"] = user.get("lender_id")
    out = []
    async for a in db.credit_applications.find(q).sort("created_at", -1):
        out.append(_public_app(a, role))
    return out


@credit_router.post("/applications")
async def create_application(body: ApplicationIn, user: dict = Depends(require_roles(*STAFF))):
    await ensure_seed()
    count = await db.credit_applications.count_documents({})
    doc = {
        "id": str(uuid.uuid4()),
        "app_no": f"BLP-LN-{datetime.now().strftime('%y%m')}-{count + 1:04d}",
        "status": "draft",
        "student": body.student, "applicant": body.applicant,
        "co_applicant": body.co_applicant, "fee": body.fee,
        "school_id": body.school_id or user.get("school_id"),
        "created_by": user["email"], "created_by_role": user["role"],
        "consent": {}, "kyc": {}, "documents": [], "bureau": {},
        "bank_analysis": {}, "income_assessment": {}, "foir": {},
        "internal_score": {}, "decision": {}, "pricing": {}, "fraud": {},
        "workflow": {"stage": "maker", "deficiencies": []},
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.credit_applications.insert_one(doc)
    await audit(doc["id"], user, "application_created", {"app_no": doc["app_no"]})
    return _public_app(doc, user["role"])


async def _get_app(app_id):
    a = await db.credit_applications.find_one({"id": app_id})
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    return a


def _assert_can_view(a: dict, user: dict):
    role = user["role"]
    if role in ("school_admin", "finance", "counsellor", "manager") and user.get("school_id"):
        if a.get("school_id") != user["school_id"]:
            raise HTTPException(status_code=403, detail="Application belongs to another institute")
    elif role == "lender":
        if a.get("workflow", {}).get("submitted_lender") != user.get("lender_id"):
            raise HTTPException(status_code=403, detail="Not submitted to your institution")


@credit_router.get("/applications/{app_id}")
async def get_application(app_id: str, user: dict = Depends(require_roles(*STAFF, "lender"))):
    a = await _get_app(app_id)
    _assert_can_view(a, user)
    return _public_app(a, user["role"])


@credit_router.put("/applications/{app_id}")
async def update_application(app_id: str, body: ApplicationIn, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    upd = {k: v for k, v in body.model_dump().items() if v}
    upd["updated_at"] = now_iso()
    await db.credit_applications.update_one({"id": app_id}, {"$set": upd})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/consent")
async def capture_consent(app_id: str, body: ConsentIn, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    consent = {"bureau_consent": body.bureau_consent, "dpdp_consent": body.dpdp_consent,
               "captured_at": now_iso(), "captured_by": user["email"]}
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"consent": consent, "updated_at": now_iso()}})
    await audit(app_id, user, "consent_captured", consent)
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/kyc")
async def run_kyc(app_id: str, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    ap = a.get("applicant", {})
    has_pan = bool(ap.get("pan"))
    has_aadhaar = bool(ap.get("aadhaar"))
    kyc = {
        "pan_verified": has_pan, "aadhaar_verified": has_aadhaar,
        "ckyc_ref": ("CKYC" + hashlib.sha1((ap.get("pan") or "x").encode()).hexdigest()[:12].upper()) if has_pan else None,
        "digilocker": has_aadhaar, "ocr_done": bool(a.get("documents")),
        "selfie_liveness": True, "esign_ready": has_pan and has_aadhaar,
        "status": "verified" if (has_pan and has_aadhaar) else "partial",
        "verified_at": now_iso(),
    }
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"kyc": kyc, "status": "kyc_done", "updated_at": now_iso()}})
    await audit(app_id, user, "kyc_run", {"status": kyc["status"]})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/documents")
async def upload_document(app_id: str, doc_type: str = "", file: UploadFile = File(...),
                          user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    content = await file.read()
    ocr_data = {}
    # Attempt AI OCR extraction for identity/income docs
    try:
        ocr_data = await _ai_ocr(content, file.filename, doc_type)
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        ocr_data = {"note": "OCR unavailable — manual entry"}
    entry = {"id": str(uuid.uuid4()), "type": doc_type or "document",
             "filename": file.filename, "size": len(content),
             "ocr_data": ocr_data, "uploaded_at": now_iso()}
    await db.credit_applications.update_one({"id": app_id}, {"$push": {"documents": entry}, "$set": {"updated_at": now_iso()}})
    await audit(app_id, user, "document_uploaded", {"type": entry["type"]})
    return {"document": entry}


@credit_router.post("/applications/{app_id}/bureau")
async def pull_bureau(app_id: str, provider: str = "TransUnion CIBIL",
                      user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    if not a.get("consent", {}).get("bureau_consent"):
        raise HTTPException(status_code=400, detail="Bureau consent required before pull")
    report = simulate_bureau(a.get("applicant", {}), provider)
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"bureau": report, "updated_at": now_iso()}})
    await audit(app_id, user, "bureau_pulled", {"provider": provider, "score": report["score"]})
    return {"bureau": report}


@credit_router.post("/applications/{app_id}/bank-statement")
async def analyze_bank(app_id: str, file: Optional[UploadFile] = File(None),
                       user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    analysis = None
    if file is not None:
        content = await file.read()
        try:
            analysis = await _ai_bank_statement(content, file.filename)
        except Exception as e:
            logger.warning("Bank AI failed: %s", e)
    if not analysis:
        analysis = simulate_bank_analysis(a.get("applicant", {}))
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"bank_analysis": analysis, "updated_at": now_iso()}})
    await audit(app_id, user, "bank_analysed", {"source": analysis.get("source")})
    return {"bank_analysis": analysis}


@credit_router.post("/applications/{app_id}/bank-statement/manual")
async def bank_manual(app_id: str, body: BankManualIn, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    analysis = body.model_dump()
    analysis.update({"source": "Manual entry", "months_analysed": 6,
                     "cash_deposits": 0, "repayment_behaviour": "Good" if body.cheque_bounces == 0 else "Fair"})
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"bank_analysis": analysis, "updated_at": now_iso()}})
    return {"bank_analysis": analysis}


async def _run_engines(a: dict) -> dict:
    """Income assessment -> pricing(proposed emi) -> FOIR -> internal score -> decision -> fraud."""
    cfg = await db.credit_config.find_one({"id": "global"})
    weights = cfg["internal_score_weights"]
    commission = cfg.get("biglyp_commission_pct", 1.5)

    a["income_assessment"] = compute_income_assessment(a)

    fee = a.get("fee", {})
    loan_amount = float(fee.get("loan_amount", 0))
    tenure = int(fee.get("tenure_months", 12))

    lenders = [l async for l in db.lenders.find({"active": True})]
    # proposed emi uses best available (lowest) interest rate for FOIR base
    rate = min([l["policy"]["interest_rate"] for l in lenders], default=14.0)
    proposed_emi = emi(loan_amount, rate, tenure)

    a["foir"] = compute_foir(a, proposed_emi)
    a["internal_score"] = compute_internal_score(a, weights)

    # policy evaluation per lender
    evals = [eval_policy(a, l, proposed_emi) for l in lenders]
    evals.sort(key=lambda x: (x["passed"], x["approval_probability"]), reverse=True)
    passing = [e for e in evals if e["passed"]]
    recommended = passing[0] if passing else (evals[0] if evals else None)

    score = a["internal_score"]["score"]
    foir_pct = a["foir"]["foir_pct"]
    if passing and score >= 700:
        status, reasons = "Approved", ["Meets lender policy", f"Strong internal score {score}/1000", f"FOIR {foir_pct}% within limits"]
    elif passing and score >= 600:
        status, reasons = "Conditional Approval", ["Meets policy with moderate score", "Recommend co-applicant / lower ticket"]
    elif not passing and score >= 550:
        status, reasons = "Refer", ["No lender fully passes automated policy", "Manual underwriting recommended"]
    else:
        status, reasons = "Reject", (evals[0]["failed_rules"][:3] if evals and evals[0]["failed_rules"] else ["Below minimum credit criteria"])

    a["decision"] = {"status": status, "reasons": reasons, "per_lender": evals,
                     "recommended_lender_id": recommended["lender_id"] if recommended else None,
                     "recommended_lender_name": recommended["lender_name"] if recommended else None,
                     "decisioned_at": now_iso()}

    # pricing based on recommended lender + subvention
    rec_rate = recommended["interest_rate"] if recommended else rate
    subv_model = fee.get("subvention_model", "parent_100")
    school_share = 1.0 if subv_model == "school_100" else (0.0 if subv_model == "parent_100" else float(fee.get("subvention_split", 50)) / 100.0)
    full_emi = emi(loan_amount, rec_rate, tenure)
    total_payable = full_emi * tenure
    total_interest = round(total_payable - loan_amount)
    pf_pct = 1.5
    if recommended:
        rec_l = next((l for l in lenders if l["id"] == recommended["lender_id"]), None)
        if rec_l:
            pf_pct = rec_l["policy"].get("processing_fee_pct", 1.5)
    processing_fee = round(loan_amount * pf_pct / 100)
    subvention_cost = round(total_interest * school_share)
    parent_interest = total_interest - subvention_cost
    parent_emi = round((loan_amount + parent_interest) / tenure) if tenure else 0
    biglyp_revenue = round(loan_amount * commission / 100)
    school_payout = round(loan_amount - subvention_cost - biglyp_revenue)
    a["pricing"] = {
        "recommended_lender": recommended["lender_name"] if recommended else None,
        "interest_rate": rec_rate, "subvention_model": subv_model, "school_share_pct": round(school_share * 100),
        "loan_amount": round(loan_amount), "tenure_months": tenure,
        "full_emi": round(full_emi), "parent_emi": parent_emi,
        "iir": round(total_interest / loan_amount * 100, 1) if loan_amount else 0,
        "total_interest": total_interest, "processing_fee": processing_fee,
        "bank_spread": round(total_interest * 0.7), "lender_yield": total_interest,
        "subvention_cost": subvention_cost, "parent_contribution": parent_interest,
        "school_payout": school_payout, "biglyp_revenue": biglyp_revenue,
    }

    # fraud engine
    a["fraud"] = await _fraud_checks(a)
    a["status"] = "assessed"
    a["updated_at"] = now_iso()
    return a


async def _fraud_checks(a: dict) -> dict:
    flags = []
    ap = a.get("applicant", {})
    pan = ap.get("pan")
    mobile = ap.get("mobile")
    if pan:
        dup = await db.credit_applications.count_documents({"applicant.pan": pan, "id": {"$ne": a["id"]}})
        if dup >= 1:
            flags.append(f"PAN used in {dup} other application(s)")
        if dup >= 3:
            flags.append("Multiple loan applications on same PAN (velocity)")
    if mobile:
        dupm = await db.credit_applications.count_documents({"applicant.mobile": mobile, "applicant.pan": {"$ne": pan}})
        if dupm >= 1:
            flags.append("Mobile shared across different PANs")
    ba = a.get("bank_analysis", {})
    if ba.get("income_consistency", 100) < 55:
        flags.append("Low income consistency — statement may be manipulated")
    if ba.get("avg_monthly_balance", 1) < 1000:
        flags.append("Very low average balance vs declared income")
    for d in a.get("documents", []):
        ocr = d.get("ocr_data", {})
        if ocr.get("name") and ap.get("name") and ocr["name"].strip().lower() not in ap["name"].strip().lower() and ap["name"].strip().lower() not in ocr["name"].strip().lower():
            flags.append(f"Name mismatch on {d.get('type')} (possible tampering)")
    risk = "Low" if not flags else ("Medium" if len(flags) <= 2 else "High")
    return {"flags": flags, "risk_level": risk, "checked_at": now_iso()}


@credit_router.post("/applications/{app_id}/assess")
async def run_assessment(app_id: str, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    if not a.get("bureau"):
        raise HTTPException(status_code=400, detail="Pull the credit bureau report first")
    if not a.get("bank_analysis"):
        a["bank_analysis"] = simulate_bank_analysis(a.get("applicant", {}))
    a = await _run_engines(a)
    await db.credit_applications.update_one({"id": app_id}, {"$set": {
        "income_assessment": a["income_assessment"], "foir": a["foir"],
        "internal_score": a["internal_score"], "decision": a["decision"],
        "pricing": a["pricing"], "fraud": a["fraud"], "bank_analysis": a["bank_analysis"],
        "status": "assessed", "updated_at": now_iso()}})
    await audit(app_id, user, "assessment_run", {"status": a["decision"]["status"], "score": a["internal_score"]["score"]})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/run-all")
async def run_full_pipeline(app_id: str, provider: str = "TransUnion CIBIL",
                            user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    if not a.get("consent", {}).get("bureau_consent"):
        await db.credit_applications.update_one({"id": app_id}, {"$set": {
            "consent": {"bureau_consent": True, "dpdp_consent": True, "captured_at": now_iso(), "captured_by": user["email"]}}})
        a = await _get_app(app_id)
    # KYC
    await run_kyc(app_id, user)
    a = await _get_app(app_id)
    a["bureau"] = simulate_bureau(a.get("applicant", {}), provider)
    if not a.get("bank_analysis"):
        a["bank_analysis"] = simulate_bank_analysis(a.get("applicant", {}))
    a = await _run_engines(a)
    await db.credit_applications.update_one({"id": app_id}, {"$set": {
        "bureau": a["bureau"], "bank_analysis": a["bank_analysis"],
        "income_assessment": a["income_assessment"], "foir": a["foir"],
        "internal_score": a["internal_score"], "decision": a["decision"],
        "pricing": a["pricing"], "fraud": a["fraud"], "status": "assessed", "updated_at": now_iso()}})
    await audit(app_id, user, "pipeline_run", {"status": a["decision"]["status"]})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/maker-submit")
async def maker_submit(app_id: str, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    if not a.get("decision"):
        raise HTTPException(status_code=400, detail="Run assessment before submitting for review")
    wf = a.get("workflow", {})
    wf.update({"stage": "checker", "maker": user["email"], "maker_at": now_iso()})
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"workflow": wf, "status": "maker_review", "updated_at": now_iso()}})
    await audit(app_id, user, "maker_submitted")
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/checker-decision")
async def checker_decision(app_id: str, body: CheckerIn, user: dict = Depends(require_roles(*ADMIN_ROLES))):
    a = await _get_app(app_id)
    wf = a.get("workflow", {})
    wf.update({"checker": user["email"], "checker_at": now_iso(),
               "checker_decision": body.decision, "checker_remark": body.remark})
    status = "checker_approved" if body.decision == "approve" else "rejected"
    wf["stage"] = "lender_submission" if body.decision == "approve" else "closed"
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"workflow": wf, "status": status, "updated_at": now_iso()}})
    await audit(app_id, user, "checker_decision", {"decision": body.decision})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/submit-lender")
async def submit_lender(app_id: str, lender_id: str, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    lender = await db.lenders.find_one({"id": lender_id})
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")
    wf = a.get("workflow", {})
    wf.update({"submitted_lender": lender_id, "submitted_lender_name": lender["name"],
               "submitted_at": now_iso(), "stage": "submitted"})
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"workflow": wf, "status": "submitted_to_lender", "updated_at": now_iso()}})
    await audit(app_id, user, "submitted_to_lender", {"lender": lender["name"]})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/lender-status")
async def lender_status(app_id: str, status: str, sanction_amount: float = 0,
                        user: dict = Depends(require_roles("lender", *ADMIN_ROLES))):
    a = await _get_app(app_id)
    wf = a.get("workflow", {})
    wf.update({"lender_status": status, "sanction_amount": sanction_amount, "lender_updated_at": now_iso()})
    app_status = {"sanctioned": "sanctioned", "rejected": "lender_rejected"}.get(status, a["status"])
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"workflow": wf, "status": app_status, "updated_at": now_iso()}})
    await audit(app_id, user, "lender_status", {"status": status})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/deficiency")
async def add_deficiency(app_id: str, body: DeficiencyIn, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    wf = a.get("workflow", {})
    defs = wf.get("deficiencies", [])
    defs.append({"id": str(uuid.uuid4()), "text": body.text, "resolved": False,
                 "raised_by": user["email"], "raised_at": now_iso()})
    wf["deficiencies"] = defs
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"workflow": wf, "updated_at": now_iso()}})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.post("/applications/{app_id}/deficiency/{def_id}/resolve")
async def resolve_deficiency(app_id: str, def_id: str, user: dict = Depends(require_roles(*STAFF))):
    a = await _get_app(app_id)
    wf = a.get("workflow", {})
    for d in wf.get("deficiencies", []):
        if d["id"] == def_id:
            d["resolved"] = True
    await db.credit_applications.update_one({"id": app_id}, {"$set": {"workflow": wf, "updated_at": now_iso()}})
    return _public_app(await _get_app(app_id), user["role"])


@credit_router.get("/applications/{app_id}/audit")
async def get_audit(app_id: str, user: dict = Depends(require_roles(*STAFF))):
    out = []
    async for e in db.credit_audit.find({"application_id": app_id}).sort("timestamp", -1):
        out.append(clean(e))
    return out


# --------------------------------------------------------------- dashboard ----
@credit_router.get("/dashboard")
async def dashboard(user: dict = Depends(require_roles(*STAFF, "lender"))):
    await ensure_seed()
    q = {}
    role = user["role"]
    if role in ("school_admin", "finance", "counsellor", "manager") and user.get("school_id"):
        q["school_id"] = user["school_id"]
    elif role == "lender":
        q["workflow.submitted_lender"] = user.get("lender_id")
    apps = [a async for a in db.credit_applications.find(q)]

    total = len(apps)
    def dstatus(a): return a.get("decision", {}).get("status")
    approved = sum(1 for a in apps if dstatus(a) in ("Approved", "Conditional Approval"))
    rejected = sum(1 for a in apps if dstatus(a) == "Reject")
    referred = sum(1 for a in apps if dstatus(a) == "Refer")
    sanctioned = [a for a in apps if a.get("status") == "sanctioned"]
    sanction_amount = sum(a.get("workflow", {}).get("sanction_amount", 0) or a.get("fee", {}).get("loan_amount", 0) for a in sanctioned)
    total_disbursal_req = sum(a.get("fee", {}).get("loan_amount", 0) for a in apps)

    # decision distribution
    dist = {}
    for a in apps:
        s = dstatus(a) or "Pending"
        dist[s] = dist.get(s, 0) + 1
    decision_dist = [{"name": k, "value": v} for k, v in dist.items()]

    # lender-wise performance
    lenders = {l["id"]: l["name"] async for l in db.lenders.find()}
    lender_perf = {}
    for a in apps:
        lid = a.get("decision", {}).get("recommended_lender_id")
        if lid:
            name = lenders.get(lid, "Other")
            lp = lender_perf.setdefault(name, {"lender": name, "recommended": 0, "avg_prob": 0, "_p": []})
            lp["recommended"] += 1
            for e in a.get("decision", {}).get("per_lender", []):
                if e["lender_id"] == lid:
                    lp["_p"].append(e["approval_probability"])
    lender_perf_list = []
    for lp in lender_perf.values():
        lp["avg_prob"] = round(sum(lp["_p"]) / len(lp["_p"]) * 100) if lp["_p"] else 0
        lp.pop("_p", None)
        lender_perf_list.append(lp)

    # school-wise
    school_names = {str(s["_id"]): s["name"] async for s in db.schools.find()}
    school_map = {}
    for a in apps:
        sn = school_names.get(a.get("school_id"), "Unassigned")
        school_map[sn] = school_map.get(sn, 0) + 1
    school_dist = [{"school": k, "applications": v} for k, v in school_map.items()]

    avg_score = round(sum(a.get("internal_score", {}).get("score", 0) for a in apps if a.get("internal_score")) /
                      max(1, sum(1 for a in apps if a.get("internal_score"))))

    return {
        "kpis": {
            "total": total, "approved": approved, "rejected": rejected, "referred": referred,
            "approval_rate": round(approved / total * 100) if total else 0,
            "sanctioned_count": len(sanctioned), "sanction_amount": round(sanction_amount),
            "requested_amount": round(total_disbursal_req), "avg_internal_score": avg_score,
        },
        "decision_dist": decision_dist,
        "lender_performance": lender_perf_list,
        "school_distribution": school_dist,
    }


# --------------------------------------------------------------- AI helpers ---
async def _ai_bank_statement(content: bytes, filename: str) -> Optional[dict]:
    if not EMERGENT_LLM_KEY:
        return None
    import json, tempfile
    from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
    suffix = ".pdf" if filename.lower().endswith(".pdf") else ".txt"
    mime = "application/pdf" if suffix == ".pdf" else "text/plain"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tf.write(content)
        path = tf.name
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id="bank-" + uuid.uuid4().hex[:8],
                   system_message="You are a bank-statement analyst. Output ONLY valid JSON.").with_model("gemini", "gemini-2.5-flash")
    prompt = ("Analyse this bank statement and return JSON with keys: salary (monthly, number), "
              "business_income (number), existing_emi (monthly total, number), cheque_bounces (int), "
              "cash_deposits (number), avg_monthly_balance (number), income_consistency (0-100 int), "
              "repayment_behaviour ('Good'|'Fair'|'Poor'). Return ONLY JSON.")
    resp = await chat.send_message(UserMessage(text=prompt, file_contents=[FileContentWithMimeType(file_path=path, mime_type=mime)]))
    text = resp if isinstance(resp, str) else str(resp)
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return None
    data = json.loads(text[s:e + 1])
    data["source"] = "AI-analysed (" + filename + ")"
    data["months_analysed"] = 6
    return data


async def _ai_ocr(content: bytes, filename: str, doc_type: str) -> dict:
    if not EMERGENT_LLM_KEY:
        return {"note": "OCR unavailable"}
    import json, tempfile
    from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
    fl = filename.lower()
    if fl.endswith(".pdf"):
        mime, suffix = "application/pdf", ".pdf"
    elif fl.endswith((".png",)):
        mime, suffix = "image/png", ".png"
    else:
        mime, suffix = "image/jpeg", ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tf.write(content)
        path = tf.name
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id="ocr-" + uuid.uuid4().hex[:8],
                   system_message="You extract structured fields from Indian KYC/income documents. Output ONLY JSON.").with_model("gemini", "gemini-2.5-flash")
    prompt = (f"Extract fields from this {doc_type or 'document'}. Return JSON with any of: "
              "name, pan, aadhaar, dob, address, employer, gross_salary, net_salary, annual_income. "
              "Only include fields present. Return ONLY JSON.")
    resp = await chat.send_message(UserMessage(text=prompt, file_contents=[FileContentWithMimeType(file_path=path, mime_type=mime)]))
    text = resp if isinstance(resp, str) else str(resp)
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"note": "No fields extracted"}
    return json.loads(text[s:e + 1])
