# BiglypEnroll — PRD

## Original Problem Statement
Build **BiglypEnroll**, a School SaaS (FEE) platform for both web and app, based on the
"School SaaS (FEE) Scoping" document. Clean, sharp, modern design for GenZ students and
their tech-savvy parents. White + shades of blue branding derived from the Biglyp logo.

## User Choices (v1 scope)
- Modules: School onboarding + academic/role setup, Fee Structure setup + Parent fee payment, Analytics dashboards
- Auth: JWT email/password with role-based access
- Payments: Mock / simulated (real Razorpay/Stripe deferred)
- AI: Only fee-structure Excel parsing (Emergent LLM key, openai gpt-5.4)
- Audience: both school staff and parents/students, equally

## Architecture
- **Backend**: FastAPI + MongoDB (motor). JWT (PyJWT) bearer-token auth, bcrypt hashing, role guards.
  `fee_parser.py` uses emergentintegrations (gpt-5.4) to normalise uploaded Excel/CSV fee sheets.
- **Frontend**: React 19 + React Router 7, Tailwind + shadcn/ui, Recharts, framer-motion, sonner.
  Fonts: Outfit (headings) / Figtree (body). Colors: navy #1E2A78, electric blue #2540E8, white.
- Token stored in localStorage (`biglyp_token`), sent via Authorization header.

## Personas / Roles
super_admin (Biglyp Ops), school_admin, finance, counsellor, parent.

## Implemented (2026-06-08)
- Marketing landing page (hero, features, audience, how-it-works, footer)
- Auth: register/login/me/logout, RBAC route guards, 4 seeded demo accounts
- School onboarding wizard: profile → campuses → courses → settlement accounts → go live
- Fee Structure manager: fee heads (amount/frequency/grades), scholarships, early-bird & late-fee rules, draft/publish, **AI Excel/CSV upload parsing**
- Students list + add (with parent email linking)
- Parent app: pending fees, itemized summary w/ GST, mock payment (multiple modes) + receipt, 0% EMI financing with schedule preview, payment history
- Analytics dashboard: KPIs (collected, financed, outstanding, overdue, students, txns), collection velocity line, payment-mode pie, aging bars, admission funnel
- Seed data: Horizon International School, published fee structure, 6 students, historical payments

## Test status
Backend 21/21 pytest pass. Frontend flows verified via testing agent. Tests at
`/app/backend/tests/backend_test.py`.

## Backlog / Remaining (P1/P2 from scoping doc)

## Credit Assessment & Loan Origination module (2026-06-08)
GrayQuest-inspired school fee-financing credit platform at `/credit` (staff + credit_ops) and lender portal (auto-routes lenders). Built on React+FastAPI+MongoDB; external bureaus/KYC/AA are realistically SIMULATED (deterministic from PAN); AI (Emergent LLM/Gemini) powers bank-statement + document OCR with graceful fallback.
- Loan application wizard (student/school, parent applicant, co-applicant, loan+subvention, consent)
- Digital KYC (PAN/Aadhaar/CKYC/DigiLocker/liveness/e-sign) — simulated verify
- Credit bureau pull (TransUnion CIBIL + CRIF/Experian/Equifax) with full report (score, DPD, enquiries, written-off, utilization, credit mix, repayment history, trade lines)
- Bank statement analyzer (AI PDF/CSV + manual), Income Assessment engine, FOIR calculator
- Biglyp Internal Credit Score 0–1000 with admin-configurable weightages
- Rule-based Credit Policy engine per lender (admin-editable, no code), Eligibility Decision (Approved/Conditional/Refer/Reject + reasons), Best-Lender recommendation (approval probability)
- Fee-financing subvention models (100% school / 100% parent / shared) + Loan Pricing engine (EMI, IIR, processing fee, spread, school payout, parent contribution, lender yield, Biglyp revenue)
- Document management + OCR, Fraud & Risk engine (duplicate PAN/mobile, velocity, tampering, statement anomalies)
- Maker-checker workflow, deficiency tracking, lender submission + lender status
- Dashboards (admin/school/lender), audit trail, consent gating, PII masking, RBAC
- 4 preconfigured lenders (Axis/HDFC/ICICI/Aditya Birla NBFC). Backend router: credit.py. Tests: /app/backend/tests/test_credit.py (19/19 pass).
- New logins: creditops@biglyp.com/creditops123 (checker), lender@biglyp.com/lender123 (HDFC portal).

### Earlier P1/P2 backlog
- P1: Admission CRM (lead → enrollment, AI lead scoring, counsellor assignment, offer letters)
- P1: Real payment gateway (Razorpay), settlement auto-reconciliation, collection & recovery queue
- P2: Communication engine (Email/SMS/WhatsApp templates), Student Info System, multi-campus selector, financial-year switcher, Biglyp Ops Hub, financing partner API
- Low: split server.py into routers, cache fee structure in analytics loop, brute-force lockout on login

