'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useMemo, useRef, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import {
  MapPin, ShieldCheck, Camera, ScanFace, CheckCircle2, Loader2, AlertTriangle,
  Video, RefreshCw, User, CalendarDays, Info, ArrowRight, Fingerprint,
} from "lucide-react";

// Aadhaar address on record — bank-dependent source (HARDCODED mock for this build).
const AADHAAR_ADDRESS = {
  line1: "Flat 402, Royal Palms, Vasant Kunj",
  city: "New Delhi",
  state: "Delhi",
  pincode: "110070",
};

const norm = (s) => (s || "").toString().trim().toLowerCase().replace(/\s+/g, " ");
const normPin = (s) => (s || "").toString().replace(/\D/g, "");

const MatchBadge = ({ ok }) => (
  <Box component="span" className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
    {ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}{ok ? "Match" : "Mismatch"}
  </Box>
);
const SrcRow = ({ label, value, badge }) => (
  <Box className="flex items-center justify-between gap-3 py-1.5">
    <Box component="span" className="text-[11px] uppercase tracking-wider text-slate-400 w-20 shrink-0">{label}</Box>
    <Box component="span" className="text-sm font-semibold text-brand-navy flex-1 truncate">{value || "—"}</Box>
    {badge}
  </Box>
);

export function KycVerification({
  profileName, profileDob, nameMatchRule = "aadhaar", locationMatchEnabled = true,
  onVerified, onExitHome, onProfileUpdate,
}) {
  const [stage, setStage] = useState("nudge"); // nudge | ekyc | video | decline_name | decline_dob | decline_location

  // Pre-KYC nudge — Aadhaar name/DOB are editable (demo hook to trip a mismatch).
  const panName = profileName;                 // as-per-PAN (mirrors profile in this build)
  const panDob = profileDob;
  const [aadhaarName, setAadhaarName] = useState(profileName || "");
  const [aadhaarDob, setAadhaarDob] = useState(profileDob || "");
  useEffect(() => { setAadhaarName(profileName || ""); }, [profileName]);
  useEffect(() => { setAadhaarDob(profileDob || ""); }, [profileDob]);

  const nameMatch = norm(profileName) === norm(panName) && norm(panName) === norm(aadhaarName);
  const dobMatch = norm(profileDob) === norm(panDob) && norm(panDob) === norm(aadhaarDob);

  // Correction inputs
  const [correctName, setCorrectName] = useState("");
  const [correctDob, setCorrectDob] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  // E-KYC — Aadhaar
  const [aadhaarConsent, setAadhaarConsent] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [aadhaarVerified, setAadhaarVerified] = useState(false);

  // E-KYC — location match
  const [pincode, setPincode] = useState(AADHAAR_ADDRESS.pincode);
  const [locStatus, setLocStatus] = useState("idle"); // idle|requesting|checking|matched|denied|unavailable|timeout|no_postcode|error
  const [detectedPin, setDetectedPin] = useState("");
  const locationOk = !locationMatchEnabled || locStatus === "matched";

  // E-KYC — liveness (camera motion-based check; see LivenessCheck component below)
  const [liveness, setLiveness] = useState("idle"); // idle|done

  // Compliance (silent, hardcoded pass) + completion guard
  const [compliance, setCompliance] = useState("idle"); // idle|running|pass
  const doneRef = useRef(false);
  const complianceStartedRef = useRef(false);
  const complianceTimerRef = useRef(null);
  // Clear the pending completion timer ONLY on unmount (never on effect re-run).
  useEffect(() => () => { if (complianceTimerRef.current) clearTimeout(complianceTimerRef.current); }, []);

  // Video KYC
  const [videoStage, setVideoStage] = useState("idle"); // idle|connecting|verifying|done

  // ---- Nudge -> verification ----
  const continueFromNudge = () => {
    if (!nameMatch) { setCorrectName(profileName || ""); setStage("decline_name"); return; }
    if (!dobMatch) { setCorrectDob(profileDob || ""); setStage("decline_dob"); return; }
    setStage("ekyc");
  };

  const saveNameCorrection = async () => {
    if (!correctName.trim()) { toast.error("Please enter your name as per records"); return; }
    setSavingProfile(true);
    try {
      await api.put("/parent/profile", { name: correctName.trim() });
      onProfileUpdate?.(correctName.trim(), null);     // profile becomes value of record
      setAadhaarName(correctName.trim());
      toast.success("Profile name updated");
      setStage("ekyc");
    } catch {
      toast.error("Could not update your profile");
    } finally { setSavingProfile(false); }
  };

  const saveDobCorrection = async () => {
    if (!correctDob.trim()) { toast.error("Please enter your date of birth"); return; }
    setSavingProfile(true);
    try {
      await api.put("/parent/profile", { dob: correctDob.trim() });
      onProfileUpdate?.(null, correctDob.trim());
      setAadhaarDob(correctDob.trim());
      toast.success("Profile date of birth updated");
      setStage("ekyc");
    } catch {
      toast.error("Could not update your profile");
    } finally { setSavingProfile(false); }
  };

  // ---- Aadhaar OTP (simulated) ----
  const sendOtp = () => {
    if (!aadhaarConsent) { toast.error("Please provide Aadhaar verification consent"); return; }
    setOtpSent(true); toast.success("OTP sent to Aadhaar-linked mobile (simulated)");
  };
  const verifyOtp = () => {
    if (otp.trim().length < 4) { toast.error("Enter the 6-digit code"); return; }
    setAadhaarVerified(true); toast.success("Aadhaar identity verified");
  };

  // ---- Real location-match: device geolocation + Nominatim reverse-geocode ----
  const runLocationMatch = () => {
    setDetectedPin("");
    if (!("geolocation" in navigator)) { setLocStatus("unavailable"); return; }
    setLocStatus("requesting");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setLocStatus("checking");
        const { latitude, longitude } = pos.coords;
        try {
          // Public Nominatim endpoint — rate-limited to ~1 req/sec (swap for a
          // production geocoding provider before scale).
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
            { headers: { Accept: "application/json" } }
          );
          const data = await res.json();
          const postcode = data?.address?.postcode;
          if (!postcode) { setLocStatus("no_postcode"); return; }
          const detected = normPin(postcode);
          setDetectedPin(detected);
          if (detected && normPin(pincode) && detected === normPin(pincode)) {
            setLocStatus("matched");
            toast.success("Location matches your Aadhaar pincode");
          } else {
            setLocStatus("mismatch");
            setStage("decline_location");
          }
        } catch {
          setLocStatus("no_postcode");
        }
      },
      (err) => {
        if (err.code === 1) setLocStatus("denied");
        else if (err.code === 3) setLocStatus("timeout");
        else setLocStatus("unavailable");
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
  };

  // ---- Liveness handled by the <LivenessCheck> component (camera motion check) ----

  // ---- Auto compliance + completion once all E-KYC parts pass ----
  // The completion timer is stored in a ref and is NEVER cleared by an effect
  // re-run (only on unmount). Previously the effect returned a cleanup that
  // cancelled the timeout as soon as `compliance` flipped to "running" (or on
  // any dep re-run / StrictMode), so finish() never fired and KYC hung on
  // "Running final checks…". A one-shot ref guard starts it exactly once.
  useEffect(() => {
    if (stage !== "ekyc") return;
    if (complianceStartedRef.current) return;
    if (aadhaarVerified && locationOk && liveness === "done") {
      complianceStartedRef.current = true;
      setCompliance("running");
      complianceTimerRef.current = setTimeout(() => { setCompliance("pass"); finish(); }, 1200);
    }
  }, [stage, aadhaarVerified, locationOk, liveness]);

  const finish = () => {
    if (doneRef.current) return;
    doneRef.current = true;
    onVerified?.();
  };

  // ---- Video KYC (fallback) ----
  const startVideoKyc = () => {
    setVideoStage("connecting");
    setTimeout(() => setVideoStage("verifying"), 1600);
    setTimeout(() => {
      setVideoStage("done");
      setCompliance("running");
      setTimeout(() => { setCompliance("pass"); finish(); }, 1000);
    }, 3400);
  };

  const retryLocation = () => { setLocStatus("idle"); setDetectedPin(""); setStage("ekyc"); };

  const ruleLabel = { aadhaar: "Aadhaar", pan: "PAN", profile: "Profile" }[nameMatchRule] || "Aadhaar";

  // ============================ RENDER ============================
  if (stage === "nudge") {
    return (
      <Box className="space-y-4" data-testid="kyc-nudge">
        <Box className="rounded-xl border border-[#5548D1]/25 bg-[#EEF0FF]/40 p-4">
          <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#5548D1]" /> Before we verify</Typography>
          <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-0.5">A few quick confirmations so verification goes through smoothly.</Typography>
        </Box>

        {/* Name match across Profile / PAN / Aadhaar */}
        <Box className="rounded-xl border border-border p-4" data-testid="nudge-name">
          <Box className="flex items-center justify-between">
            <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><User className="h-4 w-4 text-[#5548D1]" /> Confirm your name matches</Typography>
            <MatchBadge ok={nameMatch} />
          </Box>
          <Box className="mt-2 divide-y divide-border">
            <SrcRow label="Profile" value={profileName} />
            <SrcRow label="PAN" value={panName} />
            <Box className="flex items-center justify-between gap-3 py-1.5">
              <Box component="span" className="text-[11px] uppercase tracking-wider text-slate-400 w-20 shrink-0">Aadhaar</Box>
              <Input value={aadhaarName} onChange={(e) => setAadhaarName(e.target.value)} className="h-8 rounded-lg text-sm" data-testid="nudge-aadhaar-name" />
            </Box>
          </Box>
          <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 mt-1.5">Name-match rule: <b>{ruleLabel}</b> is the source of record.</Typography>
        </Box>

        {/* DOB match across PAN / Aadhaar / Profile */}
        <Box className="rounded-xl border border-border p-4" data-testid="nudge-dob">
          <Box className="flex items-center justify-between">
            <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><CalendarDays className="h-4 w-4 text-[#5548D1]" /> Confirm your date of birth matches</Typography>
            <MatchBadge ok={dobMatch} />
          </Box>
          <Box className="mt-2 divide-y divide-border">
            <SrcRow label="Profile" value={profileDob} />
            <SrcRow label="PAN" value={panDob} />
            <Box className="flex items-center justify-between gap-3 py-1.5">
              <Box component="span" className="text-[11px] uppercase tracking-wider text-slate-400 w-20 shrink-0">Aadhaar</Box>
              <Input value={aadhaarDob} onChange={(e) => setAadhaarDob(e.target.value)} placeholder="DD Mon YYYY" className="h-8 rounded-lg text-sm" data-testid="nudge-aadhaar-dob" />
            </Box>
          </Box>
        </Box>

        {/* Location notice */}
        {locationMatchEnabled && (
          <Box className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 flex items-start gap-2.5" data-testid="nudge-location-notice">
            <MapPin className="h-4 w-4 text-amber-700 mt-0.5 shrink-0" />
            <Typography variant="inherit" component="p" className="text-[12.5px] text-amber-900 leading-relaxed">
              Location sharing is required for this bank. Please complete verification from your home so your
              current location matches your <b>Aadhaar-registered pincode</b>.
            </Typography>
          </Box>
        )}

        <Button onClick={continueFromNudge} data-testid="nudge-continue-btn" className="w-full h-11 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
          Continue to verification <ArrowRight className="h-4 w-4 ml-1.5" />
        </Button>
      </Box>
    );
  }

  if (stage === "decline_name" || stage === "decline_dob") {
    const isName = stage === "decline_name";
    return (
      <Box className="rounded-xl border border-red-200 bg-red-50/50 p-5" data-testid={isName ? "decline-name" : "decline-dob"}>
        <Box className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <Typography variant="inherit" component="h3" className="font-head font-black text-lg">{isName ? "Name Mismatch" : "DOB Mismatch"}</Typography>
        </Box>
        <Typography variant="inherit" component="p" className="text-sm text-slate-600 mt-1.5">
          Your {isName ? "name" : "date of birth"} doesn&apos;t match across your Profile, PAN and Aadhaar records.
          Enter the correct {isName ? "name" : "date of birth"} — we&apos;ll update your profile and continue.
        </Typography>
        <Box className="mt-4">
          <Label className="text-sm text-brand-navy">{isName ? "Correct full name" : "Correct date of birth"}</Label>
          {isName ? (
            <Input value={correctName} onChange={(e) => setCorrectName(e.target.value)} className="rounded-lg mt-1.5" data-testid="correct-name-input" />
          ) : (
            <Input value={correctDob} onChange={(e) => setCorrectDob(e.target.value)} placeholder="DD Mon YYYY" className="rounded-lg mt-1.5" data-testid="correct-dob-input" />
          )}
        </Box>
        <Box className="mt-4 flex flex-col sm:flex-row gap-2">
          <Button onClick={isName ? saveNameCorrection : saveDobCorrection} disabled={savingProfile} data-testid="save-correction-btn" className="h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
            {savingProfile ? "Saving..." : "Save & continue"}
          </Button>
          <Button variant="outline" onClick={onExitHome} data-testid="decline-exit-home" className="h-10 rounded-lg border-border text-slate-600 font-semibold">
            Choose another payment option
          </Button>
        </Box>
      </Box>
    );
  }

  if (stage === "decline_location") {
    return (
      <Box className="rounded-xl border border-red-200 bg-red-50/50 p-5" data-testid="decline-location">
        <Box className="flex items-center gap-2 text-red-700">
          <MapPin className="h-5 w-5" />
          <Typography variant="inherit" component="h3" className="font-head font-black text-lg">Location Mismatch</Typography>
        </Box>
        <Typography variant="inherit" component="p" className="text-sm text-slate-600 mt-1.5">
          Your current location doesn&apos;t match your Aadhaar-registered pincode.
        </Typography>
        <Box className="mt-3 grid grid-cols-2 gap-3">
          <Box className="rounded-lg bg-white border border-border p-3">
            <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-wider text-slate-400">Aadhaar pincode</Typography>
            <Typography variant="inherit" component="p" className="text-base font-bold text-brand-navy mt-0.5">{pincode || "—"}</Typography>
          </Box>
          <Box className="rounded-lg bg-white border border-border p-3">
            <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-wider text-slate-400">Detected pincode</Typography>
            <Typography variant="inherit" component="p" className="text-base font-bold text-red-600 mt-0.5" data-testid="detected-pincode">{detectedPin || "—"}</Typography>
          </Box>
        </Box>
        <Box className="mt-4 flex flex-col sm:flex-row gap-2">
          <Button onClick={retryLocation} data-testid="location-retry-btn" className="h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
            <RefreshCw className="h-4 w-4 mr-1.5" /> Retry
          </Button>
          <Button variant="outline" onClick={() => setStage("video")} data-testid="switch-video-kyc-btn" className="h-10 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold">
            <Video className="h-4 w-4 mr-1.5" /> Switch to Video KYC
          </Button>
        </Box>
      </Box>
    );
  }

  if (stage === "video") {
    return (
      <Box className="rounded-xl border border-border p-5" data-testid="video-kyc">
        <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><Video className="h-4 w-4 text-[#5548D1]" /> Video KYC</Typography>
        <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-1">A quick live video verification with an agent. Handles name variations better than E-KYC.</Typography>
        <Box className="mt-4 flex flex-col items-center">
          <Box className="relative h-44 w-full max-w-sm rounded-xl overflow-hidden bg-slate-900 flex items-center justify-center" data-testid="video-frame">
            {videoStage === "done" ? (
              <Box className="flex flex-col items-center text-emerald-400"><CheckCircle2 className="h-12 w-12" /><Typography variant="inherit" component="p" className="text-sm mt-2">Verified by agent</Typography></Box>
            ) : videoStage === "idle" ? (
              <Video className="h-12 w-12 text-slate-600" />
            ) : (
              <Box className="flex flex-col items-center text-white"><Loader2 className="h-10 w-10 animate-spin" /><Typography variant="inherit" component="p" className="text-sm mt-2">{videoStage === "connecting" ? "Connecting to agent…" : "Agent verifying your identity…"}</Typography></Box>
            )}
          </Box>
          {videoStage === "idle" && (
            <Button onClick={startVideoKyc} data-testid="start-video-kyc-btn" className="mt-4 h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
              Start Video KYC
            </Button>
          )}
          {videoStage === "done" && compliance === "pass" && (
            <Box className="mt-4 flex items-center gap-2 text-emerald-600 font-semibold" data-testid="kyc-complete-video">
              <CheckCircle2 className="h-5 w-5" /> Verification complete
            </Box>
          )}
        </Box>
      </Box>
    );
  }

  // stage === "ekyc"
  return (
    <Box className="space-y-4" data-testid="kyc-ekyc">
      <Box className="rounded-xl border border-[#5548D1]/25 bg-[#EEF0FF]/40 p-4 flex items-center justify-between">
        <Box>
          <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><Fingerprint className="h-4 w-4 text-[#5548D1]" /> E-KYC Verification</Typography>
          <Typography variant="inherit" component="p" className="text-xs text-slate-500 mt-0.5">Fastest way to verify. You can switch to Video KYC anytime.</Typography>
        </Box>
        <Button variant="ghost" size="sm" onClick={() => setStage("video")} data-testid="ekyc-switch-video" className="text-[#5548D1] hover:bg-[#EEF0FF] text-xs font-semibold">
          <Video className="h-3.5 w-3.5 mr-1" /> Can&apos;t complete? Video KYC
        </Button>
      </Box>

      {/* Aadhaar */}
      <Box className="rounded-xl border border-border p-4" data-testid="ekyc-aadhaar">
        <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><ScanFace className="h-4 w-4 text-[#5548D1]" /> Aadhaar Verification</Typography>
        <Box component="label" className="flex items-start gap-3 cursor-pointer mt-3">
          <Checkbox checked={aadhaarConsent} onCheckedChange={(v) => setAadhaarConsent(!!v)} className="mt-0.5" data-testid="ekyc-aadhaar-consent" disabled={aadhaarVerified} />
          <Box component="span" className="text-xs text-slate-600 leading-relaxed">I consent to verify my identity via Aadhaar OTP / DigiLocker as per UIDAI guidelines.</Box>
        </Box>
        {aadhaarVerified ? (
          <Box className="mt-3 flex items-center gap-2 text-sm font-semibold text-green-600" data-testid="ekyc-aadhaar-verified"><CheckCircle2 className="h-5 w-5" /> Aadhaar identity verified</Box>
        ) : !otpSent ? (
          <Button variant="outline" onClick={sendOtp} disabled={!aadhaarConsent} data-testid="ekyc-send-otp" className="mt-3 h-10 rounded-lg border-[#5548D1] text-[#5548D1] hover:bg-[#EEF0FF] font-semibold">Send Verification Code</Button>
        ) : (
          <Box className="mt-3 flex items-end gap-2">
            <Box className="flex-1">
              <Label className="text-xs text-brand-navy">Enter OTP</Label>
              <Input value={otp} onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} placeholder="6-digit code" className="rounded-lg mt-1.5" inputMode="numeric" data-testid="ekyc-otp" />
            </Box>
            <Button onClick={verifyOtp} data-testid="ekyc-verify-otp" className="h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">Verify</Button>
          </Box>
        )}
      </Box>

      {/* Location match */}
      {locationMatchEnabled && (
        <Box className="rounded-xl border border-border p-4" data-testid="ekyc-location">
          <Box className="flex items-center justify-between">
            <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><MapPin className="h-4 w-4 text-[#5548D1]" /> Location Match (Aadhaar address)</Typography>
            {locStatus === "matched" && <Box component="span" className="inline-flex items-center gap-1 text-emerald-600 text-xs font-bold"><CheckCircle2 className="h-4 w-4" /> Matched</Box>}
          </Box>
          <Box className="mt-2 text-sm text-brand-navy leading-relaxed">
            {AADHAAR_ADDRESS.line1}, {AADHAAR_ADDRESS.city}, {AADHAAR_ADDRESS.state}
          </Box>
          <Box className="mt-3 flex items-end gap-3">
            <Box className="w-40">
              <Label className="text-xs text-brand-navy">Pincode (editable)</Label>
              <Input value={pincode} onChange={(e) => setPincode(e.target.value.replace(/\D/g, "").slice(0, 6))} className="rounded-lg mt-1.5" inputMode="numeric" data-testid="ekyc-pincode" disabled={locStatus === "matched"} />
            </Box>
            {locStatus !== "matched" && (
              <Button onClick={runLocationMatch} disabled={locStatus === "requesting" || locStatus === "checking"} data-testid="share-location-btn" className="h-10 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
                {locStatus === "requesting" || locStatus === "checking"
                  ? (<><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Locating…</>)
                  : (<><MapPin className="h-4 w-4 mr-1.5" /> Share location & verify</>)}
              </Button>
            )}
          </Box>
          {(locStatus === "denied" || locStatus === "unavailable" || locStatus === "timeout" || locStatus === "no_postcode") && (
            <Box className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 flex items-start gap-2" data-testid="ekyc-location-error">
              <Info className="h-4 w-4 text-amber-700 mt-0.5 shrink-0" />
              <Box className="text-[12.5px] text-amber-900">
                {locStatus === "denied" && (<>Location permission was denied. Please allow location access in your browser and <b>retry</b>.</>)}
                {locStatus === "unavailable" && (<>We couldn&apos;t get your location. Check that location services are on and <b>retry</b>.</>)}
                {locStatus === "timeout" && (<>Getting your location timed out. Please <b>retry</b>.</>)}
                {locStatus === "no_postcode" && (<>No pincode could be determined for your current location. Consider <b>Video KYC</b> instead.</>)}
                <Box className="mt-2 flex gap-2">
                  <Button size="sm" variant="outline" onClick={runLocationMatch} data-testid="ekyc-location-retry" className="h-8 rounded-lg text-xs font-semibold">Retry</Button>
                  <Button size="sm" variant="outline" onClick={() => { setDetectedPin(normPin(pincode)); setLocStatus("matched"); toast.success("Location matched (demo)"); }} data-testid="ekyc-location-simulate" className="h-8 rounded-lg text-xs font-semibold border-[#5548D1] text-[#5548D1]">Use demo location</Button>
                  {locStatus === "no_postcode" && (
                    <Button size="sm" variant="outline" onClick={() => setStage("video")} className="h-8 rounded-lg text-xs font-semibold border-[#5548D1] text-[#5548D1]"><Video className="h-3.5 w-3.5 mr-1" /> Video KYC</Button>
                  )}
                </Box>
              </Box>
            </Box>
          )}
          <Typography variant="inherit" component="p" className="text-[10.5px] text-slate-400 mt-2">Live location + OpenStreetMap Nominatim reverse-geocode. Public endpoint is rate-limited (~1 req/sec) — use a production geocoder before scale.</Typography>
        </Box>
      )}

      {/* Liveness — camera motion-based liveliness check */}
      <Box className="rounded-xl border border-border p-4" data-testid="ekyc-liveness">
        <Typography variant="inherit" component="p" className="font-head font-bold text-brand-navy text-sm flex items-center gap-2"><Camera className="h-4 w-4 text-[#5548D1]" /> Live Photo Check</Typography>
        <LivenessCheck done={liveness === "done"} onPass={() => setLiveness("done")} />
      </Box>

      {/* Compliance + completion (silent — no detail shown) */}
      {compliance === "running" && (
        <Box className="rounded-xl border border-border p-4 flex items-center gap-2 text-slate-600" data-testid="kyc-compliance-running">
          <Loader2 className="h-4 w-4 animate-spin text-[#5548D1]" /> Running final checks…
        </Box>
      )}
      {compliance === "pass" && (
        <Box className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center gap-2 text-emerald-700 font-semibold" data-testid="kyc-complete-ekyc">
          <CheckCircle2 className="h-5 w-5" /> Verification complete
        </Box>
      )}
    </Box>
  );
}


