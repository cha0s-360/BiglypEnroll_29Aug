from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import math
import random
import re
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Annotated

from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends, UploadFile, File
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, ConfigDict
from bson import ObjectId

from fee_parser import parse_fee_file
from credit import credit_router, ensure_seed as ensure_credit_seed
from extras import create_extras_router, seed_extras

# Populated at startup with helpers returned by the extras factory
EXTRAS = {}

# ---------------------------------------------------------------- DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ACADEMIC_YEAR = "2025-26"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("biglyp")

app = FastAPI(title="BiglypEnroll API")
api = APIRouter(prefix="/api")

PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v))]

ROLES = ["super_admin", "school_admin", "counsellor", "finance", "parent",
         "manager", "admission", "legal", "credit_ops", "lender"]
# Roles that belong to a school staff team (can be added via Team management)
TEAM_ROLES = ["school_admin", "manager", "finance", "counsellor", "admission", "legal"]
# Roles allowed into the staff dashboard
STAFF_ROLES = ["super_admin", "school_admin", "manager", "finance",
               "counsellor", "admission", "legal", "credit_ops"]

# ------------------------------------------------------------ helpers ---------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
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


def public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "name": u.get("name"),
        "email": u.get("email"),
        "role": u.get("role"),
        "school_id": u.get("school_id"),
    }


# ------------------------------------------------------------ models ----------
class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "parent"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SchoolIn(BaseModel):
    name: str
    type: str = "School"
    spoc_name: str = ""
    spoc_email: str = ""
    phone: str = ""
    address: str = ""


PAYMENT_OPTIONS_DEFAULT = {"emi": True, "auto_debit": True, "full": True}


def normalize_payment_options(po) -> dict:
    """Coerce to the 3 known flags; if none are enabled fall back to defaults."""
    if not isinstance(po, dict):
        return dict(PAYMENT_OPTIONS_DEFAULT)
    out = {k: bool(po.get(k, True)) for k in PAYMENT_OPTIONS_DEFAULT}
    if not any(out.values()):
        return dict(PAYMENT_OPTIONS_DEFAULT)
    return out


class OnboardingIn(BaseModel):
    campuses: List[dict] = []
    courses: List[dict] = []
    team: List[dict] = []
    multi_account_enabled: bool = False
    settlement_accounts: List[dict] = []
    payment_options: Optional[dict] = None
    complete: bool = False


class FeeHead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    amount: float
    frequency: str = "Yearly"
    grades: List[str] = []
    account_id: Optional[str] = None


class Scholarship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str = "percentage"  # percentage | fixed
    value: float = 0


class FeeStructureIn(BaseModel):
    fee_heads: List[FeeHead] = []
    scholarships: List[Scholarship] = []
    early_bird_discount: float = 0
    late_fee: float = 0
    published: bool = False


class StudentIn(BaseModel):
    name: str
    grade: str
    program: str = ""
    parent_email: str = ""
    roll_no: str = ""


class StudentUpdateIn(BaseModel):
    name: Optional[str] = None
    grade: Optional[str] = None
    program: Optional[str] = None
    parent_email: Optional[str] = None
    roll_no: Optional[str] = None


class TeamMemberIn(BaseModel):
    name: str
    email: EmailStr
    role: str = "counsellor"
    password: str = "biglyp123"
    campus: str = ""


