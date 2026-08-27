'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useMemo, useRef, useState } from "react";
import api, { inr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  ShieldCheck, Check, ArrowRight, ArrowLeft, Fingerprint, ScanFace,
  Camera, Landmark, Smartphone, CreditCard, Lock, BadgeCheck, Zap,
  CheckCircle2, Loader2, Calendar, FileSignature, ShieldQuestion,
  Gauge, XCircle, RefreshCw, BookOpen, Sparkle, FileText, Upload,
  PartyPopper, Download, ScrollText, User, Briefcase, GraduationCap,
} from "lucide-react";

const STEPS = [
  { n: 1, label: "Plan" },
  { n: 2, label: "Eligibility" },
  { n: 3, label: "Digital KYC" },
  { n: 4, label: "Review" },
  { n: 5, label: "Sign & Pay" },
];
const SUBTITLES = {
  1: "Choose Your 0% EMI Plan",
  2: "Instant Eligibility Pre-Check",
  3: "Digital Identity Verification (KYC)",
  4: "Application Review & Final Decision",
  5: "Review, Sign & Pay",
  6: "All Done",
};
const TENURE_OPTIONS = [3, 6, 9, 12];
const DOC_THRESHOLD = 300000;
const RAILS = [
  { key: "UPI AutoPay", title: "UPI AutoPay (Google Pay, PhonePe, Paytm)", icon: Smartphone, badge: "Recommended" },
  { key: "Net Banking eNACH", title: "Net Banking eNACH", icon: Landmark },
  { key: "Debit Card Mandate", title: "Debit Card Mandate", icon: CreditCard },
];
const PAN_RE = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

// A profile-sourced address (auto-fetched, shown read-only in KYC)
const PROFILE_ADDRESS = {
  line1: "Flat 402, Royal Palms",
  locality: "Vasant Kunj",
  city: "New Delhi",
  state: "Delhi",
  pincode: "110070",
  residenceType: "Self Owned",
};