## Update (2025-07) — Configurable parent payment options (Option A/B/C)
- School Setup gained a **Fee Collection** step: toggle 3 parent payment options (A=0% EMI, B=Auto-Debit quarterly/half-yearly, C=Pay full upfront). At least one must stay enabled (enforced client + server via normalize_payment_options). Stored as `payment_options {emi, auto_debit, full}` on the school doc; exposed via GET /api/parent/fees.
- Parent Fee Payment screen: top quick-pick replaced by prominent **Option A/B/C** cards (wizard-style, with highlight badges). Only school-enabled options render. "Choose how to pay" (Quarterly/Half-Yearly) now shows only when Option B is selected.
- Financing wizard Step 1: removed the EMI-vs-lumpsum (Option A/B) chooser; it's now a clean 0% EMI setup.

## Update (2026-06) — Homepage product-section mockups + prominent hero
- Homepage (/) redesigned in **indigo/violet + yellow** palette (aligned to user reference mockups), harmonized across nav, buttons, tabs, testimonials, FAQ, footer.
- 3 product sections now use **custom-built UI mockups** (not stock photos), inspired by user references:
  - BiglypEnroll: dual-engine dashboard (Career Hub psychometric card + Fee Collection live dashboard with bar chart).
  - Biglyp Career Hub: psychometrics radar/profile card (SVG pentagon) + course-discovery result card.
  - Biglyp Fee Collection: Parents/Institutions benefit cards + payment-option cards (Auto-Collect/Instant/0% EMI).
- Hero made more prominent: larger headline (up to 68px) with violet italic accent + yellow underline, subhead, description, dual CTAs, and a trust row (avatars + rating + "6,500+ institutions").
- Hero entrance switched from framer-motion to CSS `float-up` reveal classes (reveal-1..5) in globals.css for paint-based, hydration-independent reliability.
- File: /app/frontend/src/components/home/Homepage.tsx. Verified visually (hero + all 3 sections render correctly).

## Update (2026-06b) — Homepage interactions + polish
- Interactive Radar: Career Hub psychometrics radar (SVG) now scale-animates in on scroll (framer motion.g, whileInView, transformBox view-box).
- Live counters: hero Stats (42+/1,200+/2,50,000+) count up from zero via IntersectionObserver + rAF (CountUp component, en-IN formatting).
- Mockup hover: `.mockup-hover` class (globals.css) adds lift + indigo glow to all 3 product mockups.
- Section CTAs already wired via <Link href> to /biglypenroll, /career-hub, /fee-collection (routes exist).
- Hero background darkened to a deeper lavender wash; Career Hub mockup made sleeker (gradient pill, live-scan dot, readiness=72 stat, larger radar, softer ring shadows); Fee Collection mockup fonts enlarged/bolder.
- Added footnote "* 0% EMI subject to partnership." under the Fee Collection CTA (ProductSection `note` prop) + `*` on the "0% EMIs*" bullet.

## Update (2026-06c) — Homepage engagement features (tested 100%)
- Counter Everywhere: CountUp extended (prefix/suffix/decimals); added animated mini-stat rows to all 3 ProductSections (Enroll: 6,500+/50L+/₹4,200Cr+; Career: 2,50,000+/42/60+; Fee: 8+/0%/100%).
- Radar Compare: Career Hub radar has an Ananya/Rahul toggle (data-testid radar-profile-0/1) that morphs the polygon + updates name, class, readiness, recommendation & fit.
- Demo Booking: sticky bottom "Book a demo" bar (data-testid demo-bar / demo-bar-cta / demo-bar-close) appears after scrollY>700, dismissible, scrolls to DarkCta (id='book-demo').
- Mobile Pass: tightened hero spacing (pt-12/pb-14 on mobile, text-4xl headline), reduced product-section padding/gap, responsive mockup card padding.
- Section CTAs confirmed wired to /biglypenroll, /career-hub, /fee-collection (all 200).
- Verified by testing agent (iteration_4.json): frontend 100%, no blocking issues.
- PENDING user decision: hero tagline choice (options a–e presented); not yet applied to copy.

## Parent Portal UI Revamp (2026-08-16)
Frontend-only modernisation of the post-login parent portal (white + blue palette retained):
- New design utilities in globals.css (soft layered shadows, card-lift, hero-gradient, glass bars, gradient nav pill)
- ParentLayout: sectioned sidebar (Explore/Payments/Account) with gradient active pill + "Soon" chips, user mini-card w/ logout, glass sticky topbar with personalised greeting, refined notifications, gradient-underline sub-tabs
- ParentDashboard: gradient hero band (child, grade/AY, wallet chip, total pending, due date, child selector), sharpened Option A/B/C cards (selected check, hover lift, stagger reveal), polished dues card, gradient CTAs, elevated Other Fees cards
- All logic, API calls and data-testids preserved (parent-logout now in sidebar card; parent-logout-mobile added for mobile topbar)