class TeamUpdateIn(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    campus: Optional[str] = None


class PayIn(BaseModel):
    student_id: str
    fee_head_ids: List[str]
    mode: str = "UPI"
    tenure: int = 12
    down_payment: float = 0
    use_wallet: bool = False


class FinancingPreviewIn(BaseModel):
    amount: float
    down_payment: float = 0
    tenure: int = 6


class MandateIn(BaseModel):
    student_id: str
    fee_head_ids: List[str]
    frequency: str = "quarterly"  # "quarterly" | "semi"
    rail: str = "UPI AutoPay"
    bank_name: str
    account_holder: str
    account_number: str
    ifsc: str
    upfront_mode: str = "UPI"


# ------------------------------------------------------------ auth ------------
@api.post("/auth/register")
async def register(body: RegisterIn):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    role = body.role if body.role in ROLES else "parent"
    doc = {
        "name": body.name,
        "email": email,
        "password_hash": hash_password(body.password),
        "role": role,
        "school_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    token = create_access_token(uid, email, role)
    return {"token": token, "user": {"id": uid, "name": body.name, "email": email, "role": role, "school_id": None}}


@api.post("/auth/login")
async def login(body: LoginIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    uid = str(user["_id"])
    token = create_access_token(uid, email, user["role"])
    return {"token": token, "user": {"id": uid, "name": user["name"], "email": email,
                                     "role": user["role"], "school_id": user.get("school_id")}}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@api.post("/auth/logout")
async def logout():
    return {"ok": True}


# ------------------------------------------------------------ school ----------
async def get_user_school_id(user: dict) -> str:
    sid = user.get("school_id")
    if not sid:
        raise HTTPException(status_code=400, detail="No school linked to this account")
    return sid


@api.get("/school")
async def get_school(user: dict = Depends(get_current_user)):
    sid = user.get("school_id")
    if not sid:
        return None
    school = await db.schools.find_one({"_id": ObjectId(sid)})
    if not school:
        return None
    school["id"] = str(school.pop("_id"))
    return school


@api.get("/school/list")
async def list_schools(user: dict = Depends(require_roles("super_admin"))):
    out = []
    async for s in db.schools.find():
        s["id"] = str(s.pop("_id"))
        out.append(s)
    return out


@api.post("/school")
async def upsert_school(body: SchoolIn, user: dict = Depends(require_roles("super_admin", "school_admin"))):
    sid = user.get("school_id")
    data = body.model_dump()
    if sid:
        await db.schools.update_one({"_id": ObjectId(sid)}, {"$set": data})
        school = await db.schools.find_one({"_id": ObjectId(sid)})
    else:
        data.update({
            "campuses": [], "courses": [], "team": [],
            "multi_account_enabled": False, "settlement_accounts": [],
            "payment_options": dict(PAYMENT_OPTIONS_DEFAULT),
            "onboarding_complete": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        res = await db.schools.insert_one(data)
        sid = str(res.inserted_id)
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"school_id": sid}})
        school = await db.schools.find_one({"_id": ObjectId(sid)})
    school["id"] = str(school.pop("_id"))
    return school


@api.post("/school/onboarding")
async def save_onboarding(body: OnboardingIn, user: dict = Depends(require_roles("super_admin", "school_admin"))):
    sid = await get_user_school_id(user)
    upd = body.model_dump()
    upd["onboarding_complete"] = body.complete
    upd.pop("complete", None)
    if upd.get("payment_options") is None:
        upd.pop("payment_options", None)
    else:
        upd["payment_options"] = normalize_payment_options(upd["payment_options"])
    await db.schools.update_one({"_id": ObjectId(sid)}, {"$set": upd})
    school = await db.schools.find_one({"_id": ObjectId(sid)})
    school["id"] = str(school.pop("_id"))
    return school


# --------------------------------------------------------- team management ----
@api.get("/school/team")
async def list_team(user: dict = Depends(require_roles(*STAFF_ROLES))):
    sid = await get_user_school_id(user)
    out = []
    async for u in db.users.find({"school_id": sid, "role": {"$in": TEAM_ROLES}}):
        out.append({
            "id": str(u["_id"]), "name": u.get("name"), "email": u.get("email"),
            "role": u.get("role"), "campus": u.get("campus", ""),
            "is_self": str(u["_id"]) == user["id"],
        })
    return out


@api.post("/school/team")
async def add_team_member(body: TeamMemberIn, user: dict = Depends(require_roles("super_admin", "school_admin", "manager"))):
    sid = await get_user_school_id(user)
    role = body.role if body.role in TEAM_ROLES else "counsellor"
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        if existing.get("school_id") and existing["school_id"] != sid:
            raise HTTPException(status_code=400, detail="This email already belongs to another institute")
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"school_id": sid, "role": role, "name": body.name, "campus": body.campus}},
        )
        uid = str(existing["_id"])
    else:
        res = await db.users.insert_one({
            "name": body.name, "email": email,
            "password_hash": hash_password(body.password),
            "role": role, "school_id": sid, "campus": body.campus,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        uid = str(res.inserted_id)
    return {"id": uid, "name": body.name, "email": email, "role": role, "campus": body.campus, "is_self": False}


@api.put("/school/team/{member_id}")
async def update_team_member(member_id: str, body: TeamUpdateIn, user: dict = Depends(require_roles("super_admin", "school_admin", "manager"))):
    sid = await get_user_school_id(user)
    member = await db.users.find_one({"_id": ObjectId(member_id), "school_id": sid})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "role" in upd and upd["role"] not in TEAM_ROLES:
        upd.pop("role")
    if upd:
        await db.users.update_one({"_id": ObjectId(member_id)}, {"$set": upd})
    m = await db.users.find_one({"_id": ObjectId(member_id)})
    return {"id": member_id, "name": m.get("name"), "email": m.get("email"),
            "role": m.get("role"), "campus": m.get("campus", "")}


@api.delete("/school/team/{member_id}")
async def remove_team_member(member_id: str, user: dict = Depends(require_roles("super_admin", "school_admin", "manager"))):
    sid = await get_user_school_id(user)
    if member_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    member = await db.users.find_one({"_id": ObjectId(member_id), "school_id": sid})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    await db.users.delete_one({"_id": ObjectId(member_id)})
    return {"ok": True}


# --------------------------------------------------------- fee structure ------
@api.get("/fees/structure")
async def get_fee_structure(user: dict = Depends(get_current_user)):
    sid = await get_user_school_id(user)
    fs = await db.fee_structures.find_one({"school_id": sid})
    if not fs:
        return {"school_id": sid, "fee_heads": [], "scholarships": [],
                "early_bird_discount": 0, "late_fee": 0, "published": False}
    fs["id"] = str(fs.pop("_id"))
    return fs


@api.post("/fees/structure")
async def save_fee_structure(body: FeeStructureIn, user: dict = Depends(require_roles("super_admin", "school_admin", "finance"))):
    sid = await get_user_school_id(user)
    data = body.model_dump()
    data["school_id"] = sid
    await db.fee_structures.update_one({"school_id": sid}, {"$set": data}, upsert=True)
    fs = await db.fee_structures.find_one({"school_id": sid})
    fs["id"] = str(fs.pop("_id"))
    return fs


@api.post("/fees/parse-excel")
async def parse_excel(file: UploadFile = File(...),
                      user: dict = Depends(require_roles("super_admin", "school_admin", "finance"))):
    content = await file.read()
    try:
        heads = await parse_fee_file(content, file.filename)
    except Exception as e:
        logger.exception("fee parse failed")
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
    for h in heads:
        h["id"] = str(uuid.uuid4())
        h["account_id"] = None
    return {"fee_heads": heads}


# ------------------------------------------------------------ students --------
@api.get("/students")
async def list_students(user: dict = Depends(require_roles(*STAFF_ROLES))):
    sid = await get_user_school_id(user)
    out = []
    async for s in db.students.find({"school_id": sid}):
        s["id"] = str(s.pop("_id"))
        out.append(s)
    return out


@api.post("/students")
async def add_student(body: StudentIn, user: dict = Depends(require_roles("super_admin", "school_admin", "counsellor", "admission", "manager"))):
    sid = await get_user_school_id(user)
    parent_id = None
    if body.parent_email:
        parent = await db.users.find_one({"email": body.parent_email.lower()})
        if parent:
            parent_id = str(parent["_id"])
            await db.users.update_one({"_id": parent["_id"]}, {"$set": {"school_id": sid}})
    doc = body.model_dump()
    doc.update({"school_id": sid, "parent_id": parent_id,
                "created_at": datetime.now(timezone.utc).isoformat()})
    res = await db.students.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


@api.put("/students/{student_id}")
async def edit_student(student_id: str, body: StudentUpdateIn, user: dict = Depends(require_roles("super_admin", "school_admin", "counsellor", "admission", "manager"))):
    sid = await get_user_school_id(user)
    student = await db.students.find_one({"_id": ObjectId(student_id), "school_id": sid})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None and k != "parent_email"}
    if body.parent_email is not None:
        if body.parent_email == "":
            upd["parent_id"] = None
        else:
            parent = await db.users.find_one({"email": body.parent_email.lower()})
            if not parent:
                raise HTTPException(status_code=400, detail="No account found for that parent email")
            upd["parent_id"] = str(parent["_id"])
            await db.users.update_one({"_id": parent["_id"]}, {"$set": {"school_id": sid}})
    if upd:
        await db.students.update_one({"_id": ObjectId(student_id)}, {"$set": upd})
    s = await db.students.find_one({"_id": ObjectId(student_id)})
    s["id"] = str(s.pop("_id"))
    return s


@api.delete("/students/{student_id}")
async def delete_student(student_id: str, user: dict = Depends(require_roles("super_admin", "school_admin", "manager"))):
    sid = await get_user_school_id(user)
    student = await db.students.find_one({"_id": ObjectId(student_id), "school_id": sid})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await db.students.delete_one({"_id": ObjectId(student_id)})
    await db.payments.delete_many({"student_id": student_id})
    return {"ok": True}


# --------------------------------------------------- parent fee journey -------
def frequency_months(freq: str) -> int:
    return {"Yearly": 12, "Half-Yearly": 6, "Quarterly": 3, "Monthly": 1, "One-Time": 0}.get(freq, 12)


async def compute_pending(sid: str, student: dict):
    fs = await db.fee_structures.find_one({"school_id": sid})
    if not fs or not fs.get("published"):
        return []
    grade = student.get("grade", "")
    paid_ids = set()
    async for p in db.payments.find({"student_id": student["id"], "academic_year": ACADEMIC_YEAR, "status": "success"}):
        for item in p.get("items", []):
            paid_ids.add(item["fee_head_id"])
    items = []
    for h in fs.get("fee_heads", []):
        grades = h.get("grades", [])
        if grades and grade not in grades:
            continue
        items.append({
            "fee_head_id": h["id"],
            "name": h["name"],
            "amount": h["amount"],
            "frequency": h["frequency"],
            "paid": h["id"] in paid_ids,
        })
    # Per-student extra/premium fee heads (additive) — used to seed high-value
    # (> ₹3 lakh) students so the document-upload financing flow can be tested.
    for h in student.get("extra_fee_heads", []):
        items.append({
            "fee_head_id": h["id"],
            "name": h["name"],
            "amount": h["amount"],
            "frequency": h.get("frequency", "Yearly"),
            "paid": h["id"] in paid_ids,
        })
    return items


@api.get("/parent/children")
async def parent_children(user: dict = Depends(get_current_user)):
    out = []
    async for s in db.students.find({"parent_id": user["id"]}):
        s["id"] = str(s.pop("_id"))
        out.append(s)
    return out


async def _resolve_student(student_id: str, user: dict) -> dict:
    student = await db.students.find_one({"_id": ObjectId(student_id)})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student["id"] = str(student.pop("_id"))
    if user["role"] == "parent" and student.get("parent_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your child")
    return student


@api.get("/parent/fees/{student_id}")
async def parent_fees(student_id: str, user: dict = Depends(get_current_user)):
    student = await _resolve_student(student_id, user)
    pending = await compute_pending(student["school_id"], student)
    fs = await db.fee_structures.find_one({"school_id": student["school_id"]})
    scholarships = fs.get("scholarships", []) if fs else []
    school = await db.schools.find_one({"_id": ObjectId(student["school_id"])})
    payment_options = normalize_payment_options((school or {}).get("payment_options"))
    return {"student": student, "items": pending, "academic_year": ACADEMIC_YEAR,
            "scholarships": scholarships, "payment_options": payment_options}


@api.post("/parent/pay")
async def parent_pay(body: PayIn, user: dict = Depends(get_current_user)):
    student = await _resolve_student(body.student_id, user)
    pending = await compute_pending(student["school_id"], student)
    selected = [i for i in pending if i["fee_head_id"] in body.fee_head_ids and not i["paid"]]
    if not selected:
        raise HTTPException(status_code=400, detail="No payable items selected")
    total = sum(i["amount"] for i in selected)
    receipt_no = "BLP-" + datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

    # apply reward-wallet credit if requested
    wallet_applied = 0.0
    if body.use_wallet and user["role"] == "parent" and EXTRAS.get("spend_wallet"):
        wallet_applied = await EXTRAS["spend_wallet"](user["id"], total)
    net_paid = round(total - wallet_applied, 2)

    doc = {
        "student_id": student["id"],
        "student_name": student["name"],
        "school_id": student["school_id"],
        "items": selected,
        "amount": total,
        "wallet_applied": wallet_applied,
        "net_paid": net_paid,
        "gst": round(total * 0.18, 2),
        "mode": body.mode,
        "status": "success",
        "financing": False,
        "receipt_no": receipt_no,
        "academic_year": ACADEMIC_YEAR,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.payments.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    # reward: full/upfront payment earns 2x points + 1% cashback
    if user["role"] == "parent" and EXTRAS.get("award_rewards"):
        doc["rewards_earned"] = await EXTRAS["award_rewards"](
            user["id"], student["school_id"], total, "full")
    return doc


DOC_THRESHOLD = 300000.0  # financing above this needs income documents


def _financing_economics(financed: float, tenure: int, down: float) -> dict:
    """Shared economics for the 0% EMI product: a small (1%) one-time processing
    fee + GST, everything else is genuinely interest-free."""
    financed = max(0.0, float(financed))
    tenure = max(1, int(tenure))
    down = max(0.0, float(down))
    if financed > 0:
        pf_base = max(499.0, round(financed * 0.01))
        processing_fee = round(pf_base * 1.18)  # incl. 18% GST
        apr = round((processing_fee / financed) * (12.0 / tenure) * 100.0, 1)
    else:
        processing_fee, apr = 0.0, 0.0
    return {
        "processing_fee": processing_fee,
        "apr": apr,
        "total_repayment": round(financed),   # 0% interest -> EMIs sum to financed
        "amount_payable_now": round(down + processing_fee),
        "requires_docs": financed > DOC_THRESHOLD,
        "doc_threshold": DOC_THRESHOLD,
    }


FINANCING_MIN_DEFAULT = 25000.0


async def _active_financing_bank() -> dict | None:
    """The bank whose config drives the parent 0% EMI flow (first active one)."""
    return await db.financing_banks.find_one({"active": True})


def _bank_flow_cfg(bank: dict | None) -> dict:
    return {
        "id": (bank or {}).get("id"),
        "name": (bank or {}).get("name"),
        "advance_emi": bool((bank or {}).get("advance_emi")),
        "min_loan_amount": float((bank or {}).get("min_loan_amount", FINANCING_MIN_DEFAULT)),
        # Bucket 4 Screen 3 (KYC) — driven by the OPS bank config
        "location_match": bool((bank or {}).get("location_match_aadhaar")),
        "name_match_rule": (bank or {}).get("name_match_rule", "aadhaar"),  # profile | pan | aadhaar
    }


@api.get("/parent/financing/bank-config")
async def financing_bank_config(user: dict = Depends(get_current_user)):
    """Screen 1 reads this to know min loan amount + advance-EMI vs down-payment mode."""
    return _bank_flow_cfg(await _active_financing_bank())


class ProfileUpdateIn(BaseModel):
    name: str | None = None
    dob: str | None = None


@api.put("/parent/profile")
async def update_parent_profile(body: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    """Bucket 4 Screen 3 (KYC) — used by the name/DOB-mismatch correction flow so a
    corrected name/DOB becomes the value of record on the parent's profile."""
    upd = {}
    if body.name and body.name.strip():
        upd["name"] = body.name.strip()
    if body.dob and body.dob.strip():
        upd["dob"] = body.dob.strip()
    if upd:
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": upd})
    return {"ok": True, **upd}


@api.post("/parent/financing/preview")
async def financing_preview(body: FinancingPreviewIn, user: dict = Depends(get_current_user)):
    cfg = _bank_flow_cfg(await _active_financing_bank())
    advance_mode = cfg["advance_emi"]
    min_loan = cfg["min_loan_amount"]
    total = max(0.0, float(body.amount))
    tenure = max(3, min(12, body.tenure))
    if advance_mode:
        # Advance EMI: the 1st installment counts as EMI #1 (NOT a reduction of the loan).
        down = 0.0
        financed = total
    else:
        # Optional down payment reduces the financed amount.
        down = max(0.0, min(total, float(body.down_payment)))
        financed = max(0.0, total - down)
    emi = math.ceil(financed / tenure) if tenure else 0
    advance_amount = emi if advance_mode else 0
    econ = _financing_economics(financed, tenure, down)
    amount_payable_now = round((advance_amount if advance_mode else down) + econ["processing_fee"])
    meets_min = financed >= min_loan
    schedule = []
    base = datetime.now(timezone.utc)
    for i in range(tenure):
        due = base + timedelta(days=30 * (i + 1))
        label = "1st Installment (Advance)" if (advance_mode and i == 0) else f"EMI {i + 1}"
        schedule.append({"month": i + 1, "label": label, "due_date": due.strftime("%d %b %Y"),
                         "amount": emi, "status": "upcoming"})
    return {"financed_amount": financed, "down_payment": down,
            "tenure": tenure, "emi": emi, "interest": "0%", "schedule": schedule,
            **econ, "amount_payable_now": amount_payable_now,
            "advance_mode": advance_mode, "advance_amount": advance_amount,
            "min_loan_amount": min_loan, "meets_min": meets_min,
            "bank_name": cfg["name"]}


@api.post("/parent/pay-financing")
async def pay_financing(body: PayIn, user: dict = Depends(get_current_user)):
    student = await _resolve_student(body.student_id, user)
    pending = await compute_pending(student["school_id"], student)
    selected = [i for i in pending if i["fee_head_id"] in body.fee_head_ids and not i["paid"]]
    if not selected:
        raise HTTPException(status_code=400, detail="No payable items selected")
    total = sum(i["amount"] for i in selected)
    cfg = _bank_flow_cfg(await _active_financing_bank())
    advance_mode = cfg["advance_emi"]
    min_loan = cfg["min_loan_amount"]
    tenure = max(3, min(12, body.tenure))
    if advance_mode:
        down = 0.0
        financed = total
    else:
        down = max(0.0, min(total, body.down_payment))
        financed = max(0.0, total - down)
    if financed < min_loan:
        raise HTTPException(
            status_code=400,
            detail=f"Financing amount {int(financed)} is below the minimum loan amount "
                   f"{int(min_loan)} for {cfg['name'] or 'the selected bank'}.")
    emi = math.ceil(financed / tenure) if tenure else 0
    advance_amount = emi if advance_mode else 0
    base = datetime.now(timezone.utc)
    main_receipt = "BLP-FIN-" + uuid.uuid4().hex[:6].upper()
    schedule = []
    for i in range(tenure):
        due = base + timedelta(days=30 * i)  # EMI 1 settled at activation
        label = "1st Installment (Advance)" if (advance_mode and i == 0) else f"EMI {i + 1}"
        if i == 0:
            status, rail, rcpt = "paid", "UPI AutoPay", main_receipt
        elif i == 1:
            status, rail, rcpt = "scheduled", "eNACH Mandate", None
        else:
            status, rail, rcpt = "upcoming", "eNACH Mandate", None
        schedule.append({"month": i + 1, "label": label,
                         "due_date": due.strftime("%d %b %Y"),
                         "amount": emi, "status": status, "rail": rail, "receipt_no": rcpt})
    receipt_no = main_receipt
    econ = _financing_economics(financed, tenure, down)
    amount_payable_now = round((advance_amount if advance_mode else down) + econ["processing_fee"])
    doc = {
        "student_id": student["id"], "student_name": student["name"],
        "school_id": student["school_id"], "items": selected, "amount": total,
        "gst": round(total * 0.18, 2), "mode": "Financing (EMI)", "status": "success",
        "financing": True, "plan_type": "EMI", "tenure": tenure, "emi": emi,
        "down_payment": down, "financed_amount": financed, "schedule": schedule,
        "processing_fee": econ["processing_fee"], "apr": econ["apr"],
        "total_repayment": econ["total_repayment"],
        "advance_mode": advance_mode, "advance_amount": advance_amount,
        "amount_payable_now": amount_payable_now,
        "bank_name": cfg["name"],
        "agreement_id": "BLP-AGR-" + uuid.uuid4().hex[:8].upper(),
        "receipt_no": receipt_no, "academic_year": ACADEMIC_YEAR,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.payments.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    if user["role"] == "parent" and EXTRAS.get("award_rewards"):
        doc["rewards_earned"] = await EXTRAS["award_rewards"](
            user["id"], student["school_id"], total, "financing")
    return doc


@api.get("/parent/financing/active/{student_id}")
async def active_financing(student_id: str, user: dict = Depends(get_current_user)):
    student = await _resolve_student(student_id, user)
    out = []
    async for p in db.payments.find({"student_id": student["id"], "plan_type": "EMI"}).sort("created_at", -1):
        p["id"] = str(p.pop("_id"))
        out.append(p)
    return out


class EmiPayIn(BaseModel):
    payment_id: str
    month: int
    mode: str = "UPI"


@api.post("/parent/financing/pay-emi")
async def pay_emi(body: EmiPayIn, user: dict = Depends(get_current_user)):
    p = await db.payments.find_one({"_id": ObjectId(body.payment_id)})
    if not p:
        raise HTTPException(status_code=404, detail="Financing plan not found")
    await _resolve_student(p["student_id"], user)  # ownership guard
    sched = p.get("schedule", [])
    found = False
    for s in sched:
        if s["month"] == body.month and s["status"] != "paid":
            s["status"] = "paid"
            s["rail"] = f"{body.mode} (Manual)"
            s["receipt_no"] = "BLP-EMI-" + uuid.uuid4().hex[:6].upper()
            found = True
    if not found:
        raise HTTPException(status_code=400, detail="Installment already paid or not found")
    # re-derive statuses for the remaining unpaid installments
    first_unpaid_set = False
    for s in sched:
        if s["status"] == "paid":
            continue
        s["status"] = "scheduled" if not first_unpaid_set else "upcoming"
        first_unpaid_set = True
    await db.payments.update_one({"_id": ObjectId(body.payment_id)}, {"$set": {"schedule": sched}})
    p["schedule"] = sched
    p["id"] = str(p.pop("_id"))
    return p


class VerifyAccountIn(BaseModel):
    account_number: str
    ifsc: str


@api.post("/school/verify-account")
async def verify_account(body: VerifyAccountIn, user: dict = Depends(get_current_user)):
    """SIMULATED penny-drop: resolves the account holder name from account no + IFSC."""
    acc = body.account_number.strip()
    ifsc = body.ifsc.strip().upper()
    if len(acc) < 6 or len(ifsc) < 6:
        raise HTTPException(status_code=400, detail="Enter a valid account number and IFSC")
    import hashlib
    names = ["Horizon International School Trust", "Sunrise Education Society",
             "Green Valley Academy A/C", "St. Xavier Institute Fund",
             "Oakridge School Collections", "Silver Oak Education Trust"]
    h = int(hashlib.md5((acc + ifsc).encode()).hexdigest(), 16)
    return {"account_name": names[h % len(names)], "bank": ifsc[:4] + " Bank", "verified": True}


PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class CibilCheckIn(BaseModel):
    pan: str
    dob: Optional[str] = None
    consent: bool = False


@api.post("/parent/cibil-check")
async def cibil_check(body: CibilCheckIn, user: dict = Depends(get_current_user)):
    """SIMULATED soft CIBIL pull: deterministic score from PAN (no bureau hit)."""
    pan = (body.pan or "").strip().upper()
    if not PAN_RE.match(pan):
        raise HTTPException(status_code=400, detail="Enter a valid PAN (e.g. ABCDE1234F)")
    if not body.consent:
        raise HTTPException(status_code=400, detail="Consent is required for the eligibility check")

    import hashlib
    h = int(hashlib.md5(pan.encode()).hexdigest(), 16)
    # Deterministic score in 690..830 (soft-pull safe demo band — most PANs are approved)
    score = 690 + (h % 141)

    # Special demo hooks: PAN starting with "ZZZZZ" simulates low score; "AAAAA" simulates excellent
    if pan.startswith("ZZZZZ"):
        score = 540 + (h % 40)
    elif pan.startswith("AAAAA"):
        score = 800 + (h % 51)

    if score >= 780:
        band, band_color = "Excellent", "emerald"
    elif score >= 720:
        band, band_color = "Good", "blue"
    elif score >= 670:
        band, band_color = "Fair", "amber"
    else:
        band, band_color = "Poor", "red"

    approved = score >= 670
    max_eligible = 250000 if score >= 780 else 150000 if score >= 720 else 75000 if score >= 670 else 0
    # Reason bullets for the UI
    factors = [
        {"label": "Payment history", "status": "positive" if score >= 720 else "neutral"},
        {"label": "Credit utilization", "status": "positive" if score >= 700 else "neutral"},
        {"label": "Credit mix & age", "status": "positive" if score >= 750 else "neutral"},
        {"label": "Recent enquiries (soft pull)", "status": "neutral"},
    ]
    # Bucket 4 — Screen 2 eligibility gate: check the credit score against the
    # bank's CONFIGURED threshold (hardcoded default 750; wire to Bucket 1 later).
    bank = await _active_financing_bank()
    emi_threshold = int((bank or {}).get("min_credit_score") or 750)
    emi_eligible = score >= emi_threshold

    decision = (
        "Congratulations! You are pre-approved for 0% EMI financing."
        if approved
        else "Your current score needs a boost. We recommend improving credit health and retrying later."
    )
    return {
        "pan_masked": pan[:3] + "XXX" + pan[-2:],
        "score": score,
        "band": band,
        "band_color": band_color,
        "approved": approved,
        "emi_threshold": emi_threshold,
        "emi_eligible": emi_eligible,
        "max_eligible": max_eligible,
        "bureau": "CIBIL (TransUnion)",
        "pull_type": "Soft — no impact on credit score",
        "factors": factors,
        "decision": decision,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@api.post("/parent/mandate")
async def setup_mandate(body: MandateIn, user: dict = Depends(get_current_user)):
    student = await _resolve_student(body.student_id, user)
    pending = await compute_pending(student["school_id"], student)
    selected = [i for i in pending if i["fee_head_id"] in body.fee_head_ids and not i["paid"]]
    if not selected:
        raise HTTPException(status_code=400, detail="No payable items selected")
    total = sum(i["amount"] for i in selected)

    freq = body.frequency.lower()
    n = 4 if freq.startswith("quart") else 2
    step_months = 3 if n == 4 else 6
    per = round(total / n)
    upfront = total - per * (n - 1)  # keep the sum exact

    base = datetime.now(timezone.utc)
    schedule = []
    for i in range(n):
        due = base if i == 0 else (base + timedelta(days=30 * step_months * i)).replace(day=10)
        label = (f"Q{i + 1}" if n == 4 else f"Term {i + 1}")
        schedule.append({
            "month": i + 1, "label": label,
            "due_date": due.strftime("%d %b %Y"),
            "amount": upfront if i == 0 else per,
            "status": "paid" if i == 0 else "upcoming",
        })

    acct = body.account_number.strip()
    acct_masked = ("•••• " + acct[-4:]) if len(acct) >= 4 else "••••"
    mandate_id = "BLP-MND-" + uuid.uuid4().hex[:8].upper()
    mandate_doc = {
        "id": mandate_id, "student_id": student["id"], "school_id": student["school_id"],
        "frequency": freq, "rail": body.rail, "bank_name": body.bank_name,
        "account_holder": body.account_holder, "account_masked": acct_masked,
        "ifsc": body.ifsc.upper(), "installments": n, "installment_amount": per,
        "upfront_amount": upfront, "total": total, "schedule": schedule,
        "status": "active", "academic_year": ACADEMIC_YEAR,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.mandates.insert_one(mandate_doc)
    mandate_doc.pop("_id", None)

    receipt_no = "BLP-AD-" + uuid.uuid4().hex[:6].upper()
    doc = {
        "student_id": student["id"], "student_name": student["name"],
        "school_id": student["school_id"], "items": selected, "amount": total,
        "gst": round(total * 0.18, 2), "mode": f"Auto-Debit ({body.rail})",
        "status": "success", "financing": False, "auto_debit": True,
        "plan_type": "AutoDebit", "frequency": freq, "installments": n,
        "installment_amount": per, "upfront_amount": upfront,
        "mandate_id": mandate_id, "schedule": schedule,
        "receipt_no": receipt_no, "academic_year": ACADEMIC_YEAR,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.payments.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    rewards_earned = None
    if user["role"] == "parent" and EXTRAS.get("award_rewards"):
        rewards_earned = await EXTRAS["award_rewards"](
            user["id"], student["school_id"], total, "autodebit")
    return {"mandate": mandate_doc, "payment": doc, "rewards_earned": rewards_earned}


@api.get("/parent/payments/{student_id}")
async def parent_payments(student_id: str, user: dict = Depends(get_current_user)):
    student = await _resolve_student(student_id, user)
    out = []
    async for p in db.payments.find({"student_id": student["id"]}).sort("created_at", -1):
        p["id"] = str(p.pop("_id"))
        out.append(p)
    return out


@api.post("/school/reset-demo")
async def reset_demo(user: dict = Depends(require_roles("super_admin", "school_admin"))):
    """Reset demo parent's payments + rewards + notifications so the wallet toggle and
    reminder flows can be re-demoed anytime. Only affects the seeded demo parent
    (parent@biglyp.com) under the caller's school — real parents are untouched."""
    sid = await get_user_school_id(user)
    parent = await db.users.find_one({"email": "parent@biglyp.com", "school_id": sid})
    if not parent:
        return {"ok": True, "note": "No demo parent in this school", "reset": {}}
    pid = str(parent["_id"])
    students = []
    async for s in db.students.find({"parent_id": pid, "school_id": sid}):
        students.append(str(s["_id"]))
    p_del = await db.payments.delete_many({"student_id": {"$in": students}, "school_id": sid})
    r_del = await db.rewards_accounts.delete_many({"parent_id": pid})
    t_del = await db.rewards_txns.delete_many({"parent_id": pid})
    red_del = await db.rewards_redemptions.delete_many({"parent_id": pid})
    n_del = await db.notifications.delete_many({"parent_id": pid})
    e_del = await db.email_log.delete_many({"school_id": sid})
    # any active EMI plans (financing) also removed via payments delete above
    logger.info(f"Demo reset for parent={pid}: payments={p_del.deleted_count} rewards_txns={t_del.deleted_count}")
    return {
        "ok": True,
        "reset": {
            "students_affected": len(students),
            "payments_deleted": p_del.deleted_count,
            "rewards_accounts_deleted": r_del.deleted_count,
            "rewards_txns_deleted": t_del.deleted_count,
            "redemptions_deleted": red_del.deleted_count,
            "notifications_deleted": n_del.deleted_count,
            "email_logs_deleted": e_del.deleted_count,
        },
    }


# ------------------------------------------------------------ analytics -------
@api.get("/analytics/overview")
async def analytics(user: dict = Depends(require_roles(*STAFF_ROLES))):
    sid = await get_user_school_id(user)
    payments = []
    async for p in db.payments.find({"school_id": sid, "status": "success"}):
        payments.append(p)

    total_collected = sum(p["amount"] for p in payments)
    financed = sum(p["amount"] for p in payments if p.get("financing"))

    # Outstanding across all students
    students = []
    async for s in db.students.find({"school_id": sid}):
        s["id"] = str(s["_id"])
        students.append(s)
    outstanding = 0.0
    overdue_count = 0
    for s in students:
        pending = await compute_pending(sid, s)
        due = sum(i["amount"] for i in pending if not i["paid"])
        outstanding += due
        if due > 0:
            overdue_count += 1

    # mode split
    mode_map = {}
    for p in payments:
        mode_map[p["mode"]] = mode_map.get(p["mode"], 0) + p["amount"]
    mode_split = [{"name": k, "value": round(v)} for k, v in mode_map.items()]

    # monthly trend (last 6 months)
    months = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        m = (now.replace(day=1) - timedelta(days=30 * i))
        key = m.strftime("%Y-%m")
        label = m.strftime("%b")
        amt = 0.0
        for p in payments:
            try:
                pd_dt = datetime.fromisoformat(p["created_at"])
                if pd_dt.strftime("%Y-%m") == key:
                    amt += p["amount"]
            except Exception:
                pass
        months.append({"month": label, "collected": round(amt)})

    # aging buckets (simplified against outstanding)
    aging = [
        {"bucket": "0-30 days", "amount": round(outstanding * 0.5)},
        {"bucket": "31-60 days", "amount": round(outstanding * 0.3)},
        {"bucket": "61-90 days", "amount": round(outstanding * 0.15)},
        {"bucket": "90+ days", "amount": round(outstanding * 0.05)},
    ]

    # admission funnel
    total_students = len(students)
    funnel = [
        {"stage": "Inquiries", "count": max(total_students * 4, 12)},
        {"stage": "Applications", "count": max(total_students * 3, 9)},
        {"stage": "Interviews", "count": max(total_students * 2, 6)},
        {"stage": "Offers", "count": max(int(total_students * 1.4), 4)},
        {"stage": "Enrolled", "count": total_students},
    ]

    return {
        "kpis": {
            "total_collected": round(total_collected),
            "financed_disbursals": round(financed),
            "outstanding": round(outstanding),
            "overdue_count": overdue_count,
            "total_students": total_students,
            "transactions": len(payments),
        },
        "mode_split": mode_split,
        "monthly_trend": months,
        "aging": aging,
        "funnel": funnel,
    }


# ------------------------------------------------------------ seed ------------
async def seed():
    await db.users.create_index("email", unique=True)

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@biglyp.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    if not await db.users.find_one({"email": admin_email}):
        await db.users.insert_one({
            "name": "Biglyp Ops", "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role": "super_admin", "school_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # demo school
    school = await db.schools.find_one({"name": "Horizon International School"})
    if not school:
        res = await db.schools.insert_one({
            "name": "Horizon International School", "type": "School",
            "spoc_name": "Meera Iyer", "spoc_email": "meera@horizon.edu",
            "phone": "+91 98765 43210", "address": "Bandra West, Mumbai",
            "campuses": [{"id": str(uuid.uuid4()), "name": "Main Campus", "city": "Mumbai"}],
            "courses": [{"id": str(uuid.uuid4()), "name": g, "duration": "1 yr"}
                        for g in (["LKG", "UKG"] + [f"Class {i}" for i in range(1, 13)])],
            "team": [], "multi_account_enabled": False, "settlement_accounts": [],
            "onboarding_complete": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        school_id = str(res.inserted_id)
    else:
        school_id = str(school["_id"])

    # school admin
    if not await db.users.find_one({"email": "school@biglyp.com"}):
        await db.users.insert_one({
            "name": "Meera Iyer", "email": "school@biglyp.com",
            "password_hash": hash_password("school123"),
            "role": "school_admin", "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await db.users.update_one({"email": "school@biglyp.com"}, {"$set": {"school_id": school_id}})

    # finance user
    if not await db.users.find_one({"email": "finance@biglyp.com"}):
        await db.users.insert_one({
            "name": "Rohan Desai", "email": "finance@biglyp.com",
            "password_hash": hash_password("finance123"),
            "role": "finance", "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # parent user
    parent = await db.users.find_one({"email": "parent@biglyp.com"})
    if not parent:
        pres = await db.users.insert_one({
            "name": "Anjali Sharma", "email": "parent@biglyp.com",
            "password_hash": hash_password("parent123"),
            "role": "parent", "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        parent_id = str(pres.inserted_id)
    else:
        parent_id = str(parent["_id"])
        await db.users.update_one({"_id": ObjectId(parent_id)}, {"$set": {"school_id": school_id}})

    # fee structure
    if not await db.fee_structures.find_one({"school_id": school_id}):
        grades = ["LKG", "UKG"] + [f"Class {i}" for i in range(1, 13)]
        await db.fee_structures.insert_one({
            "school_id": school_id,
            "fee_heads": [
                {"id": str(uuid.uuid4()), "name": "Tuition Fee", "amount": 120000, "frequency": "Yearly", "grades": grades, "account_id": None},
                {"id": str(uuid.uuid4()), "name": "Admission Fee", "amount": 25000, "frequency": "One-Time", "grades": grades, "account_id": None},
                {"id": str(uuid.uuid4()), "name": "Lab & Technology Fee", "amount": 12000, "frequency": "Yearly", "grades": grades, "account_id": None},
                {"id": str(uuid.uuid4()), "name": "Transport Fee", "amount": 24000, "frequency": "Quarterly", "grades": grades, "account_id": None},
                {"id": str(uuid.uuid4()), "name": "Examination Fee", "amount": 6000, "frequency": "Half-Yearly", "grades": grades, "account_id": None},
            ],
            "scholarships": [
                {"id": str(uuid.uuid4()), "name": "Merit Scholarship", "type": "percentage", "value": 15},
                {"id": str(uuid.uuid4()), "name": "Sibling Discount", "type": "fixed", "value": 10000},
            ],
            "early_bird_discount": 5, "late_fee": 500, "published": True,
        })

    # Idempotent: ensure add-on / "other" fee heads exist for a richer parent dashboard
    fs_doc = await db.fee_structures.find_one({"school_id": school_id})
    if fs_doc:
        grades_all = ["LKG", "UKG"] + [f"Class {i}" for i in range(1, 13)]
        existing_names = {h["name"] for h in fs_doc.get("fee_heads", [])}
        addon_heads = [
            {"name": "Meal Plan",           "amount": 18000, "frequency": "Quarterly", "grades": grades_all},
            {"name": "Uniform Kit",         "amount": 4500,  "frequency": "One-Time",  "grades": grades_all},
            {"name": "Sports & Activity Fee","amount": 9000, "frequency": "Yearly",    "grades": grades_all},
            {"name": "Annual Field Trip",   "amount": 3500,  "frequency": "One-Time",  "grades": grades_all},
            {"name": "Overnight Excursion", "amount": 6500,  "frequency": "One-Time",  "grades": grades_all},
            {"name": "Music & Arts Club",   "amount": 5400,  "frequency": "Half-Yearly","grades": grades_all},
        ]
        new_heads = [
            {"id": str(uuid.uuid4()), "account_id": None, **h}
            for h in addon_heads if h["name"] not in existing_names
        ]
        if new_heads:
            await db.fee_structures.update_one(
                {"school_id": school_id},
                {"$push": {"fee_heads": {"$each": new_heads}}}
            )

    # students
    if await db.students.count_documents({"school_id": school_id}) == 0:
        sample = [
            {"name": "Aarav Sharma", "grade": "Class 10", "roll_no": "H-1001", "parent_id": parent_id},
            {"name": "Diya Mehta", "grade": "Class 9", "roll_no": "H-1002", "parent_id": None},
            {"name": "Kabir Nair", "grade": "Class 11", "roll_no": "H-1003", "parent_id": None},
            {"name": "Ishita Rao", "grade": "Class 12", "roll_no": "H-1004", "parent_id": None},
            {"name": "Vivaan Gupta", "grade": "Class 10", "roll_no": "H-1005", "parent_id": None},
            {"name": "Ananya Singh", "grade": "Class 9", "roll_no": "H-1006", "parent_id": None},
        ]
        for s in sample:
            s.update({"school_id": school_id, "program": "",
                      "created_at": datetime.now(timezone.utc).isoformat()})
            await db.students.insert_one(s)

        # historical payments for analytics
        fs = await db.fee_structures.find_one({"school_id": school_id})
        heads = fs["fee_heads"]
        modes = ["UPI", "Cards", "Net Banking", "AutoPay", "Financing (EMI)"]
        now = datetime.now(timezone.utc)
        students_docs = []
        async for s in db.students.find({"school_id": school_id}):
            s["id"] = str(s["_id"])
            students_docs.append(s)
        for si, s in enumerate(students_docs):
            npays = random.randint(1, 3)
            for j in range(npays):
                head = random.choice(heads)
                created = now - timedelta(days=random.randint(0, 150))
                fin = head["frequency"] == "Yearly" and random.random() < 0.4
                await db.payments.insert_one({
                    "student_id": s["id"], "student_name": s["name"], "school_id": school_id,
                    "items": [{"fee_head_id": head["id"], "name": head["name"],
                               "amount": head["amount"], "frequency": head["frequency"], "paid": True}],
                    "amount": head["amount"], "gst": round(head["amount"] * 0.18, 2),
                    "mode": "Financing (EMI)" if fin else random.choice(modes[:-1]),
                    "status": "success", "financing": fin,
                    "receipt_no": "BLP-" + uuid.uuid4().hex[:6].upper(),
                    "academic_year": ACADEMIC_YEAR,
                    "created_at": created.isoformat(),
                })

    # Demo team members (idempotent) — so Team page isn't empty
    demo_team = [
        {"name": "Priya Menon", "email": "counsellor@biglyp.com", "role": "counsellor", "pw": "counsellor123"},
        {"name": "Arjun Kapoor", "email": "manager@biglyp.com", "role": "manager", "pw": "manager123"},
        {"name": "Neha Verma", "email": "admission@biglyp.com", "role": "admission", "pw": "admission123"},
    ]
    for t in demo_team:
        if not await db.users.find_one({"email": t["email"]}):
            await db.users.insert_one({
                "name": t["name"], "email": t["email"],
                "password_hash": hash_password(t["pw"]),
                "role": t["role"], "school_id": school_id, "campus": "Main Campus",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    # Fresh unpaid student linked to the parent (idempotent) — for testing payment options
    if not await db.students.find_one({"school_id": school_id, "name": "Sara Sharma"}):
        await db.students.insert_one({
            "name": "Sara Sharma", "grade": "Class 9", "roll_no": "H-2001",
            "program": "", "parent_id": parent_id, "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Two high-value (> ₹3 lakh) students linked to the parent (idempotent) — so the
    # document-upload financing flow (financing above ₹3 lakh) can be tested. A large
    # "International Curriculum Fee" pushes their financeable total well past ₹3 lakh.
    premium_students = [
        {"name": "Reyansh Kapoor", "grade": "Class 11", "roll_no": "H-2002"},
        {"name": "Saanvi Joshi", "grade": "Class 12", "roll_no": "H-2003"},
    ]
    for ps in premium_students:
        if not await db.students.find_one({"school_id": school_id, "name": ps["name"]}):
            await db.students.insert_one({
                "name": ps["name"], "grade": ps["grade"], "roll_no": ps["roll_no"],
                "program": "", "parent_id": parent_id, "school_id": school_id,
                "extra_fee_heads": [
                    {"id": str(uuid.uuid4()), "name": "International Curriculum Fee",
                     "amount": 250000, "frequency": "Yearly"},
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    logger.info("Seed complete")


@app.on_event("startup")
async def on_start():
    await seed()
    await ensure_credit_seed()

    # wire up extra-features router (rewards, reminders, receipts, cashflow)
    bundle = create_extras_router(db, {
        "get_current_user": get_current_user,
        "require_roles": require_roles,
        "resolve_student": _resolve_student,
        "compute_pending": compute_pending,
        "get_user_school_id": get_user_school_id,
        "STAFF_ROLES": STAFF_ROLES,
        "ACADEMIC_YEAR": ACADEMIC_YEAR,
    })
    EXTRAS.update(bundle)
    app.include_router(bundle["router"])
    await seed_extras(db)

    # psychometry report PDF endpoint
    from psychometry import create_psychometry_router
    psy = create_psychometry_router(db, {
        "get_current_user": get_current_user,
        "resolve_student": _resolve_student,
    })
    app.include_router(psy["router"])

    # OPS notifications management + EMI reminder job
    from notifications import create_notifications_router
    notif = create_notifications_router(db, {
        "get_current_user": get_current_user,
        "require_roles": require_roles,
    })
    app.include_router(notif["router"])
    await notif["ensure_seed"]()

    # daily auto-reminder job (respects each school's reminder_settings)
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(lambda: bundle["generate_reminders"](force=False),
                          "cron", hour=3, minute=0, id="daily_reminders", replace_existing=True)
        scheduler.start()
        EXTRAS["scheduler"] = scheduler
        logger.info("Reminder scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")


@app.on_event("shutdown")
async def on_stop():
    client.close()


app.include_router(api)
app.include_router(credit_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