// ===========================================================================
// LivenessCheck — camera-only, on-device motion-based liveliness check.
// The user is asked to perform a random action while the camera is live; a
// static photo held to the camera produces near-zero frame-to-frame motion,
// while a live face performing the action produces a clearly higher score.
// Runs entirely on-device (no external API). A demo fallback lets the flow
// complete on devices without a usable camera.
// ===========================================================================
const CHALLENGES = [
  { name: "Blink twice", hint: "Blink your eyes twice" },
  { name: "Turn head left then center", hint: "Slowly turn your head left, then back to center" },
  { name: "Turn head right then center", hint: "Slowly turn your head right, then back to center" },
  { name: "Smile", hint: "Give a natural smile" },
  { name: "Nod", hint: "Nod your head once" },
];
const MOTION_THRESHOLD = 6;
const CAPTURE_DURATION_MS = 3000;
const SAMPLE_INTERVAL_MS = 150;

function LivenessCheck({ done, onPass }) {
  const [phase, setPhase] = useState("idle"); // idle | live | capturing | pass | fail
  const [status, setStatus] = useState({ kind: "", text: "" });
  const [overlay, setOverlay] = useState("");
  const [progress, setProgress] = useState(0);
  const [camError, setCamError] = useState(false);
  const [detail, setDetail] = useState(null); // { challenge, maxScore, avgScore }

  const videoRef = useRef(null);
  const capturedRef = useRef(null);
  const workRef = useRef(null);
  const streamRef = useRef(null);

  const stopCam = () => {
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch { /* ignore */ }
    streamRef.current = null;
  };
  useEffect(() => () => stopCam(), []);

  const startCamera = async () => {
    setStatus({ kind: "info", text: "Requesting camera access…" });
    setCamError(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 480 }, height: { ideal: 360 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      if (workRef.current) { workRef.current.width = 240; workRef.current.height = 180; }
      setPhase("live");
      setStatus({ kind: "info", text: "Camera live. Position your face in the frame, then begin the check." });
    } catch (err) {
      setCamError(true);
      let msg = "Could not access the camera.";
      if (err?.name === "NotAllowedError") msg = "Camera permission denied — allow access, or use the demo option below.";
      else if (err?.name === "NotFoundError") msg = "No camera found on this device — use the demo option below.";
      setStatus({ kind: "error", text: msg });
    }
  };

  const grabFrame = (ctx, w, h) => {
    ctx.drawImage(videoRef.current, 0, 0, w, h);
    return ctx.getImageData(0, 0, w, h).data;
  };
  const frameDiffScore = (prev, curr) => {
    let total = 0;
    const len = prev.length;
    for (let i = 0; i < len; i += 4) {
      const p = (prev[i] + prev[i + 1] + prev[i + 2]) / 3;
      const c = (curr[i] + curr[i + 1] + curr[i + 2]) / 3;
      total += Math.abs(c - p);
    }
    return total / (len / 4);
  };

  const runChallenge = async () => {
    const work = workRef.current;
    if (!work) return;
    const ctx = work.getContext("2d", { willReadFrequently: true });
    const w = work.width, h = work.height;
    const challenge = CHALLENGES[Math.floor(Math.random() * CHALLENGES.length)];
    setPhase("capturing");
    setOverlay(challenge.hint);
    setProgress(0);
    setDetail(null);
    setStatus({ kind: "info", text: "Capturing — perform the action shown above…" });

    const start = Date.now();
    let prev = grabFrame(ctx, w, h);
    const scores = [];
    let bestScore = -1;
    let bestFrame = null;

    await new Promise((resolve) => {
      const interval = setInterval(() => {
        const elapsed = Date.now() - start;
        setProgress(Math.min(100, (elapsed / CAPTURE_DURATION_MS) * 100));
        const curr = grabFrame(ctx, w, h);
        const score = frameDiffScore(prev, curr);
        scores.push(score);
        if (score > bestScore) {
          bestScore = score;
          const v = videoRef.current;
          const c = document.createElement("canvas");
          c.width = v.videoWidth || 480; c.height = v.videoHeight || 360;
          c.getContext("2d").drawImage(v, 0, 0);
          bestFrame = c;
        }
        prev = curr;
        if (elapsed >= CAPTURE_DURATION_MS) { clearInterval(interval); resolve(); }
      }, SAMPLE_INTERVAL_MS);
    });

    setOverlay("");
    const avgScore = scores.reduce((a, b) => a + b, 0) / (scores.length || 1);
    const maxScore = scores.length ? Math.max(...scores) : 0;
    const passed = maxScore > MOTION_THRESHOLD;
    setDetail({ challenge: challenge.name, maxScore, avgScore });

    if (passed && bestFrame && capturedRef.current) {
      capturedRef.current.width = bestFrame.width;
      capturedRef.current.height = bestFrame.height;
      capturedRef.current.getContext("2d").drawImage(bestFrame, 0, 0);
    }
    stopCam();

    if (passed) {
      setPhase("pass");
      setStatus({ kind: "pass", text: "Liveliness confirmed — captured photo accepted." });
      onPass?.();
    } else {
      setPhase("fail");
      setStatus({ kind: "fail", text: "Could not confirm liveliness (motion too low — possible static photo). Please try again with clearer movement." });
    }
  };

  const retry = () => {
    setPhase("idle"); setStatus({ kind: "", text: "" }); setDetail(null); setProgress(0); setCamError(false);
  };

  const simulate = () => {
    stopCam();
    setPhase("pass");
    setDetail({ challenge: "Simulated (demo)", maxScore: 0, avgScore: 0 });
    setStatus({ kind: "pass", text: "Liveliness simulated for demo — accepted." });
    onPass?.();
  };

  const statusTone = {
    info: "bg-[#EEF0FF] text-[#3F35A8] border-[#5548D1]/20",
    pass: "bg-emerald-50 text-emerald-700 border-emerald-200",
    fail: "bg-red-50 text-red-700 border-red-200",
    error: "bg-amber-50 text-amber-800 border-amber-200",
  }[status.kind] || "";

  const passed = done || phase === "pass";

  return (
    <Box className="mt-3">
      <Box className="relative mx-auto w-full max-w-[320px] aspect-[4/3] rounded-xl overflow-hidden bg-slate-900 flex items-center justify-center">
        <video ref={videoRef} autoPlay playsInline muted
          className={`h-full w-full object-cover ${phase === "live" || phase === "capturing" ? "block" : "hidden"}`} />
        <canvas ref={capturedRef} className={`h-full w-full object-cover ${passed ? "block" : "hidden"}`} />
        {!passed && phase !== "live" && phase !== "capturing" && (
          <ScanFace className="h-14 w-14 text-slate-600" />
        )}
        {overlay && (
          <Box className="absolute top-0 left-0 right-0 px-4 py-3 text-center text-white text-sm font-semibold bg-gradient-to-b from-black/60 to-transparent" data-testid="liveness-overlay">
            {overlay}
          </Box>
        )}
        {phase === "capturing" && (
          <Box className="absolute bottom-0 left-0 right-0 h-1.5 bg-white/25">
            <Box className="h-full bg-[#5548D1] transition-all" style={{ width: `${progress}%` }} />
          </Box>
        )}
        {passed && (
          <Box className="absolute top-2 right-2 h-8 w-8 rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-lg">
            <CheckCircle2 className="h-5 w-5" />
          </Box>
        )}
      </Box>
      <canvas ref={workRef} className="hidden" />

      {!passed && (
        <Box className="mt-3 flex flex-wrap justify-center gap-2">
          {phase === "idle" && (
            <Button onClick={startCamera} data-testid="liveness-start" className="h-9 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
              <Camera className="h-4 w-4 mr-1.5" /> Start camera
            </Button>
          )}
          {phase === "live" && (
            <Button onClick={runChallenge} data-testid="liveness-begin" className="h-9 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
              <ScanFace className="h-4 w-4 mr-1.5" /> Begin liveliness check
            </Button>
          )}
          {phase === "fail" && (
            <Button onClick={retry} variant="outline" data-testid="liveness-retry" className="h-9 rounded-lg border-border text-slate-600 font-semibold">
              <RefreshCw className="h-4 w-4 mr-1.5" /> Try again
            </Button>
          )}
          {/* Demo fallback — always available so the flow never dead-ends without a camera */}
          {(phase === "idle" || phase === "fail" || camError) && (
            <Button onClick={simulate} variant="outline" data-testid="liveness-simulate" className="h-9 rounded-lg border-[#5548D1] text-[#5548D1] font-semibold">
              Use simulated liveliness (demo)
            </Button>
          )}
        </Box>
      )}

      {status.text && (
        <Box className={`mt-3 rounded-lg border px-3 py-2 text-[12.5px] leading-relaxed ${statusTone}`} data-testid="liveness-status">
          {status.text}
        </Box>
      )}

      {detail && (
        <Box className="mt-2 text-[11px] text-slate-400 text-center" data-testid="liveness-detail">
          Challenge: {detail.challenge} · Motion {detail.maxScore.toFixed(1)} (threshold &gt; {MOTION_THRESHOLD})
        </Box>
      )}
    </Box>
  );
}