## Psychometry Mock — Assessment Flow + Reports (2026-08-16)
Per user-attached PDFs (Psychometry flow + ExploreX detailed report):
- Assessment types by grade: DiscoverU (6-8), ExploreX (9-10), DecidePro (11-12). Landing page /app/psychometry is now grade-aware (demo child Aarav = Class 10 -> ExploreX). DiscoverU/DecidePro report content pending from user; structure is data-driven and ready.
- /app/psychometry/attempt: focus-mode 80-question likert flow (4 categories x 20), Question X of 80, Previous/Next/Finish, category progress rail, "Demo: auto-fill" helper, animated report-waiting screen (rotating clock, 3 stages, 12s countdown). Answers scored per category -> localStorage (biglyp_psycho_results).
- /app/psychometry/reports: Congratulations banner (?completed=1), personalized summary report (Profile Snapshot, Professional Identity "Empathetic Global Business Strategist", Category Scores w/ marker bars, 12-param Radar chart via recharts, 3 Career Clusters, 4 Academic & Skill tiles, Parent Guidance), Download Report, emoji feedback widget (mock toast), past assessment list w/ Download/Email (email MOCKED via toast).
- Backend: backend/psychometry.py — GET /api/parent/psychometry/report/{student_id} generates the detailed multi-section report PDF (reportlab; cover, congratulations, TOC, framework, identity, scores w/ bars, stream-fit, clusters, skills, parent guidance, disclaimer) personalised with student name/grade (replaces "Mahesh Mehta"). Tested 7/7 via backend testing agent.

## Update (2025-07) — Full CSB Bank Loan Agreement in Financing Wizard
- Replaced the one-paragraph placeholder in the parent Financing Wizard's "View Loan Agreement" view (DocOverlay, shared across Step 4, Step 5 & Done screen) with a full, professionally formatted **School Fee Financing Loan Agreement** modelled on the user's Sample Agreement PDF.
- Lender named **CSB Bank Limited**. Structure: header (date + loan/app no.), recital, 1. Loan Details table, and clauses 2–10 (Purpose & Disbursement, Repayment, Applicant Declarations (7-item list), Fees & Charges, Default, Privacy & Data Consent, Grievance Redressal, Governing Terms, Electronic Acceptance) + signature block + acknowledgement.
- Handling charge fixed at **₹850 + GST** (shows ₹1,003 incl. 18% GST). All values (applicant, student, amounts, tenure, EMI, financed) are dynamically populated from wizard state.
- New component `AgreementDoc` in `src/screens/parent/FinancingWizard.tsx`. KFS view lender label also updated to CSB Bank Limited. Verified via isolated render screenshot; lint clean; frontend production build.

## Update (2025-07) — School Fee Financing Gap List, PHASE 1: Financing Banks CRUD (OPS)
- New OPS-driven **Financing Banks** configuration (drives the parent 0% EMI flow; nothing hardcoded).
- Backend (`backend/credit.py`), collection `financing_banks`, router prefix `/api/credit`:
  - GET `/financing-banks` (admin), POST `/financing-banks` (admin), GET `/financing-banks/{bid}` (any authed — full-config lookup for later phases), PUT `/financing-banks/{bid}` (admin), DELETE `/financing-banks/{bid}` (admin). ADMIN_ROLES = super_admin, credit_ops.
  - Fields: name, active, advance_emi, min_loan_amount (default 25000), location_match_aadhaar, name_match_rule (profile|pan|aadhaar), income_proof{cibil_threshold, income_threshold, required_matrix{high_cibil_high_income, high_cibil_low_income, low_cibil_high_income, low_cibil_low_income}}, fund_release{multi_account_allowed, vendor_external_allowed}.
  - One default bank seeded: "CSB Bank Limited". Backend tested 24/24 pass.
- Frontend: new `/credit/banks` screen (`src/screens/credit/FinancingBanks.tsx`, route `src/app/credit/banks/page.tsx`), nav item "Financing Banks" added to CreditLayout (admin-only). List view + Add/Edit dialog, all fields editable post-creation, delete supported. No approval workflow. Verified via screenshots.
- Phase 1 done. Later phases (Screen 1 amount/advance-EMI, Screen 2 income-proof + NACH, Screen 3 KYC priority/name-match/decline states) will consume GET-by-ID config.