export function FinancingWizard({ open, onOpenChange, studentId, studentName, studentGrade, feeHeadIds, academicTotal, onSuccess }) {
  const { user } = useAuth();
  const [step, setStep] = useState(1);

  // Step 1 — plan
  const [down, setDown] = useState(0);
  const [tenure, setTenure] = useState(12);
  const [preview, setPreview] = useState(null);

  // Step 2 — eligibility + CIBIL check (now also collects name + DOB)
  const [eligConsent, setEligConsent] = useState(false);
  const [cibilPan, setCibilPan] = useState("");
  const [cibilChecking, setCibilChecking] = useState(false);
  const [cibilResult, setCibilResult] = useState(null);
  const [scoreAnim, setScoreAnim] = useState(0);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [dob, setDob] = useState("");

  // Step 3 — KYC
  const [gender, setGender] = useState("");
  const [maritalStatus, setMaritalStatus] = useState("");
  const [email, setEmail] = useState("");
  const [fatherName, setFatherName] = useState("");
  const [pan, setPan] = useState("");
  const [relationship, setRelationship] = useState("");
  const [employment, setEmployment] = useState("Salaried");
  // Aadhaar + liveness
  const [aadhaarConsent, setAadhaarConsent] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [aadhaarVerified, setAadhaarVerified] = useState(false);
  const [liveness, setLiveness] = useState("idle"); // idle | checking | done
  const [camOn, setCamOn] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  // Income documents (only when financed > 3L) — simulated uploads
  const [docs, setDocs] = useState({}); // { key: filename }

  // Step 4 — review & offer
  const [reviewChecks, setReviewChecks] = useState({ identity: "done", documents: "done", credit: "pending", decision: "pending" });
  const [offerReady, setOfferReady] = useState(false);

  // Step 5 — sign + autopay + down-payment (progressive)
  const [esignSent, setEsignSent] = useState(false);
  const [esignOtp, setEsignOtp] = useState("");
  const [agree, setAgree] = useState(false);
  const [agreementSigned, setAgreementSigned] = useState(false);
  const [rail, setRail] = useState("UPI AutoPay");
  const [upiId, setUpiId] = useState("");
  const [netBank, setNetBank] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvv, setCardCvv] = useState("");
  const [autopaySet, setAutopaySet] = useState(false);
  const [autopayWorking, setAutopayWorking] = useState(false);
  const [upfrontPaid, setUpfrontPaid] = useState(false);
  const [payingUpfront, setPayingUpfront] = useState(false);

  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null); // activation response for step 6

  // Overlay document viewer (KFS / Agreement / Schedule)
  const [docView, setDocView] = useState(null); // null | 'kfs' | 'agreement' | 'schedule'

  const financed = preview?.financed_amount ?? Math.max(0, academicTotal - down);
  const needDocs = academicTotal > DOC_THRESHOLD;

  // reset on open
  useEffect(() => {
    if (!open) return;
    setStep(1); setDown(0); setTenure(12); setPreview(null);
    setEligConsent(false); setCibilPan(""); setCibilChecking(false); setCibilResult(null); setScoreAnim(0);
    setGender(""); setMaritalStatus(""); setFatherName(""); setPan(""); setRelationship(""); setEmployment("Salaried");
    setAadhaarConsent(false); setOtpSent(false); setOtp(""); setAadhaarVerified(false); setLiveness("idle");
    setDocs({});
    setReviewChecks({ identity: "done", documents: "done", credit: "pending", decision: "pending" });
    setOfferReady(false);
    setEsignSent(false); setEsignOtp(""); setAgree(false); setAgreementSigned(false);
    setRail("UPI AutoPay"); setUpiId(""); setNetBank(""); setCardNumber(""); setCardExpiry(""); setCardCvv("");
    setAutopaySet(false); setAutopayWorking(false);
    setUpfrontPaid(false); setPayingUpfront(false);
    setProcessing(false); setResult(null); setDocView(null);
    // prefill applicant name + email from the logged-in parent's profile
    const parts = (user?.name || "").trim().split(/\s+/);
    setFirstName(parts[0] || "");
    setLastName(parts.slice(1).join(" ") || "");
    setEmail(user?.email || "");
    setDob("");
  }, [open, user]);

  // plan preview
  useEffect(() => {
    if (!open || !academicTotal) return;
    api.post("/parent/financing/preview", { amount: academicTotal, down_payment: down, tenure })
      .then(({ data }) => setPreview(data)).catch(() => {});
  }, [open, down, tenure, academicTotal]);

  // camera lifecycle
  const stopCam = () => {
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    setCamOn(false);
  };
  useEffect(() => () => stopCam(), []);
  useEffect(() => { if (step !== 3) stopCam(); }, [step]);

  const startCam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCamOn(true);
    } catch {
      toast.info("Camera unavailable — using simulated liveness check.");
      setCamOn(false);
    }
  };
  const captureLiveness = () => {
    setLiveness("checking");
    setTimeout(() => { setLiveness("done"); stopCam(); }, 1600);
  };
  const sendOtp = () => {
    if (!aadhaarConsent) { toast.error("Please provide Aadhaar verification consent first"); return; }
    setOtpSent(true); toast.success("OTP sent to Aadhaar-linked mobile (simulated)");
  };
  const verifyOtp = () => {
    if (otp.trim().length < 4) { toast.error("Enter the 6-digit code"); return; }
    setAadhaarVerified(true); toast.success("Aadhaar identity verified");
  };
  const sendEsign = () => { setEsignSent(true); toast.success("e-Sign OTP sent (simulated)"); };
  const verifySign = () => {
    if (!agree) { toast.error("Please accept the Terms & Conditions"); return; }
    if (esignOtp.trim().length < 4) { toast.error("Enter the e-Sign OTP"); return; }
    setAgreementSigned(true); toast.success("Agreement signed successfully");
  };
  const changeRail = (v) => { setRail(v); setAutopaySet(false); setUpiId(""); setNetBank(""); setCardNumber(""); setCardExpiry(""); setCardCvv(""); };
  const UPI_RE = /^[a-z0-9.\-_]{2,}@[a-z]{2,}$/i;
  const railReady = rail === "UPI AutoPay" ? UPI_RE.test(upiId)
    : rail === "Net Banking eNACH" ? !!netBank
    : cardNumber.replace(/\s/g, "").length >= 12 && /^\d{2}\/\d{2}$/.test(cardExpiry) && cardCvv.length >= 3;
  const setupAutopay = () => {
    if (!railReady) { toast.error("Please complete the mandate details"); return; }
    setAutopayWorking(true);
    setTimeout(() => { setAutopayWorking(false); setAutopaySet(true); toast.success("AutoPay mandate set up"); }, 1200);
  };

  // CIBIL check (Step 2)
  const runCibilCheck = async () => {
    if (!PAN_RE.test(cibilPan)) { toast.error("Enter a valid PAN (e.g. ABCDE1234F)"); return; }
    if (!eligConsent) { toast.error("Please provide consent for the soft credit check"); return; }
    setCibilChecking(true); setCibilResult(null); setScoreAnim(0);
    try {
      const [{ data }] = await Promise.all([
        api.post("/parent/cibil-check", { pan: cibilPan.toUpperCase(), consent: true }),
        new Promise((r) => setTimeout(r, 1400)),
      ]);
      setCibilResult(data);
      setPan(cibilPan.toUpperCase());
      toast.success(data.approved ? "Pre-approved for 0% EMI" : "Eligibility check completed");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not run the eligibility check");
    } finally {
      setCibilChecking(false);
    }
  };

  // animate the CIBIL score meter
  useEffect(() => {
    if (!cibilResult) { setScoreAnim(0); return; }
    const target = cibilResult.score;
    let start = 0;
    const inc = Math.max(4, Math.round(target / 40));
    const id = setInterval(() => {
      start = Math.min(target, start + inc);
      setScoreAnim(start);
      if (start >= target) clearInterval(id);
    }, 20);
    return () => clearInterval(id);
  }, [cibilResult]);

  // Step 4 — run the "underwriting" animation whenever we land on it
  useEffect(() => {
    if (step !== 4) return;
    setOfferReady(false);
    setReviewChecks({ identity: "done", documents: "done", credit: "running", decision: "pending" });
    const t1 = setTimeout(() => setReviewChecks((c) => ({ ...c, credit: "done", decision: "running" })), 1700);
    const t2 = setTimeout(() => { setReviewChecks((c) => ({ ...c, decision: "done" })); setOfferReady(true); }, 3400);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [step]);

  // documents completeness (only relevant when needDocs)
  const docsRequired = employment === "Salaried"
    ? [{ key: "salary_slips", label: "3 months salary slips" }, { key: "bank_statement", label: "3 months bank statement" }]
    : [{ key: "itr", label: "2 years ITR" }, { key: "bank_statement", label: "6 months bank statement" }];
  const docsComplete = !needDocs || docsRequired.every((d) => docs[d.key]);

  const amountNow = preview?.amount_payable_now ?? (down + (preview?.processing_fee || 0));

  // per-step validity
  const canContinue = useMemo(() => {
    if (step === 1) return !!preview;
    if (step === 2) return eligConsent && cibilResult && cibilResult.approved &&
      firstName.trim() && lastName.trim() && dob && PAN_RE.test(cibilPan);
    if (step === 3) return (
      firstName.trim() && lastName.trim() && fatherName.trim() && gender && maritalStatus &&
      email.trim() && /^\S+@\S+\.\S+$/.test(email) && PAN_RE.test(pan) && dob &&
      relationship && employment &&
      aadhaarVerified && liveness === "done" && docsComplete
    );
    if (step === 4) return offerReady;
    if (step === 5) return agreementSigned && autopaySet && upfrontPaid;
    return false;
  }, [step, preview, eligConsent, cibilResult, cibilPan, firstName, lastName, dob, fatherName, gender, maritalStatus,
      email, pan, relationship, employment, aadhaarVerified, liveness, docsComplete, offerReady,
      agreementSigned, autopaySet, upfrontPaid]);

  const next = () => {
    if (!canContinue) { toast.error("Please complete this step to continue."); return; }
    if (step < 5) setStep((s) => s + 1);
    else activate();
  };
  const back = () => setStep((s) => Math.max(1, s - 1));

  const payUpfront = () => {
    setPayingUpfront(true);
    setTimeout(() => { setPayingUpfront(false); setUpfrontPaid(true); toast.success("Payment successful"); }, 1300);
  };

  const activate = async () => {
    setProcessing(true);
    try {
      const { data } = await api.post("/parent/pay-financing", {
        student_id: studentId, fee_head_ids: feeHeadIds, tenure, down_payment: down,
      });
      setResult(data);
      setStep(6);
      onSuccess?.(data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not activate financing");
    } finally {
      setProcessing(false);
    }
  };

  const uploadDoc = (key, file) => {
    if (!file) return;
    setDocs((d) => ({ ...d, [key]: file.name }));
    toast.success(`Uploaded ${file.name}`);
  };

  const empProfessional = employment === "Self-Employed Professional";
  const nextEmi = (result?.schedule || []).find((s) => s.status !== "paid");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl max-w-2xl p-0 overflow-hidden gap-0">
        {/* Header */}
        <DialogHeader className="px-6 md:px-8 pt-6 pb-5 border-b border-border">
          <DialogTitle className="font-head text-lg text-brand-navy flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-[#5548D1]" /> 0% Interest Fee Financing Application
          </DialogTitle>
          {/* step progress bar */}
          <Box className="mt-5 flex items-center" data-testid="wizard-stepper">
            {STEPS.map((s, i) => {
              const done = s.n < step;
              const active = s.n === step;
              return (
                <Box key={s.n} className="flex items-center flex-1 last:flex-none">
                  <Box className="flex items-center gap-2">
                    <Box component="span" className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                      done ? "bg-[#5548D1] text-white" : active ? "bg-[#5548D1] text-white ring-4 ring-[#EEF0FF]" : "bg-slate-100 text-slate-400"
                    }`}>
                      {done ? <Check className="h-4 w-4" /> : s.n}
                    </Box>
                    <Box component="span" className={`text-xs font-semibold hidden sm:inline ${active ? "text-[#5548D1]" : done ? "text-brand-navy" : "text-slate-400"}`}>{s.label}</Box>
                  </Box>
                  {i < STEPS.length - 1 && (
                    <Box className={`h-0.5 flex-1 mx-2 rounded-full ${done ? "bg-[#5548D1]" : "bg-slate-100"}`} />
                  )}
                </Box>
              );
            })}
          </Box>
          <Typography variant="inherit" component="p" className="mt-4 text-sm text-brand-navy font-semibold" data-testid="wizard-subtitle">
            {step <= 5 ? `Step ${step}: ` : ""}{SUBTITLES[step]}
          </Typography>
        </DialogHeader>

        {/* Body */}
        <Box className="px-6 md:px-8 py-5 max-h-[62vh] overflow-y-auto relative">
          {/* Document overlay (KFS / Agreement / Schedule) */}
          {docView && (
            <DocOverlay
              kind={docView}
              onClose={() => setDocView(null)}
              preview={preview}
              result={result}
              applicant={`${firstName} ${lastName}`.trim()}
              studentName={studentName}
              tenure={tenure}
              down={down}
              academicTotal={academicTotal}
            />
          )}

          {/* ---------- Step 1: Plan ---------- */}
          {step === 1 && (
            <Box className="space-y-4" data-testid="step-plan">
              <Typography variant="inherit" component="p" className="text-sm text-slate-500">Set up your 0% EMI plan for <b className="text-brand-navy">{inr(academicTotal)}</b>. Your school is paid 100% upfront.</Typography>

              <Box className="rounded-xl border border-[#5548D1]/20 bg-[#EEF0FF] p-4" data-testid="plan-emi-banner">
                <Box className="flex items-start justify-between gap-2">
                  <Box>
                    <Typography variant="inherit" component="p" className="text-[10px] uppercase tracking-widest font-bold text-[#5548D1]">Pay full-year fees in EMIs</Typography>
                    <Typography variant="inherit" component="p" className="text-[11.5px] text-slate-500 mt-1">Small, convenient monthly payments</Typography>
                  </Box>
                  <Box component="span" className="rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 uppercase tracking-widest">0% Interest</Box>
                </Box>
                {preview && (
                  <Typography variant="inherit" component="p" className="mt-3 font-head text-2xl font-black text-brand-navy">
                    {inr(preview.emi)}
                    <Box component="span" className="text-[11px] font-semibold text-slate-500 ml-1">/ month</Box>
                  </Typography>
                )}
              </Box>

              <Box>
                <Label className="text-sm text-brand-navy">Down payment (optional)</Label>
                <Input type="number" value={down} data-testid="wiz-down"
                  onChange={(e) => setDown(Math.max(0, Math.min(academicTotal, Number(e.target.value))))}
                  className="rounded-lg mt-1.5" />
              </Box>

              {/* Tenure — 4 discrete options instead of a slider */}
              <Box>
                <Label className="text-sm text-brand-navy">Select Tenure</Label>
                <Box className="mt-1.5 grid grid-cols-4 gap-1.5" data-testid="wiz-tenure-options">
                  {TENURE_OPTIONS.map((t) => {
                    const active = tenure === t;
                    return (
                      <Box component="button" type="button" key={t} onClick={() => setTenure(t)}
                        data-testid={`wiz-tenure-${t}`}
                        className={`rounded-lg border py-1.5 text-center transition-colors ${
                          active ? "border-[#5548D1] bg-[#EEF0FF] ring-1 ring-[#5548D1]" : "border-border bg-white hover:border-[#5548D1]/40"
                        }`}>
                        <Box component="span" className={`font-head text-base font-black ${active ? "text-[#5548D1]" : "text-brand-navy"}`}>{t}</Box>
                        <Box component="span" className="text-[10px] text-slate-400 ml-1">mo</Box>
                      </Box>
                    );
                  })}
                </Box>
              </Box>

              {preview && (
                <Box className="bg-[#EEF0FF] rounded-xl p-3 space-y-1 text-[13px]" data-testid="plan-summary">
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Financed amount</Box><Box component="span" className="font-semibold">{inr(preview.financed_amount)}</Box></Box>
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Monthly EMI</Box><Box component="span" className="font-head font-bold text-[#5548D1] text-base">{inr(preview.emi)}</Box></Box>
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Interest</Box><Box component="span" className="font-semibold text-green-600">0%</Box></Box>
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Processing fee (incl. GST)</Box><Box component="span" className="font-semibold">{inr(preview.processing_fee)}</Box></Box>
                </Box>
              )}
            </Box>
          )}

          {/* ---------- Step 2: Eligibility ---------- */}
          {step === 2 && (
            <Box className="space-y-4" data-testid="step-eligibility">
              <Box className="rounded-xl bg-[#EEF0FF] border border-[#5548D1]/15 p-4 flex items-start gap-3">
                <Box className="h-9 w-9 rounded-lg bg-[#5548D1] text-white flex items-center justify-center shrink-0"><Zap className="h-4 w-4" /></Box>
                <Box>
                  <Typography variant="inherit" component="p" className="font-semibold text-brand-navy text-sm">Instant CIBIL Eligibility Pre-Check</Typography>
                  <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-0.5">Soft credit pull via CIBIL (TransUnion) — no impact on your credit score.</Typography>
                </Box>
              </Box>

              {/* Applicant identity for the bureau pull */}
              <Box className="rounded-xl border border-border p-4">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2">
                  <Fingerprint className="h-4 w-4 text-[#5548D1]" /> Verify your CIBIL Score
                </Typography>
                <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-1">
                  Confirm your details and PAN. We fetch your CIBIL score securely from the bureau.
                </Typography>

                <Box className="mt-4 grid sm:grid-cols-2 gap-4">
                  <Box>
                    <Label className="text-sm text-brand-navy flex items-center gap-1.5">First Name {firstName && <Box component="span" className="text-[10px] text-emerald-700 font-bold">Auto-fetched</Box>}</Label>
                    <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="rounded-lg mt-1.5" data-testid="elig-first-name" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy flex items-center gap-1.5">Last Name {lastName && <Box component="span" className="text-[10px] text-emerald-700 font-bold">Auto-fetched</Box>}</Label>
                    <Input value={lastName} onChange={(e) => setLastName(e.target.value)} className="rounded-lg mt-1.5" data-testid="elig-last-name" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Date of Birth</Label>
                    <DobPicker value={dob} onChange={setDob} data-testid="elig-dob" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">PAN Card Number</Label>
                    <Input
                      value={cibilPan}
                      onChange={(e) => { setCibilPan(e.target.value.toUpperCase().slice(0, 10)); setCibilResult(null); }}
                      placeholder="ABCDE1234F"
                      className="rounded-lg mt-1.5 uppercase tracking-wider"
                      data-testid="cibil-pan"
                      disabled={cibilChecking}
                    />
                    {cibilPan && !PAN_RE.test(cibilPan) && (
                      <Typography variant="inherit" component="p" className="text-[11px] text-red-500 mt-1">Format: ABCDE1234F</Typography>
                    )}
                  </Box>
                </Box>

                {/* Consent must be checked before the CIBIL button is enabled */}
                <Box component="label" className="flex items-start gap-3 cursor-pointer mt-4" data-testid="elig-consent-label">
                  <Checkbox checked={eligConsent} onCheckedChange={(v) => setEligConsent(!!v)} className="mt-0.5" data-testid="elig-consent" disabled={cibilChecking} />
                  <Box component="span" className="text-sm text-slate-600 leading-relaxed">
                    I authorize Biglyp &amp; its NBFC lending partner to fetch my CIBIL score via a <b>soft pull</b> for eligibility.
                    This will <b>not</b> impact my credit score.
                  </Box>
                </Box>

                <Button
                  onClick={runCibilCheck}
                  disabled={!PAN_RE.test(cibilPan) || !eligConsent || cibilChecking}
                  data-testid="cibil-check-btn"
                  className="mt-4 h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold px-4 w-full sm:w-auto"
                >
                  {cibilChecking ? (<><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Checking...</>)
                    : cibilResult ? (<><RefreshCw className="h-4 w-4 mr-1.5" /> Re-check</>)
                    : (<><Gauge className="h-4 w-4 mr-1.5" /> Check CIBIL Score</>)}
                </Button>
                {!eligConsent && (
                  <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 mt-2">Tick the consent box above to enable the CIBIL check.</Typography>
                )}
              </Box>

              {cibilChecking && !cibilResult && (
                <TriviaLoader title="Fetching your CIBIL score…" subtitle="Securely connecting to CIBIL (TransUnion) via RBI-regulated NBFC rails." data-testid="cibil-checking" />
              )}

              {/* Simplified result — score + approved message + max eligible ONLY */}
              {cibilResult && (
                <Box className={`rounded-xl border p-5 ${cibilResult.approved ? "border-emerald-200 bg-emerald-50/40" : "border-red-200 bg-red-50/40"}`} data-testid="cibil-result">
                  <Box className="flex flex-col sm:flex-row gap-5 items-center">
                    <CibilGauge score={scoreAnim} target={cibilResult.score} band={cibilResult.band} color={cibilResult.band_color} />
                    <Box className="flex-1 min-w-0 text-center sm:text-left">
                      <Box className="flex items-center gap-2 justify-center sm:justify-start">
                        {cibilResult.approved ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <XCircle className="h-5 w-5 text-red-500" />}
                        <Typography variant="inherit" component="p" className={`font-head font-bold text-base ${cibilResult.approved ? "text-emerald-700" : "text-red-600"}`}>
                          {cibilResult.approved ? "Pre-approved for 0% EMI" : "Not eligible right now"}
                        </Typography>
                      </Box>
                      {cibilResult.approved && (
                        <Typography variant="inherit" component="p" className="text-sm text-emerald-800 mt-1" data-testid="cibil-congrats">
                          Congratulations! You are pre-approved for 0% EMI financing{cibilResult.max_eligible > 0 ? <> up to <b>{inr(cibilResult.max_eligible)}</b></> : ""}.
                        </Typography>
                      )}
                    </Box>
                  </Box>
                </Box>
              )}

              <Box component="ul" className="space-y-2 pt-1">
                {["Zero interest, zero hidden charges", "Powered by RBI-regulated NBFC lending partners", "Instant digital approval — no paperwork"].map((t) => (
                  <Box component="li" key={t} className="flex items-center gap-2.5 text-xs text-slate-600">
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" /> {t}
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          {/* ---------- Step 3: Digital KYC ---------- */}
          {step === 3 && (
            <Box className="space-y-4" data-testid="step-kyc">
              {/* Student details — autofilled, name + class only */}
              <Box className="rounded-xl border border-border p-4 bg-slate-50/60" data-testid="kyc-student">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><GraduationCap className="h-4 w-4 text-[#5548D1]" /> Student Details</Typography>
                <Box className="mt-3 grid sm:grid-cols-2 gap-4">
                  <Box>
                    <Label className="text-[11px] text-slate-400 uppercase tracking-wider">Student Name</Label>
                    <Typography variant="inherit" component="p" className="text-sm font-semibold text-brand-navy mt-1">{studentName || "—"}</Typography>
                  </Box>
                  <Box>
                    <Label className="text-[11px] text-slate-400 uppercase tracking-wider">Class</Label>
                    <Typography variant="inherit" component="p" className="text-sm font-semibold text-brand-navy mt-1">{studentGrade || "—"}</Typography>
                  </Box>
                </Box>
              </Box>

              {/* Applicant basic details */}
              <Box className="rounded-xl border border-border p-4">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><User className="h-4 w-4 text-[#5548D1]" /> Applicant / Parent Basic Details</Typography>
                <Typography variant="inherit" component="p" className="text-[11px] text-slate-500 mt-0.5">As per PAN card records.</Typography>
                <Box className="mt-4 grid sm:grid-cols-2 gap-4">
                  <Box>
                    <Label className="text-sm text-brand-navy">First Name</Label>
                    <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="rounded-lg mt-1.5" data-testid="kyc-first-name" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Last Name</Label>
                    <Input value={lastName} onChange={(e) => setLastName(e.target.value)} className="rounded-lg mt-1.5" data-testid="kyc-last-name" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Father&apos;s First Name</Label>
                    <Input value={fatherName} onChange={(e) => setFatherName(e.target.value)} placeholder="Ramesh" className="rounded-lg mt-1.5" data-testid="kyc-father-name" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Date of Birth</Label>
                    <DobPicker value={dob} onChange={setDob} data-testid="kyc-dob" />
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Gender</Label>
                    <Select value={gender} onValueChange={setGender}>
                      <SelectTrigger className="rounded-lg mt-1.5" data-testid="kyc-gender"><SelectValue placeholder="Select gender" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Male">Male</SelectItem>
                        <SelectItem value="Female">Female</SelectItem>
                        <SelectItem value="Other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Marital Status</Label>
                    <Select value={maritalStatus} onValueChange={setMaritalStatus}>
                      <SelectTrigger className="rounded-lg mt-1.5" data-testid="kyc-marital"><SelectValue placeholder="Select status" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Single">Single</SelectItem>
                        <SelectItem value="Married">Married</SelectItem>
                        <SelectItem value="Other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Relationship with Student</Label>
                    <Select value={relationship} onValueChange={setRelationship}>
                      <SelectTrigger className="rounded-lg mt-1.5" data-testid="kyc-relationship"><SelectValue placeholder="Select relationship" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Parent">Parent</SelectItem>
                        <SelectItem value="Guardian">Guardian</SelectItem>
                      </SelectContent>
                    </Select>
                  </Box>
                  <Box>
                    <Label className="text-sm text-brand-navy">Email Address</Label>
                    <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="rounded-lg mt-1.5" data-testid="kyc-email" />
                  </Box>
                  <Box className="sm:col-span-2">
                    <Label className="text-sm text-brand-navy flex items-center gap-2">
                      PAN Card Number
                      {cibilResult && cibilResult.approved && (
                        <Box component="span" className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider" data-testid="kyc-pan-verified-chip">
                          <BadgeCheck className="h-3 w-3" /> Verified via CIBIL
                        </Box>
                      )}
                    </Label>
                    <Box className="relative">
                      <Input value={pan} onChange={(e) => setPan(e.target.value.toUpperCase().slice(0, 10))} placeholder="ABCDE1234F"
                        className={`rounded-lg mt-1.5 uppercase ${cibilResult && cibilResult.approved ? "bg-emerald-50/40 border-emerald-200 pr-9" : ""}`}
                        data-testid="kyc-pan" readOnly={!!(cibilResult && cibilResult.approved)} />
                      {cibilResult && cibilResult.approved && (<BadgeCheck className="h-4 w-4 text-emerald-600 absolute right-2.5 top-1/2 -translate-y-1/2 mt-[3px]" />)}
                    </Box>
                    {pan && !PAN_RE.test(pan) && <Typography variant="inherit" component="p" className="text-[11px] text-red-500 mt-1">Format: ABCDE1234F</Typography>}
                  </Box>
                  <Box className="sm:col-span-2">
                    <Label className="text-sm text-brand-navy">Employment Type</Label>
                    <Select value={employment} onValueChange={(v) => { setEmployment(v); setDocs({}); }}>
                      <SelectTrigger className="rounded-lg mt-1.5" data-testid="kyc-employment"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Salaried">Salaried</SelectItem>
                        <SelectItem value="Self-Employed">Self-Employed</SelectItem>
                        <SelectItem value="Self-Employed Professional">Self-Employed Professional</SelectItem>
                      </SelectContent>
                    </Select>
                    {empProfessional && (
                      <Typography variant="inherit" component="p" className="text-[10.5px] text-slate-400 mt-1">Doctors, Lawyers, Architects, Chartered Accountants, Consultants etc.</Typography>
                    )}
                  </Box>
                </Box>
              </Box>

              {/* Address — auto-fetched from profile (read-only) */}
              <Box className="rounded-xl border border-border p-4 bg-slate-50/60" data-testid="kyc-address">
                <Box className="flex items-center justify-between">
                  <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><Landmark className="h-4 w-4 text-[#5548D1]" /> Residential Address</Typography>
                  <Box component="span" className="text-[10px] text-emerald-700 font-bold uppercase tracking-wider">Auto-fetched from profile</Box>
                </Box>
                <Typography variant="inherit" component="p" className="text-sm text-brand-navy mt-2 leading-relaxed">
                  {PROFILE_ADDRESS.line1}, {PROFILE_ADDRESS.locality}, {PROFILE_ADDRESS.city}, {PROFILE_ADDRESS.state} - {PROFILE_ADDRESS.pincode}
                </Typography>
                <Typography variant="inherit" component="p" className="text-[11px] text-slate-500 mt-1">Residence type: {PROFILE_ADDRESS.residenceType}</Typography>
              </Box>

              {/* Aadhaar verification with consent */}
              <Box className="rounded-xl border border-border p-4">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><ScanFace className="h-4 w-4 text-[#5548D1]" /> Aadhaar Verification</Typography>
                <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-1">Authorize fast identity verification via Aadhaar-linked OTP / DigiLocker.</Typography>
                <Box component="label" className="flex items-start gap-3 cursor-pointer mt-3" data-testid="aadhaar-consent-label">
                  <Checkbox checked={aadhaarConsent} onCheckedChange={(v) => setAadhaarConsent(!!v)} className="mt-0.5" data-testid="aadhaar-consent" disabled={aadhaarVerified} />
                  <Box component="span" className="text-xs text-slate-600 leading-relaxed">I consent to verify my identity using my Aadhaar via OTP / DigiLocker as per UIDAI guidelines.</Box>
                </Box>
                {aadhaarVerified ? (
                  <Box className="mt-3 flex items-center gap-2 text-sm font-semibold text-green-600" data-testid="aadhaar-verified">
                    <CheckCircle2 className="h-5 w-5" /> Aadhaar identity verified
                  </Box>
                ) : !otpSent ? (
                  <Button variant="outline" onClick={sendOtp} disabled={!aadhaarConsent} data-testid="send-otp-btn"
                    className="mt-3 h-10 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold">
                    Send Verification Code
                  </Button>
                ) : (
                  <Box className="mt-3 flex items-end gap-2">
                    <Box className="flex-1">
                      <Label className="text-xs text-brand-navy">Enter OTP</Label>
                      <Input value={otp} onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} placeholder="6-digit code" className="rounded-lg mt-1.5" inputMode="numeric" data-testid="otp-input" />
                    </Box>
                    <Button onClick={verifyOtp} data-testid="verify-otp-btn" className="h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">Verify</Button>
                  </Box>
                )}
              </Box>

              {/* Live photo check */}
              <Box className="rounded-xl border border-border p-4">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><Camera className="h-4 w-4 text-[#5548D1]" /> Live Photo Check</Typography>
                <Box className="mt-4 flex flex-col items-center">
                  <Box className="relative h-40 w-40 rounded-full overflow-hidden border-4 border-dashed border-[#5548D1]/40 bg-slate-50 flex items-center justify-center" data-testid="liveness-frame">
                    {camOn && liveness !== "done" ? (
                      <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
                    ) : liveness === "done" ? (
                      <Box className="flex flex-col items-center text-green-600"><CheckCircle2 className="h-10 w-10" /></Box>
                    ) : liveness === "checking" ? (
                      <Loader2 className="h-10 w-10 text-[#5548D1] animate-spin" />
                    ) : (
                      <ScanFace className="h-12 w-12 text-slate-300" />
                    )}
                  </Box>
                  <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-3">
                    {liveness === "done" ? "Live photo verified" : "Position face within the frame"}
                  </Typography>
                  {liveness !== "done" && (
                    <Box className="mt-3 flex gap-2">
                      {!camOn && liveness === "idle" && (
                        <Button variant="outline" onClick={startCam} data-testid="start-cam-btn" className="h-9 rounded-lg border-border text-slate-600 font-semibold">
                          <Camera className="h-4 w-4 mr-1.5" /> Start Camera
                        </Button>
                      )}
                      <Button onClick={captureLiveness} disabled={liveness === "checking"} data-testid="capture-liveness-btn" className="h-9 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
                        {liveness === "checking" ? "Verifying..." : "Capture Selfie & Verify"}
                      </Button>
                    </Box>
                  )}
                </Box>
              </Box>

              {/* Income documents — only when financing above ₹3L */}
              {needDocs && (
                <Box className="rounded-xl border border-amber-200 bg-amber-50/50 p-4" data-testid="kyc-docs">
                  <Typography variant="inherit" component="p" className="font-head font-bold text-amber-900 text-sm flex items-center gap-2"><FileText className="h-4 w-4 text-amber-700" /> Income Documents</Typography>
                  <Typography variant="inherit" component="p" className="text-[11px] text-amber-800 mt-0.5">Required because your financing amount is above {inr(DOC_THRESHOLD)} ({employment}).</Typography>
                  <Box className="mt-3 space-y-2.5">
                    {docsRequired.map((d) => (
                      <Box key={d.key} className="flex items-center justify-between gap-3 rounded-lg bg-white border border-amber-200 p-3">
                        <Box className="flex items-center gap-2 min-w-0">
                          {docs[d.key] ? <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" /> : <FileText className="h-4 w-4 text-amber-600 shrink-0" />}
                          <Box className="min-w-0">
                            <Typography variant="inherit" component="p" className="text-[13px] font-semibold text-brand-navy">{d.label}</Typography>
                            {docs[d.key] && <Typography variant="inherit" component="p" className="text-[11px] text-emerald-700 truncate">{docs[d.key]}</Typography>}
                          </Box>
                        </Box>
                        <Box component="label" className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold text-xs px-3 py-1.5 cursor-pointer" data-testid={`kyc-doc-${d.key}`}>
                          <Upload className="h-3.5 w-3.5" /> {docs[d.key] ? "Replace" : "Upload"}
                          <input type="file" className="hidden" onChange={(e) => uploadDoc(d.key, e.target.files?.[0])} />
                        </Box>
                      </Box>
                    ))}
                  </Box>
                </Box>
              )}

              <Box className="flex items-start gap-2 text-xs text-slate-500 rounded-lg bg-slate-50 p-3" data-testid="kyc-compliance">
                <Lock className="h-4 w-4 text-[#5548D1] shrink-0 mt-0.5" />
                Data transmitted via encrypted RBI-regulated NBFC lending partner rails. Zero manual paperwork.
              </Box>
            </Box>
          )}

          {/* ---------- Step 4: Review & Offer ---------- */}
          {step === 4 && (
            <Box className="space-y-4" data-testid="step-review">
              {!offerReady ? (
                <Box className="py-4" data-testid="review-loading">
                  <Box className="flex flex-col items-center text-center">
                    <Box className="relative h-16 w-16">
                      <Box className="absolute inset-0 rounded-2xl bg-[#EEF0FF] flex items-center justify-center"><ShieldCheck className="h-8 w-8 text-[#5548D1]" /></Box>
                      <Loader2 className="absolute -bottom-1 -right-1 h-6 w-6 text-[#5548D1] animate-spin bg-white rounded-full" />
                    </Box>
                    <Typography variant="inherit" component="p" className="mt-4 font-head font-bold text-brand-navy">We&apos;re reviewing your application</Typography>
                    <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-1">This usually takes a few seconds — hang tight.</Typography>
                  </Box>
                  <Box className="mt-6 space-y-2.5 max-w-sm mx-auto">
                    {[
                      { key: "identity", label: "Identity verified" },
                      { key: "documents", label: "Documents verified" },
                      { key: "credit", label: "Credit assessment" },
                      { key: "decision", label: "Final decision" },
                    ].map((c) => {
                      const st = reviewChecks[c.key];
                      return (
                        <Box key={c.key} className="flex items-center gap-3 rounded-xl border border-border bg-white px-4 py-3" data-testid={`review-check-${c.key}`}>
                          {st === "done" ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                            : st === "running" ? <Loader2 className="h-5 w-5 text-[#5548D1] animate-spin" />
                            : <Box className="h-5 w-5 rounded-full border-2 border-slate-200" />}
                          <Box component="span" className={`text-sm font-medium ${st === "done" ? "text-brand-navy" : "text-slate-500"}`}>{c.label}</Box>
                        </Box>
                      );
                    })}
                  </Box>
                </Box>
              ) : (
                <Box className="space-y-4" data-testid="review-offer">
                  <Box className="flex items-center gap-2 text-emerald-700">
                    <CheckCircle2 className="h-6 w-6" />
                    <Typography variant="inherit" component="p" className="font-head font-black text-lg text-brand-navy">Your Fee payment option is ready</Typography>
                  </Box>

                  {/* Offer economics */}
                  <Box className="rounded-2xl border border-[#5548D1]/20 bg-[#EEF0FF] p-4" data-testid="offer-card">
                    <Box className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
                      <OfferRow label="Financing Amount" value={inr(preview?.financed_amount || 0)} strong />
                      <OfferRow label="Tenure" value={`${tenure} months`} />
                      <OfferRow label="EMI" value={`${inr(preview?.emi || 0)}/mo`} strong accent />
                      <OfferRow label="Interest Rate" value="0%" />
                      <OfferRow label="Handling Charges" value="₹850 + GST" />
                      <OfferRow label="Total Repayment" value={inr(preview?.total_repayment || 0)} />
                      <OfferRow label="Amount Payable Now" value={inr(amountNow)} />
                    </Box>
                  </Box>

                  {/* Fee breakdown */}
                  <Box className="rounded-xl border border-border p-4 space-y-1.5 text-sm" data-testid="offer-fee-breakdown">
                    <Box className="flex justify-between"><Box component="span" className="text-slate-500">School Fee</Box><Box component="span" className="font-semibold">{inr(academicTotal)}</Box></Box>
                    <Box className="flex justify-between"><Box component="span" className="text-slate-500">Upfront Payment</Box><Box component="span" className="font-semibold">{inr(down)}</Box></Box>
                    <Box className="flex justify-between"><Box component="span" className="text-slate-500">Financed Amount</Box><Box component="span" className="font-semibold text-[#5548D1]">{inr(preview?.financed_amount || 0)}</Box></Box>
                  </Box>
                </Box>
              )}
            </Box>
          )}

          {/* ---------- Step 5: Sign + AutoPay + Down-payment (progressive) ---------- */}
          {step === 5 && (
            <Box className="space-y-3" data-testid="step-sign-pay">
              {/* Section 1 — Review & Sign agreement */}
              <GatedSection n={1} done={agreementSigned} locked={false} icon={FileSignature} title="Review & Sign Agreement" subtitle="Read the loan agreement, then e-sign using an OTP.">
                <Button variant="outline" onClick={() => setDocView("agreement")} data-testid="signpay-view-agreement" className="h-8 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold text-xs">
                  <ScrollText className="h-3.5 w-3.5 mr-1.5" /> Read Agreement
                </Button>
                <Box component="label" className="flex items-start gap-2.5 cursor-pointer mt-2.5" data-testid="esign-agree-label">
                  <Checkbox checked={agree} onCheckedChange={(v) => setAgree(!!v)} disabled={agreementSigned} className="mt-0.5" data-testid="esign-agree" />
                  <Box component="span" className="text-[13px] text-slate-600 leading-snug">
                    I accept the <b className="text-brand-navy">Terms &amp; Conditions</b> and confirm all information provided is correct.
                  </Box>
                </Box>
                {agreementSigned ? (
                  <Box className="mt-2.5 flex items-center gap-1.5 text-sm font-semibold text-green-600" data-testid="agreement-signed"><CheckCircle2 className="h-4 w-4" /> Agreement signed</Box>
                ) : !esignSent ? (
                  <Button variant="outline" onClick={sendEsign} disabled={!agree} data-testid="send-esign-btn" className="mt-2.5 h-9 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold text-sm">
                    Send e-Sign OTP
                  </Button>
                ) : (
                  <Box className="mt-2.5 flex items-end gap-2">
                    <Box>
                      <Label className="text-xs text-brand-navy">e-Sign OTP</Label>
                      <Input value={esignOtp} onChange={(e) => setEsignOtp(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} placeholder="6-digit code" className="rounded-lg mt-1 max-w-[160px]" inputMode="numeric" data-testid="esign-otp" />
                    </Box>
                    <Button onClick={verifySign} data-testid="verify-sign-btn" className="h-9 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold text-sm">Verify &amp; Sign</Button>
                  </Box>
                )}
              </GatedSection>

              {/* Section 2 — Set up EMI AutoPay */}
              <GatedSection n={2} done={autopaySet} locked={!agreementSigned} icon={RefreshCw} title="Set Up EMI AutoPay" subtitle="Auto-debit for your monthly EMIs. Reminders sent 5 days prior.">
                <RadioGroup value={rail} onValueChange={changeRail} className="space-y-2" data-testid="wiz-rail-group">
                  {RAILS.map((r) => {
                    const Icon = r.icon; const active = rail === r.key;
                    return (
                      <Box component="label" key={r.key} data-testid={`wiz-rail-${r.key.split(" ")[0].toLowerCase()}`}
                        className={`flex items-center gap-2.5 rounded-lg border p-2.5 cursor-pointer transition-colors ${active ? "border-[#5548D1] bg-[#EEF0FF]" : "border-border hover:border-[#5548D1]/40"}`}>
                        <RadioGroupItem value={r.key} disabled={autopaySet} />
                        <Box className={`h-7 w-7 rounded-lg flex items-center justify-center ${active ? "bg-[#5548D1] text-white" : "bg-slate-100 text-slate-500"}`}><Icon className="h-3.5 w-3.5" /></Box>
                        <Box component="span" className="flex-1 text-[13px] font-medium text-brand-navy">{r.title}</Box>
                        {r.badge && <Box component="span" className="rounded-full bg-[#5548D1] text-white text-[9px] font-bold px-2 py-0.5">{r.badge}</Box>}
                      </Box>
                    );
                  })}
                </RadioGroup>

                {!autopaySet && (
                  <Box className="mt-3">
                    {/* UPI — QR or UPI ID */}
                    {rail === "UPI AutoPay" && (
                      <Box className="rounded-lg border border-border p-3" data-testid="autopay-upi">
                        <Box className="flex flex-col sm:flex-row gap-3 items-center">
                          <Box className="h-24 w-24 shrink-0 rounded-lg bg-white border border-border grid grid-cols-4 grid-rows-4 gap-0.5 p-1.5" data-testid="upi-qr" aria-label="UPI QR code">
                            {Array.from({ length: 16 }).map((_, i) => (
                              <Box key={i} className={`rounded-[1px] ${[0,1,3,4,6,9,11,12,14,15].includes(i) ? "bg-brand-navy" : "bg-transparent"}`} />
                            ))}
                          </Box>
                          <Box className="flex-1 w-full">
                            <Typography variant="inherit" component="p" className="text-[11px] text-slate-500">Scan the QR in any UPI app to set up AutoPay, or enter your UPI ID.</Typography>
                            <Box className="mt-2 flex items-end gap-2">
                              <Box className="flex-1">
                                <Label className="text-xs text-brand-navy">UPI ID</Label>
                                <Input value={upiId} onChange={(e) => setUpiId(e.target.value.trim())} placeholder="name@bank" className="rounded-lg mt-1 lowercase" data-testid="upi-id" />
                              </Box>
                            </Box>
                          </Box>
                        </Box>
                      </Box>
                    )}

                    {/* Net Banking — bank quick select */}
                    {rail === "Net Banking eNACH" && (
                      <Box className="rounded-lg border border-border p-3" data-testid="autopay-netbank">
                        <Typography variant="inherit" component="p" className="text-[11px] text-slate-500 mb-2">Select your bank for the eNACH mandate.</Typography>
                        <Box className="grid grid-cols-3 gap-2">
                          {["CSB Bank", "HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank", "Kotak Mahindra Bank"].map((b) => {
                            const active = netBank === b;
                            return (
                              <Box component="button" type="button" key={b} onClick={() => setNetBank(b)} data-testid={`netbank-${b.split(" ")[0].toLowerCase()}`}
                                className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-2 text-center transition-colors ${active ? "border-[#5548D1] bg-[#EEF0FF] ring-1 ring-[#5548D1]" : "border-border hover:border-[#5548D1]/40"}`}>
                                <Box className={`h-6 w-6 rounded-md flex items-center justify-center ${active ? "bg-[#5548D1] text-white" : "bg-slate-100 text-slate-500"}`}><Landmark className="h-3.5 w-3.5" /></Box>
                                <Box component="span" className="text-[10px] font-semibold text-brand-navy leading-tight">{b}</Box>
                              </Box>
                            );
                          })}
                        </Box>
                      </Box>
                    )}

                    {/* Debit Card mandate */}
                    {rail === "Debit Card Mandate" && (
                      <Box className="rounded-lg border border-border p-3 grid grid-cols-2 gap-3" data-testid="autopay-card">
                        <Box className="col-span-2">
                          <Label className="text-xs text-brand-navy">Card Number</Label>
                          <Input value={cardNumber} onChange={(e) => setCardNumber(e.target.value.replace(/[^0-9]/g, "").slice(0, 16).replace(/(.{4})/g, "$1 ").trim())} placeholder="1234 5678 9012 3456" className="rounded-lg mt-1" inputMode="numeric" data-testid="card-number" />
                        </Box>
                        <Box>
                          <Label className="text-xs text-brand-navy">Expiry (MM/YY)</Label>
                          <Input value={cardExpiry} onChange={(e) => { let v = e.target.value.replace(/[^0-9]/g, "").slice(0, 4); if (v.length >= 3) v = v.slice(0, 2) + "/" + v.slice(2); setCardExpiry(v); }} placeholder="MM/YY" className="rounded-lg mt-1" inputMode="numeric" data-testid="card-expiry" />
                        </Box>
                        <Box>
                          <Label className="text-xs text-brand-navy">CVV</Label>
                          <Input type="password" value={cardCvv} onChange={(e) => setCardCvv(e.target.value.replace(/[^0-9]/g, "").slice(0, 4))} placeholder="•••" className="rounded-lg mt-1" inputMode="numeric" data-testid="card-cvv" />
                        </Box>
                      </Box>
                    )}

                    <Button onClick={setupAutopay} disabled={!railReady || autopayWorking} data-testid="setup-autopay-btn" className="mt-3 h-9 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold text-sm px-5">
                      {autopayWorking ? <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Setting up...</> : <>Set Up AutoPay</>}
                    </Button>
                  </Box>
                )}
                {autopaySet && (
                  <Box className="mt-2.5 flex items-center gap-1.5 text-sm font-semibold text-green-600" data-testid="autopay-done"><CheckCircle2 className="h-4 w-4" /> AutoPay mandate active — {rail}</Box>
                )}
              </GatedSection>

              {/* Section 3 — Complete the down-payment */}
              <GatedSection n={3} done={upfrontPaid} locked={!autopaySet} icon={CreditCard} title="Complete the down-payment" subtitle="">
                <Box className="rounded-lg bg-[#EEF0FF] p-2.5 space-y-1 text-[13px]" data-testid="upfront-pay">
                  {down > 0 && <Box className="flex justify-between"><Box component="span" className="text-slate-500">Down payment</Box><Box component="span" className="font-semibold">{inr(down)}</Box></Box>}
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Processing fee (incl. GST)</Box><Box component="span" className="font-semibold">{inr(preview?.processing_fee || 0)}</Box></Box>
                  <Box className="flex justify-between border-t border-[#5548D1]/15 pt-1.5 mt-1.5"><Box component="span" className="font-semibold text-brand-navy">Amount Payable Now</Box><Box component="span" className="font-head font-black text-[#5548D1]">{inr(amountNow)}</Box></Box>
                </Box>
                {upfrontPaid ? (
                  <Box className="mt-2.5 flex items-center gap-1.5 text-sm font-semibold text-green-600" data-testid="upfront-paid"><CheckCircle2 className="h-4 w-4" /> Payment successful</Box>
                ) : (
                  <Button onClick={payUpfront} disabled={payingUpfront} data-testid="pay-upfront-btn" className="mt-2.5 h-9 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold text-sm w-full sm:w-auto px-6">
                    {payingUpfront ? <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Processing...</> : <>Pay {inr(amountNow)}</>}
                  </Button>
                )}
              </GatedSection>

              <Box className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-slate-500 pt-1">
                <Box component="span" className="flex items-center gap-1.5"><BadgeCheck className="h-3.5 w-3.5 text-[#5548D1]" /> RBI-regulated NBFC</Box>
                <Box component="span" className="flex items-center gap-1.5"><Lock className="h-3.5 w-3.5 text-[#5548D1]" /> 256-Bit Encryption</Box>
              </Box>
            </Box>
          )}

          {/* ---------- Step 6: All set ---------- */}
          {step === 6 && result && (
            <Box className="space-y-4" data-testid="step-done">
              <Box className="flex flex-col items-center text-center py-2">
                <Box className="h-16 w-16 rounded-2xl bg-emerald-100 flex items-center justify-center"><PartyPopper className="h-8 w-8 text-emerald-600" /></Box>
                <Typography variant="inherit" component="p" className="mt-3 font-head font-black text-xl text-brand-navy">You&apos;re all set!</Typography>
                <Typography variant="inherit" component="p" className="text-sm text-slate-500 mt-1">Your 0% EMI financing is now active.</Typography>
              </Box>

              <Box className="rounded-xl border border-border p-4" data-testid="done-fee-summary">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm">School Fee Payment</Typography>
                <Box className="mt-2 space-y-1.5 text-sm">
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Total Fee</Box><Box component="span" className="font-semibold">{inr(result.amount)}</Box></Box>
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Paid Upfront</Box><Box component="span" className="font-semibold">{inr(result.down_payment)}</Box></Box>
                  <Box className="flex justify-between"><Box component="span" className="text-slate-500">Financed</Box><Box component="span" className="font-semibold text-[#5548D1]">{inr(result.financed_amount)}</Box></Box>
                </Box>
              </Box>

              <Box className="rounded-xl border border-border p-4" data-testid="done-active">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm">Active Financing</Typography>
                <Box className="mt-2 grid grid-cols-3 gap-2 text-center">
                  <Box className="rounded-lg bg-[#EEF0FF] p-2.5"><Box component="span" className="block text-[10px] text-slate-400 uppercase">EMI</Box><Box component="span" className="font-head font-bold text-brand-navy">{inr(result.emi)}</Box></Box>
                  <Box className="rounded-lg bg-[#EEF0FF] p-2.5"><Box component="span" className="block text-[10px] text-slate-400 uppercase">Tenure</Box><Box component="span" className="font-head font-bold text-brand-navy">{result.tenure} mo</Box></Box>
                  <Box className="rounded-lg bg-[#EEF0FF] p-2.5"><Box component="span" className="block text-[10px] text-slate-400 uppercase">Next EMI</Box><Box component="span" className="font-head font-bold text-brand-navy text-[13px]">{nextEmi?.due_date || "—"}</Box></Box>
                </Box>
              </Box>

              <Box className="rounded-xl border border-border p-4" data-testid="done-status">
                <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm mb-2">Agreement Status</Typography>
                {["Agreement signed", "AutoPay active", "Upfront payment successful", "Financing active"].map((t) => (
                  <Box key={t} className="flex items-center gap-2 text-sm text-brand-navy py-0.5"><CheckCircle2 className="h-4 w-4 text-emerald-600" /> {t}</Box>
                ))}
                <Box className="mt-2 pt-2 border-t border-border text-xs text-slate-500">Agreement ID: <b className="text-brand-navy font-mono">{result.agreement_id || result.receipt_no}</b></Box>
              </Box>

              <Box className="flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => setDocView("agreement")} data-testid="done-view-agreement" className="h-10 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold text-sm">
                  <FileSignature className="h-4 w-4 mr-1.5" /> View Active Agreement
                </Button>
                <Button variant="outline" onClick={() => setDocView("schedule")} data-testid="done-view-schedule" className="h-10 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold text-sm">
                  <Calendar className="h-4 w-4 mr-1.5" /> View Repayment Schedule
                </Button>
                <Button variant="outline" onClick={() => toast.success("Documents downloaded (simulated)")} data-testid="done-download" className="h-10 rounded-lg border-border text-slate-600 hover:bg-slate-50 font-semibold text-sm">
                  <Download className="h-4 w-4 mr-1.5" /> Download Documents
                </Button>
              </Box>
            </Box>
          )}
        </Box>

        {/* Footer actions */}
        {step <= 5 ? (
          <Box className="px-6 md:px-8 py-4 border-t border-border flex items-center justify-between gap-3 bg-white">
            <Button variant="outline" onClick={back} disabled={step === 1 || processing} data-testid="wiz-back" className="h-11 rounded-lg border-border text-slate-600 font-semibold">
              <ArrowLeft className="h-4 w-4 mr-1.5" /> Back
            </Button>
            <Button onClick={next} disabled={!canContinue || processing} data-testid="wiz-next" className="h-11 px-6 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] text-white font-semibold">
              {processing ? "Activating..."
                : step === 4 ? <><ArrowRight className="h-4 w-4 mr-1.5" /> Proceed</>
                : step === 5 ? <><ShieldCheck className="h-4 w-4 mr-1.5" /> Confirm &amp; Activate</>
                : <>Continue <ArrowRight className="h-4 w-4 ml-1.5" /></>}
            </Button>
          </Box>
        ) : (
          <Box className="px-6 md:px-8 py-4 border-t border-border flex items-center justify-end bg-white">
            <Button onClick={() => onOpenChange(false)} data-testid="wiz-done" className="h-11 px-8 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] text-white font-semibold">
              Done
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}

/* -------- Progressive gated section (Step 5) -------- */
function GatedSection({ n, title, subtitle, icon: Icon, done, locked, children }) {
  return (
    <Box className={`rounded-xl border p-3.5 transition-all ${done ? "border-emerald-200 bg-emerald-50/30" : locked ? "border-border bg-slate-50/60" : "border-[#5548D1]/30 bg-white"}`}
      data-testid={`gated-section-${n}`}>
      <Box className="flex items-center gap-2.5">
        <Box component="span" className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${done ? "bg-emerald-500 text-white" : locked ? "bg-slate-200 text-slate-400" : "bg-[#5548D1] text-white"}`}>
          {done ? <Check className="h-4 w-4" /> : locked ? <Lock className="h-3.5 w-3.5" /> : n}
        </Box>
        <Box className="min-w-0">
          <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-1.5"><Icon className="h-4 w-4 text-[#5548D1]" /> {title}</Typography>
          {subtitle && <Typography variant="inherit" component="p" className="text-[11px] text-slate-500">{subtitle}</Typography>}
        </Box>
      </Box>
      {!locked && <Box className="mt-3">{children}</Box>}
      {locked && <Typography variant="inherit" component="p" className="mt-2 text-[11px] text-slate-400 italic">Complete the previous step to unlock.</Typography>}
    </Box>
  );
}

/* -------- Offer economics row -------- */
function OfferRow({ label, value, strong = false, accent = false }) {
  return (
    <Box className="flex flex-col">
      <Box component="span" className="text-[10.5px] text-slate-500 uppercase tracking-wider">{label}</Box>
      <Box component="span" className={`${strong ? "font-head font-black" : "font-semibold"} ${accent ? "text-[#5548D1]" : "text-brand-navy"}`}>{value}</Box>
    </Box>
  );
}

/* -------- In-body document overlay (KFS / Agreement / Repayment Schedule) -------- */
function DocOverlay({ kind, onClose, preview, result, applicant, studentName, tenure, down, academicTotal }) {
  const financed = result?.financed_amount ?? preview?.financed_amount ?? 0;
  const emi = result?.emi ?? preview?.emi ?? 0;
  const pf = result?.processing_fee ?? preview?.processing_fee ?? 0;
  const schedule = result?.schedule || preview?.schedule || [];
  const title = kind === "kfs" ? "Key Fact Statement (KFS)" : kind === "agreement" ? "Loan Agreement" : "Repayment Schedule";

  return (
    <Box className="absolute inset-0 z-20 bg-white flex flex-col" data-testid="doc-overlay">
      <Box className="flex items-center justify-between px-1 pb-3 border-b border-border">
        <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><ScrollText className="h-4 w-4 text-[#5548D1]" /> {title}</Typography>
        <Button variant="outline" onClick={onClose} data-testid="doc-overlay-close" className="h-8 rounded-lg border-border text-slate-600 font-semibold text-xs">
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back
        </Button>
      </Box>
      <Box className="flex-1 overflow-y-auto pt-3 text-sm text-slate-700 space-y-3">
        {kind === "schedule" ? (
          <Box className="rounded-lg border border-border divide-y divide-border overflow-hidden">
            {schedule.length === 0 && <Box className="p-3 text-slate-400 text-xs">No schedule available.</Box>}
            {schedule.map((s) => (
              <Box key={s.month} className="flex items-center justify-between px-3 py-2 text-[13px]">
                <Box component="span" className="text-slate-500">{s.label || `EMI ${s.month}`}</Box>
                <Box component="span" className="text-slate-500">{s.due_date}</Box>
                <Box component="span" className="font-semibold text-brand-navy">{inr(s.amount)}</Box>
                <Box component="span" className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full ${s.status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{s.status}</Box>
              </Box>
            ))}
          </Box>
        ) : kind === "kfs" ? (
          <>
            <Box className="rounded-lg bg-slate-50 border border-border p-3 space-y-1.5">
              <Row k="Applicant" v={applicant || "—"} />
              <Row k="Student" v={studentName || "—"} />
              <Row k="Lender" v="CSB Bank Limited" />
              <Row k="School Fee" v={inr(academicTotal)} />
              <Row k="Down Payment" v={inr(down)} />
              <Row k="Financed Amount" v={inr(financed)} />
              <Row k="Tenure" v={`${tenure} months`} />
              <Row k="Monthly EMI" v={inr(emi)} />
              <Row k="Interest Rate" v="0% p.a." />
              <Row k="Processing Fee (incl. GST)" v={inr(pf)} />
              <Row k="Total Repayment" v={inr(financed)} />
            </Box>
            <Typography variant="inherit" component="p" className="text-xs text-slate-500 leading-relaxed">
              This Key Fact Statement summarises the key terms of your 0% interest education-fee financing facility as mandated by the RBI Digital Lending Guidelines. There is no interest charged on this facility; a one-time processing fee (inclusive of GST) applies as shown above. Prepayment is allowed with no foreclosure charges. Missed EMIs may attract nominal late-payment fees and be reported to credit bureaus.
            </Typography>
          </>
        ) : (
          <AgreementDoc
            applicant={applicant}
            studentName={studentName}
            tenure={tenure}
            down={down}
            academicTotal={academicTotal}
            financed={financed}
            emi={emi}
            agreementId={result?.agreement_id || result?.receipt_no}
          />
        )}
      </Box>
    </Box>
  );
}
function Row({ k, v }) {
  return (
    <Box className="flex justify-between gap-4">
      <Box component="span" className="text-slate-500">{k}</Box>
      <Box component="span" className="font-semibold text-brand-navy text-right">{v}</Box>
    </Box>
  );
}

/* -------- Full CSB Bank Limited School Fee Financing Loan Agreement -------- */
function AgreementDoc({ applicant, studentName, tenure, down, academicTotal, financed, emi, agreementId }) {
  const HANDLING = 850;
  const GST = Math.round(HANDLING * 0.18); // 18% GST => ₹153
  const HANDLING_TOTAL = HANDLING + GST; // ₹1,003
  const today = new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });

  const clauseHead = "font-head font-bold text-brand-navy text-[13px] mt-4 mb-1.5";
  const para = "text-[12px] text-slate-600 leading-relaxed";

  const declarations = [
    "confirms that all information and documents submitted for KYC, credit assessment and loan processing are true, accurate and complete;",
    "confirms that the loan proceeds shall be used solely for the stated school-fee financing purpose;",
    "authorises the Lender and its authorised service providers to verify KYC and other information and, where legally permitted, obtain / share information with credit information companies and other authorised entities;",
    "authorises auto-debit of the EMIs through the selected mandate;",
    "agrees to comply with the repayment schedule and all applicable terms of the loan;",
    "acknowledges that the loan remains repayable notwithstanding any dispute between the Applicant and the school concerning services, admission, withdrawal or other matters, subject to applicable law and the terms of the financing arrangement; and",
    "confirms that the Applicant has reviewed and understood the applicable KFS, repayment schedule, charges and other applicable terms before accepting the facility.",
  ];

  return (
    <Box data-testid="agreement-doc" className="text-slate-700">
      {/* Header */}
      <Box className="text-center border-b border-border pb-3">
        <Typography variant="inherit" component="p" className="font-head font-black text-brand-navy text-[15px] tracking-tight">
          SCHOOL FEE FINANCING LOAN AGREEMENT
        </Typography>
        <Box className="mt-1.5 flex items-center justify-center gap-4 text-[11px] text-slate-500">
          <Box component="span"><b className="text-slate-600">Date:</b> {today}</Box>
          <Box component="span" className="h-3 w-px bg-border" />
          <Box component="span"><b className="text-slate-600">Loan / Application No.:</b> <span className="font-mono">{agreementId || "To be generated on activation"}</span></Box>
        </Box>
      </Box>

      {/* Recital */}
      <Typography variant="inherit" component="p" className={`${para} mt-3`}>
        This School Fee Financing Loan Agreement (&quot;Agreement&quot;) is entered into between{" "}
        <b className="text-brand-navy">CSB Bank Limited</b> (&quot;Lender / Bank&quot;) and{" "}
        <b className="text-brand-navy">{applicant || "the Applicant"}</b> (&quot;Applicant / Borrower&quot;) for financing
        the school fees of <b className="text-brand-navy">{studentName || "the Student"}</b> (&quot;Student&quot;),
        subject to the terms and conditions set out below.
      </Typography>

      {/* 1. Loan Details */}
      <Typography variant="inherit" component="p" className={clauseHead}>1. Loan Details</Typography>
      <Box className="rounded-lg bg-slate-50 border border-border p-3 space-y-1.5">
        <Row k="Applicant / Borrower" v={applicant || "—"} />
        <Row k="Student" v={studentName || "—"} />
        <Row k="Lender" v="CSB Bank Limited" />
        <Row k="Total School Fee" v={inr(academicTotal)} />
        <Row k="Down Payment" v={inr(down)} />
        <Row k="Financed Amount" v={inr(financed)} />
        <Row k="Tenure" v={`${tenure} months`} />
        <Row k="Interest Rate" v="0% p.a." />
        <Row k="Monthly EMI" v={`${inr(emi)}*`} />
        <Row k="Handling Charges" v={`₹850 + applicable GST (${inr(HANDLING_TOTAL)} incl. 18% GST)`} />
        <Row k="Total Principal Repayment" v={inr(financed)} />
      </Box>
      <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 italic mt-1.5 leading-relaxed">
        *The final EMI schedule and due dates shall be as specified in the applicable Key Facts Statement (KFS) / sanction
        communication. Any rounding adjustment in the final instalment, if applicable, shall be reflected in the repayment schedule.
      </Typography>

      {/* 2. Purpose and Disbursement */}
      <Typography variant="inherit" component="p" className={clauseHead}>2. Purpose and Disbursement</Typography>
      <Typography variant="inherit" component="p" className={para}>
        The loan facility is sanctioned solely for payment of the Student&apos;s school fees. Upon fulfilment of all applicable
        conditions and completion of documentation, the 100% financed amount of {inr(financed)} shall be disbursed upfront to the
        school towards the Student&apos;s eligible school fees. The Applicant acknowledges that the {inr(down)} down payment (if any)
        is to be paid separately by the Applicant towards the total school fee of {inr(academicTotal)}.
      </Typography>

      {/* 3. Repayment */}
      <Typography variant="inherit" component="p" className={clauseHead}>3. Repayment</Typography>
      <Typography variant="inherit" component="p" className={para}>
        The Applicant agrees to repay the financed amount in {tenure} monthly EMIs of {inr(emi)}, subject to the final repayment
        schedule issued by the Lender. The applicable interest rate for the facility is 0% per annum, and accordingly the total
        principal repayment under the facility is {inr(financed)}, excluding the applicable handling charges and GST.
        The Applicant authorises the Lender and / or its authorised service providers to collect the EMIs through the selected
        NACH / e-mandate / auto-debit / payment mandate. The Applicant shall ensure that sufficient funds are available in the
        designated account on each EMI due date. Any applicable charges arising from failed mandates, delayed payments, statutory
        levies, or other permitted charges shall be governed by the applicable KFS, sanction terms and Lender&apos;s policies.
      </Typography>

      {/* 4. Applicant Declarations and Undertakings */}
      <Typography variant="inherit" component="p" className={clauseHead}>4. Applicant Declarations and Undertakings</Typography>
      <Typography variant="inherit" component="p" className={para}>By electronically signing this Agreement, the Applicant:</Typography>
      <Box component="ol" className="mt-1.5 space-y-1.5 pl-1">
        {declarations.map((d, i) => (
          <Box component="li" key={i} className="flex gap-2 text-[12px] text-slate-600 leading-relaxed">
            <Box component="span" className="font-semibold text-[#5548D1] shrink-0">{i + 1}.</Box>
            <Box component="span">{d}</Box>
          </Box>
        ))}
      </Box>

      {/* 5. Fees and Charges */}
      <Typography variant="inherit" component="p" className={clauseHead}>5. Fees and Charges</Typography>
      <Typography variant="inherit" component="p" className={para}>
        The Applicant shall pay the applicable handling charge of ₹850 plus GST (totalling {inr(HANDLING_TOTAL)} inclusive of 18% GST),
        in accordance with the applicable KFS / charge schedule. No interest shall accrue on the financed amount at the stated
        contractual rate of 0% p.a., subject to the terms of this Agreement and applicable law.
      </Typography>

      {/* 6. Default */}
      <Typography variant="inherit" component="p" className={clauseHead}>6. Default</Typography>
      <Typography variant="inherit" component="p" className={para}>
        If any EMI is not paid on its due date, the Lender may take such action as is permitted under the applicable loan terms,
        KFS, mandate terms and applicable law, including recovery of overdue amounts and applicable permitted charges. Any applicable
        penal / late-payment charges, if any, shall be as expressly disclosed in the applicable KFS or sanction documentation and
        shall not be treated as interest on the loan unless permitted under applicable law.
      </Typography>

      {/* 7. Privacy and Data Consent */}
      <Typography variant="inherit" component="p" className={clauseHead}>7. Privacy and Data Consent</Typography>
      <Typography variant="inherit" component="p" className={para}>
        The Applicant consents to the collection, verification, processing, storage and sharing of personal and financial information
        for purposes connected with the loan, including KYC, underwriting, servicing, repayment, fraud prevention, regulatory compliance
        and credit reporting, in accordance with applicable law and the Lender&apos;s privacy policy. CSB Bank&apos;s published privacy
        policy provides for processing and sharing of customer information for purposes including verification, credit reporting, risk
        management and regulatory requirements.
      </Typography>

      {/* 8. Grievance Redressal */}
      <Typography variant="inherit" component="p" className={clauseHead}>8. Grievance Redressal</Typography>
      <Typography variant="inherit" component="p" className={para}>
        The Applicant may raise any complaint or grievance through the Lender&apos;s designated grievance-redressal channels. Where the
        complaint is not satisfactorily resolved within the applicable period, the Applicant may pursue the escalation mechanisms available
        under applicable RBI regulations. CSB Bank currently provides a multi-level grievance-redressal mechanism and escalation to the RBI
        Integrated Ombudsman framework where applicable.
      </Typography>

      {/* 9. Governing Terms */}
      <Typography variant="inherit" component="p" className={clauseHead}>9. Governing Terms</Typography>
      <Typography variant="inherit" component="p" className={para}>
        This Agreement, together with the applicable Key Facts Statement (KFS), sanction letter, repayment schedule, mandate terms and other
        loan documentation, constitutes the terms governing the facility. In case of any inconsistency, the applicable regulatory requirements
        and the final executed loan documentation / KFS shall prevail. This Agreement shall be governed by the laws of India and subject to
        applicable regulatory requirements.
      </Typography>

      {/* 10. Electronic Acceptance */}
      <Typography variant="inherit" component="p" className={clauseHead}>10. Electronic Acceptance</Typography>
      <Typography variant="inherit" component="p" className={para}>
        The Applicant agrees that electronic signing / e-signing, OTP-based acceptance or other approved electronic authentication shall
        constitute valid acceptance of this Agreement and shall have the same effect as a physical signature, to the extent permitted by applicable law.
      </Typography>

      {/* Signature block */}
      <Box className="mt-5 pt-4 border-t border-border grid grid-cols-2 gap-4">
        <Box>
          <Typography variant="inherit" component="p" className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Applicant / Borrower</Typography>
          <Typography variant="inherit" component="p" className="text-[12px] text-slate-600 mt-1.5">Name: <b className="text-brand-navy">{applicant || "—"}</b></Typography>
          <Typography variant="inherit" component="p" className="text-[12px] text-slate-400 mt-1">Signature: _______________________</Typography>
          <Typography variant="inherit" component="p" className="text-[12px] text-slate-400 mt-1">Date: {today}</Typography>
        </Box>
        <Box>
          <Typography variant="inherit" component="p" className="text-[11px] font-bold uppercase tracking-wider text-slate-500">For CSB Bank Limited</Typography>
          <Typography variant="inherit" component="p" className="text-[12px] text-slate-400 mt-1.5">Authorised Signatory: ____________</Typography>
          <Typography variant="inherit" component="p" className="text-[12px] text-slate-400 mt-1">Date: {today}</Typography>
        </Box>
      </Box>

      <Box className="mt-4 rounded-lg bg-[#EEF0FF] border border-[#5548D1]/20 p-3">
        <Typography variant="inherit" component="p" className="text-[11px] text-slate-600 leading-relaxed">
          <b className="text-brand-navy">Acknowledgement:</b> By e-signing this Agreement, the Applicant confirms that they have read,
          understood and accepted the above terms and authorises the applicable repayment mandate for the {tenure}-month school-fee financing facility.
        </Typography>
      </Box>
    </Box>
  );
}

/* -------- Delightful "Did you know?" loader (shown during CIBIL soft-pull) -------- */
const TRIVIA = [
  "The first rupee in India was introduced by Sher Shah Suri in the 16th century.",
  "A soft pull check never impacts your credit score — banks do it thousands of times a day.",
  "0% EMI = the school gets 100% of the fee upfront; you just spread your payments — no interest.",
  "Your CIBIL score updates once every 30-45 days, so back-to-back checks show the same number.",
  "eNACH mandates take under 60 seconds to set up — nothing like the paper mandates of 2015.",
  "India's UPI processes more transactions per day than Visa in most weeks.",
];

function TriviaLoader({ title, subtitle, ...rest }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setIdx((i) => (i + 1) % TRIVIA.length), 3200);
    return () => clearInterval(id);
  }, []);
  return (
    <Box className="rounded-2xl border border-dashed border-[#5548D1]/40 bg-white p-6 flex items-center gap-5" {...rest}>
      <Box className="relative h-16 w-16 shrink-0">
        <Box className="absolute inset-0 rounded-2xl bg-[#EEF0FF] flex items-center justify-center">
          <BookOpen className="h-8 w-8 text-[#5548D1]" />
        </Box>
        <Box className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-[#5548D1] text-white flex items-center justify-center animate-pulse">
          <Sparkle className="h-3 w-3" />
        </Box>
      </Box>
      <Box className="min-w-0 flex-1">
        <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2">
          {title || "Just a moment…"}
          <Loader2 className="h-3.5 w-3.5 text-[#5548D1] animate-spin" />
        </Typography>
        {subtitle && <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-0.5">{subtitle}</Typography>}
        <Box className="mt-3 rounded-lg bg-slate-50 border border-slate-100 p-3">
          <Typography variant="inherit" component="p" className="text-[10px] uppercase tracking-widest font-bold text-[#5548D1] flex items-center gap-1.5">
            <Sparkle className="h-3 w-3" /> Did you know?
          </Typography>
          <Typography variant="inherit" component="p" key={idx} className="mt-1 text-[13px] text-slate-700 leading-relaxed animate-in fade-in duration-500">
            {TRIVIA[idx]}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

/* -------- Grandparent-friendly Date-of-Birth picker (Day / Month / Year) -------- */
const DOB_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function DobPicker({ value, onChange, ...rest }) {
  const parseParts = (v) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v || "");
    return m ? { y: m[1], mo: m[2], d: m[3] } : { y: "", mo: "", d: "" };
  };
  const [parts, setParts] = useState(parseParts(value));
  useEffect(() => { setParts(parseParts(value)); }, [value]);

  const now = new Date();
  const years = useMemo(() => {
    const arr = [];
    for (let y = now.getFullYear(); y >= 1930; y--) arr.push(String(y));
    return arr;
  }, [now]);
  const daysInMonth = useMemo(() => {
    const y = parseInt(parts.y || "2000", 10);
    const mo = parseInt(parts.mo || "1", 10);
    return new Date(y, mo, 0).getDate();
  }, [parts.y, parts.mo]);
  const days = Array.from({ length: daysInMonth }, (_, i) => String(i + 1).padStart(2, "0"));

  const commit = (p) => {
    setParts(p);
    if (p.y && p.mo && p.d) onChange(`${p.y}-${p.mo}-${p.d}`);
  };

  return (
    <Box className="grid grid-cols-3 gap-2 mt-1.5" {...rest}>
      <Select value={parts.d} onValueChange={(v) => commit({ ...parts, d: v })}>
        <SelectTrigger className="rounded-lg" data-testid="dob-day"><SelectValue placeholder="Day" /></SelectTrigger>
        <SelectContent className="max-h-64">
          {days.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select value={parts.mo} onValueChange={(v) => commit({ ...parts, mo: v })}>
        <SelectTrigger className="rounded-lg" data-testid="dob-month"><SelectValue placeholder="Month" /></SelectTrigger>
        <SelectContent className="max-h-64">
          {DOB_MONTHS.map((mo, i) => (
            <SelectItem key={mo} value={String(i + 1).padStart(2, "0")}>{mo}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={parts.y} onValueChange={(v) => commit({ ...parts, y: v })}>
        <SelectTrigger className="rounded-lg" data-testid="dob-year"><SelectValue placeholder="Year" /></SelectTrigger>
        <SelectContent className="max-h-64">
          {years.map((y) => <SelectItem key={y} value={y}>{y}</SelectItem>)}
        </SelectContent>
      </Select>
    </Box>
  );
}

/* -------- CIBIL Score Gauge (SVG semi-circle meter) -------- */
function CibilGauge({ score, target, band, color = "blue" }) {
  const min = 300, max = 900;
  const clamped = Math.max(min, Math.min(max, score));
  const pct = (clamped - min) / (max - min);
  const angle = Math.PI * (1 - pct);
  const cx = 90, cy = 90, r = 72;
  const x = cx + r * Math.cos(angle);
  const y = cy - r * Math.sin(angle);
  const stroke = { emerald: "#10B981", blue: "#5548D1", amber: "#F59E0B", red: "#EF4444" }[color] || "#5548D1";
  const startX = cx - r, startY = cy;
  const arcPath = `M ${startX} ${startY} A ${r} ${r} 0 0 1 ${x} ${y}`;
  const bgPath = `M ${startX} ${startY} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
  return (
    <Box className="flex flex-col items-center shrink-0" data-testid="cibil-gauge">
      <svg width="180" height="110" viewBox="0 0 180 110">
        <path d={bgPath} stroke="#E5E7EB" strokeWidth="12" fill="none" strokeLinecap="round" />
        <path d={arcPath} stroke={stroke} strokeWidth="12" fill="none" strokeLinecap="round" />
        <text x={cx} y={cy - 4} textAnchor="middle" className="font-head" fontSize="26" fontWeight="800" fill="#0B1F44">
          {Math.round(score)}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fontSize="10" fill="#64748B" letterSpacing="1">
          / 900
        </text>
      </svg>
      <Box component="span" className="mt-1 text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full" style={{ color: stroke, backgroundColor: stroke + "1A" }}>
        {band}
      </Box>
    </Box>
  );
}
