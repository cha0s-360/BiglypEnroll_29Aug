'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useMemo, useState } from "react";
import { useRouter } from 'next/navigation';
import { ParentLayout } from "@/components/ParentLayout";
import api, { inr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import {
  Wallet, CheckCircle2, CreditCard, ShieldCheck, Download, Calendar,
  GraduationCap, Zap, Bus, Plane, ArrowRight, Sparkles, Star, RefreshCw,
  UtensilsCrossed, Shirt, Trophy, Music, MapPin, Check, FileText, IdCard,
} from "lucide-react";
import { FinancingWizard } from "./FinancingWizard";

const MODES = ["UPI", "Cards", "Net Banking", "Wallets", "AutoPay/eNACH"];
const ADDON_KEYWORDS = ["transport", "bus", "trip", "excursion", "meal", "uniform", "activity", "field", "sport", "music", "arts", "club"];
const isAddon = (name = "") => ADDON_KEYWORDS.some((k) => name.toLowerCase().includes(k));

const addonMeta = (name = "") => {
  const n = name.toLowerCase();
  if (n.includes("transport") || n.includes("bus")) return { Icon: Bus, tint: "#EEF0FF", fg: "#5548D1" };
  if (n.includes("meal") || n.includes("cafeter")) return { Icon: UtensilsCrossed, tint: "#FEF3C7", fg: "#B45309" };
  if (n.includes("uniform")) return { Icon: Shirt, tint: "#E0F2FE", fg: "#0369A1" };
  if (n.includes("sport") || n.includes("activity")) return { Icon: Trophy, tint: "#DCFCE7", fg: "#166534" };
  if (n.includes("music") || n.includes("arts") || n.includes("club")) return { Icon: Music, tint: "#FCE7F3", fg: "#BE185D" };
  if (n.includes("field") || n.includes("trip") || n.includes("excursion")) return { Icon: MapPin, tint: "#F1F5F9", fg: "#334155" };
  return { Icon: Plane, tint: "#EEF0FF", fg: "#5548D1" };
};

export default function ParentDashboard() {
  const router = useRouter();
  const [children, setChildren] = useState([]);
  const [activeChild, setActiveChild] = useState(null);
  const [feeData, setFeeData] = useState(null);

  // academic payment option selection: 'a' (EMI) | 'b' (auto-debit) | 'c' (full)
  const [selectedOption, setSelectedOption] = useState(null);
  const [autoFreq, setAutoFreq] = useState("quarterly"); // quarterly | semi
  const [clubbed, setClubbed] = useState([]); // quarterly "other fee" ids clubbed with tuition

  // pay dialog
  const [payOpen, setPayOpen] = useState(false);
  const [payHeadIds, setPayHeadIds] = useState([]);
  const [mode, setMode] = useState("UPI");
  const [processing, setProcessing] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [wallet, setWallet] = useState(0);
  const [useWallet, setUseWallet] = useState(false);

  // financing wizard
  const [finOpen, setFinOpen] = useState(false);
  const [finHeadIds, setFinHeadIds] = useState([]);
  const [finAmount, setFinAmount] = useState(0);

  useEffect(() => {
    api.get("/parent/children").then(({ data }) => {
      setChildren(data);
      if (data[0]) setActiveChild(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!activeChild) return;
    setClubbed([]);
    api.get(`/parent/fees/${activeChild}`).then(({ data }) => setFeeData(data));
  }, [activeChild]);

  const child = children.find((c) => c.id === activeChild);
  const items = feeData?.items || [];
  const pending = items.filter((i) => !i.paid);

  const isOneTime = (f = "") => /one.?time/i.test(f);
  const isQuarterly = (f = "") => /quarter/i.test(f);

  const academicPending = pending.filter((i) => !isAddon(i.name));
  const otherPending = pending.filter((i) => isAddon(i.name));
  const pendingGrandTotal = pending.reduce((a, i) => a + i.amount, 0);

  // "Other fees" that are quarterly can be clubbed with tuition and paid on the academic plan
  const clubbedItems = otherPending.filter((i) => clubbed.includes(i.fee_head_id));

  // One-time academic fees must be paid in full (no EMI / auto-debit)
  const academicOneTime = academicPending.filter((i) => isOneTime(i.frequency));
  const academicRecurring = academicPending.filter((i) => !isOneTime(i.frequency));

  const academicItems = [...academicPending, ...clubbedItems];          // full breakup
  const academicTotal = academicItems.reduce((a, i) => a + i.amount, 0); // full total
  const fullIds = academicItems.map((i) => i.fee_head_id);

  // installment plans (semi / quarterly / monthly) exclude one-time fees
  const installItems = [...academicRecurring, ...clubbedItems];
  const installTotal = installItems.reduce((a, i) => a + i.amount, 0);
  const installIds = installItems.map((i) => i.fee_head_id);

  const hasOneTimeInAcademic = academicOneTime.length > 0;

  const toggleClub = (id) =>
    setClubbed((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  // installment amounts
  const emiAmount = Math.ceil(installTotal / 12);
  const quarterlyAmount = Math.round(installTotal / 4);
  const semiAmount = Math.round(installTotal / 2);
  const autoAmount = autoFreq === "semi" ? semiAmount : quarterlyAmount;

  // school-enabled payment options (Option A / B / C)
  const paymentOptions = feeData?.payment_options || { emi: true, auto_debit: true, full: true };
  const optionDefs = useMemo(() => ([
    {
      key: "a", flag: "emi",
      title: "Pay full-year fees in EMIs",
      subtitle: "Small, convenient monthly payments",
      amount: emiAmount, unit: "/ month", primary: true,
      badge: { text: "0% Interest", tone: "green" },
    },
    {
      key: "b", flag: "auto_debit",
      title: "Set up Auto-Debit",
      subtitle: "Quarterly or Half-Yearly e-mandate",
      amount: autoAmount, unit: autoFreq === "semi" ? "/ term" : "/ quarter",
      badge: { text: "No late fees", tone: "blue" },
    },
    {
      key: "c", flag: "full",
      title: "Pay full year upfront",
      subtitle: "UPI, Credit/Debit Card or Net Banking",
      amount: academicTotal, unit: "today",
      badge: { text: "Instant", tone: "slate" },
    },
  ]), [emiAmount, autoAmount, autoFreq, academicTotal]);

  const enabledOptions = optionDefs.filter((o) => paymentOptions[o.flag]);

  // default the selected option to the first enabled one when fees load
  useEffect(() => {
    if (!feeData) return;
    const po = feeData.payment_options || { emi: true, auto_debit: true, full: true };
    const order = [["a", "emi"], ["b", "auto_debit"], ["c", "full"]];
    const firstEnabled = order.find(([, f]) => po[f]);
    setSelectedOption(firstEnabled ? firstEnabled[0] : null);
  }, [feeData]);

  const dueDate = useMemo(() => {
    const yr = (feeData?.academic_year || "2026-27").slice(0, 4);
    return `15th September ${yr}`;
  }, [feeData]);

  const refresh = () => api.get(`/parent/fees/${activeChild}`).then(({ data }) => setFeeData(data));

  // reward wallet balance (auto-applies to fee payments)
  const loadWallet = () => api.get("/parent/rewards").then(({ data }) => setWallet(data.wallet || 0)).catch(() => {});
  useEffect(() => { loadWallet(); }, [activeChild]);

  // ---------- payment ----------
  const payItems = pending.filter((i) => payHeadIds.includes(i.fee_head_id));
  const payTotal = payItems.reduce((a, i) => a + i.amount, 0);
  const payGst = Math.round(payTotal * 0.18);
  const payGross = payTotal + payGst;
  const walletApplied = useWallet ? Math.min(wallet, payGross) : 0;
  const finalPayable = payGross - walletApplied;
  const payHasOneTime = payItems.some((i) => isOneTime(i.frequency));
  const availableModes = payHasOneTime ? MODES.filter((m) => m !== "AutoPay/eNACH") : MODES;

  const startPay = (headIds) => {
    if (!headIds.length) return;
    setPayHeadIds(headIds);
    setMode("UPI");
    setUseWallet(false);
    setPayOpen(true);
  };

  const pay = async () => {
    setProcessing(true);
    try {
      const { data } = await api.post("/parent/pay", { student_id: activeChild, fee_head_ids: payHeadIds, mode, use_wallet: useWallet });
      setReceipt(data);
      setPayOpen(false);
      refresh();
      loadWallet();
      const re = data.rewards_earned;
      if (re && (re.points || re.wallet)) {
        toast.success(`Payment successful — earned ${re.points} points${re.wallet ? ` + ${inr(re.wallet)} cashback` : ""}!`);
      } else {
        toast.success("Payment successful");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Payment failed");
    } finally {
      setProcessing(false);
    }
  };

  // ---------- financing (5-step wizard) ----------
  const startFinancing = (headIds) => {
    if (!headIds.length) return;
    const amt = pending.filter((i) => headIds.includes(i.fee_head_id)).reduce((a, i) => a + i.amount, 0);
    setFinHeadIds(headIds);
    setFinAmount(amt);
    setFinOpen(true);
  };

  const onFinancingSuccess = (data) => {
    // The wizard now shows its own "You're all set!" summary (step 6),
    // so we just refresh dashboard data in the background.
    refresh();
  };


  const proceedAcademic = () => {
    if (selectedOption === "c") { startPay(fullIds); return; }
    if (selectedOption === "a") { startFinancing(installIds); return; }
    // option b -> auto-debit mandate setup (one-time fees excluded)
    sessionStorage.setItem("biglyp_mandate_state", JSON.stringify({
      studentId: activeChild,
      studentName: child?.name,
      feeHeadIds: installIds,
      academicTotal: installTotal,
      frequency: autoFreq === "semi" ? "semi" : "quarterly",
    }));
    router.push("/app/mandate");
  };

  return (
    <ParentLayout>
      {/* ===== Hero band: greeting + totals + child selector ===== */}
      <Box className="relative overflow-hidden rounded-3xl hero-gradient text-white mb-6 reveal">
        <Box className="absolute inset-0 hero-dots opacity-60 pointer-events-none" />
        <Box className="absolute -top-24 -right-16 h-72 w-72 rounded-full bg-[#7C6FF5]/30 blur-3xl pointer-events-none" />
        <Box className="relative z-10 p-6 md:p-8 flex flex-wrap items-end justify-between gap-6">
          <Box className="min-w-0">
            <Box className="inline-flex items-center gap-1.5 rounded-full bg-white/10 border border-white/15 px-3 py-1 text-[10px] uppercase tracking-[0.22em] font-bold text-white/80">
              <Sparkles className="h-3 w-3" /> Fee Payment
            </Box>
            <Typography variant="inherit" component="h1" className="font-head text-3xl md:text-4xl font-black tracking-tight mt-3">
              {child ? `${child.name.split(" ")[0]}'s Fees` : "Fee Payment"}
            </Typography>
            {child && (
              <Box className="mt-2 flex items-center gap-2 flex-wrap">
                <Box component="span" className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-white/90">
                  <GraduationCap className="h-3.5 w-3.5" /> {child.grade}
                </Box>
                <Box component="span" className="inline-flex items-center rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-white/90">
                  AY {feeData?.academic_year}
                </Box>
                {wallet > 0 && (
                  <Box component="span" className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/20 border border-emerald-300/20 px-2.5 py-1 text-xs font-bold text-emerald-200">
                    <Wallet className="h-3.5 w-3.5" /> {inr(wallet)} cashback wallet
                  </Box>
                )}
              </Box>
            )}
          </Box>

          <Box className="flex items-end gap-6 md:gap-10 flex-wrap">
            {child && pendingGrandTotal > 0 && (
              <Box>
                <Typography variant="inherit" component="p" className="text-[10px] uppercase tracking-[0.2em] font-bold text-white/60">Total pending</Typography>
                <Typography variant="inherit" component="p" className="font-head text-3xl md:text-[34px] font-black tracking-tight mt-0.5">{inr(pendingGrandTotal)}</Typography>
                <Typography variant="inherit" component="p" className="text-xs text-white/70 mt-1 flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" /> Due {dueDate}
                </Typography>
              </Box>
            )}
            {children.length > 1 && (
              <Select value={activeChild || ""} onValueChange={setActiveChild}>
                <SelectTrigger className="w-56 h-10 rounded-xl bg-white/10 border-white/20 text-white font-semibold backdrop-blur hover:bg-white/15 transition-colors [&>svg]:text-white/70" data-testid="child-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {children.map((c) => <SelectItem key={c.id} value={c.id}>{c.name} · {c.grade}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
          </Box>
        </Box>
      </Box>

      {/* Payment-option selector (Option A / B / C — school-configurable) */}
      {child && academicTotal > 0 && enabledOptions.length > 0 && (
        <Box className="mb-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="option-cards">
          {enabledOptions.map((o, idx) => {
            const active = selectedOption === o.key;
            const displayLetter = String.fromCharCode(65 + idx); // sequential A, B, C — no gaps
            const badgeTone = {
              green: "bg-emerald-100 text-emerald-700",
              blue: "bg-[#EEF0FF] text-[#5548D1]",
              slate: "bg-slate-100 text-slate-500",
            }[o.badge.tone] || "bg-slate-100 text-slate-500";
            return (
              <Box component="button"
                key={o.key}
                data-testid={`option-${o.key}`}
                onClick={() => setSelectedOption(o.key)}
                className={`card-lift reveal-${idx + 1} relative text-left rounded-2xl border-2 p-5 ${
                  active
                    ? "border-[#5548D1] bg-gradient-to-br from-[#EEF0FF] to-white soft-shadow-lg"
                    : "border-transparent bg-white soft-shadow hover:border-[#5548D1]/30"
                }`}
              >
                {/* selected check */}
                <Box component="span" className={`absolute top-4 right-4 h-6 w-6 rounded-full flex items-center justify-center transition-all duration-300 ${
                  active ? "bg-[#5548D1] text-white scale-100 opacity-100" : "bg-slate-100 text-transparent scale-75 opacity-0"
                }`}>
                  <Check className="h-3.5 w-3.5" strokeWidth={3} />
                </Box>

                <Box className="flex items-center gap-2">
                  <Box component="span" className={`h-7 w-7 rounded-lg flex items-center justify-center text-[11px] font-black transition-colors ${
                    active ? "bg-[#5548D1] text-white" : "bg-[#EEF0FF] text-[#5548D1]"
                  }`}>
                    {displayLetter}
                  </Box>
                  <Box component="span" className={`rounded-full text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 leading-tight ${badgeTone}`}>
                    {o.badge.text}
                  </Box>
                </Box>

                <Typography variant="inherit" component="p" className="font-head text-[19px] font-black tracking-tight leading-snug text-brand-navy mt-3">
                  {o.title}
                </Typography>
                <Typography variant="inherit" component="p" className="text-[12.5px] text-slate-500 mt-1">{o.subtitle}</Typography>

                <Box className="mt-4 flex items-baseline gap-1.5">
                  <Box component="span" className={`font-head text-3xl font-black tracking-tight ${o.primary || active ? "text-[#5548D1]" : "text-brand-navy"}`}>
                    {inr(o.amount)}
                  </Box>
                  <Box component="span" className="text-xs font-semibold text-slate-400">{o.unit}</Box>
                </Box>
              </Box>
            );
          })}
        </Box>
      )}

      {children.length === 0 && (
        <Box className="bg-white border border-border rounded-2xl p-12 text-center">
          <GraduationCap className="h-10 w-10 text-[#5548D1] mx-auto" />
          <Typography variant="inherit" component="p" className="mt-4 font-head font-bold text-brand-navy text-lg">No students linked yet</Typography>
          <Typography variant="inherit" component="p" className="text-sm text-slate-500 mt-1">Ask your school to link your child to this email.</Typography>
        </Box>
      )}

      {child && (
        <Box className="space-y-10">
          {/* ============ Section 1: Academic Fee Dues (compact) ============ */}
          <Box component="section">
            <Box className="flex items-center gap-2.5">
              <Box className="h-8 w-8 rounded-xl bg-[#EEF0FF] text-[#5548D1] flex items-center justify-center">
                <GraduationCap className="h-4 w-4" />
              </Box>
              <Box>
                <Typography variant="inherit" component="h2" className="font-head text-xl font-bold text-brand-navy leading-tight">Academic Fee Dues</Typography>
                <Typography variant="inherit" component="p" className="text-sm text-slate-500">Your core tuition &amp; academic charges for the year.</Typography>
              </Box>
            </Box>

            {academicTotal > 0 ? (
              <Box className="reveal-2 mt-4 bg-white border border-border/70 rounded-2xl p-5 md:p-6 soft-shadow" data-testid="academic-card">
                {/* total + due date */}
                <Box className="flex flex-wrap items-start justify-between gap-3">
                  <Box>
                    <Box className="flex items-center gap-2">
                      <Box component="span" className="text-xs uppercase tracking-[0.14em] text-slate-500 font-semibold">Total dues</Box>
                      <Box component="span" className="inline-flex items-center rounded-full bg-[#FEF3C7] text-[#92400E] text-[10px] font-semibold px-2 py-0.5" data-testid="status-badge">Pending Collection</Box>
                    </Box>
                    <Typography variant="inherit" component="p" className="font-head text-3xl font-black text-brand-navy mt-1">{inr(academicTotal)}</Typography>
                  </Box>
                  <Box component="span" className="inline-flex items-center gap-1.5 text-sm text-slate-500">
                    <Calendar className="h-4 w-4" /> Due {dueDate}
                  </Box>
                </Box>

                {/* breakup */}
                <Box className="mt-4 rounded-xl border border-border/80 divide-y divide-border/70 overflow-hidden" data-testid="academic-breakup">
                  {academicItems.map((i) => (
                    <Box key={i.fee_head_id} className="row-hover flex items-center justify-between px-4 py-2.5 text-sm">
                      <Box component="span" className="text-slate-600 flex items-center gap-2">
                        {i.name}
                        {clubbed.includes(i.fee_head_id) && <Box component="span" className="text-[10px] font-semibold text-[#5548D1] bg-[#EEF0FF] rounded-full px-1.5 py-0.5">clubbed</Box>}
                        {isOneTime(i.frequency) && <Box component="span" className="text-[10px] font-semibold text-amber-700 bg-amber-100 rounded-full px-1.5 py-0.5">one-time</Box>}
                      </Box>
                      <Box component="span" className="font-bold text-brand-navy tabular-nums">{inr(i.amount)}</Box>
                    </Box>
                  ))}
                </Box>

                {/* Choose how to pay — only for Auto-Debit (Option B): Quarterly / Half-Yearly */}
                {selectedOption === "b" && (
                  <>
                    <Typography variant="inherit" component="p" className="mt-5 text-xs uppercase tracking-[0.14em] text-slate-500 font-semibold">Choose how to pay</Typography>
                    <Box className="mt-2 grid grid-cols-2 gap-2" data-testid="autofreq-bar">
                      {[
                        { key: "quarterly", label: "Quarterly", amount: quarterlyAmount, unit: "/qtr" },
                        { key: "semi", label: "Half-Yearly", amount: semiAmount, unit: "/term" },
                      ].map((o) => {
                        const active = autoFreq === o.key;
                        return (
                          <Box component="button" key={o.key} data-testid={`autofreq-${o.key}`} onClick={() => setAutoFreq(o.key)}
                            className={`text-left rounded-xl border px-3 py-2.5 transition-colors ${
                              active ? "border-[#5548D1] bg-[#EEF0FF] ring-1 ring-[#5548D1]" : "border-border bg-white hover:border-[#5548D1]/40"
                            }`}>
                            <Box component="span" className="text-xs font-semibold text-brand-navy">{o.label}</Box>
                            <Box className="mt-1 flex items-baseline gap-1">
                              <Box component="span" className="font-head text-lg font-black text-brand-navy">{inr(o.amount)}</Box>
                              <Box component="span" className="text-[10px] text-slate-400">{o.unit}</Box>
                            </Box>
                          </Box>
                        );
                      })}
                    </Box>
                  </>
                )}

                {selectedOption === "a" && (
                  <Box className="mt-4 flex items-start gap-2.5 rounded-xl bg-[#EEF0FF] border border-[#5548D1]/15 p-3" data-testid="emi-callout">
                    <Zap className="h-4 w-4 text-[#5548D1] shrink-0 mt-0.5" />
                    <Typography variant="inherit" component="p" className="text-xs text-brand-navy leading-relaxed">Convert bulky academic fees into zero-interest monthly EMIs. School is paid 100% upfront.</Typography>
                  </Box>
                )}

                {/* Documents required for the 0% EMI application (Option A only) */}
                {selectedOption === "a" && (
                  <Box className="mt-3 rounded-xl border border-border bg-white p-4" data-testid="emi-requirements">
                    <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-[0.14em] text-slate-500 font-bold flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5 text-[#5548D1]" /> What you&apos;ll need
                    </Typography>
                    <Box className="mt-3 flex items-start gap-2.5">
                      <Box className="h-7 w-7 rounded-lg bg-[#EEF0FF] flex items-center justify-center shrink-0"><IdCard className="h-4 w-4 text-[#5548D1]" /></Box>
                      <Box>
                        <Typography variant="inherit" component="p" className="text-xs font-semibold text-brand-navy">Basic requirements</Typography>
                        <Typography variant="inherit" component="p" className="text-[11.5px] text-slate-500 mt-0.5">PAN &amp; Aadhaar of the applicant (parent / guardian).</Typography>
                      </Box>
                    </Box>

                    {academicTotal > 300000 && (
                      <Box className="mt-3 rounded-lg bg-amber-50 border border-amber-200 p-3" data-testid="emi-requirements-docs">
                        <Typography variant="inherit" component="p" className="text-[11px] font-bold text-amber-800 uppercase tracking-wider">
                          Additional requirement for financing above {inr(300000)}
                        </Typography>
                        <Box className="mt-2 space-y-1.5 text-[11.5px] text-amber-900">
                          <Box className="flex items-start gap-1.5"><Box component="span" className="font-semibold min-w-[92px]">Salaried:</Box><Box component="span">3 months salary slips + 3 months bank statement</Box></Box>
                          <Box className="flex items-start gap-1.5"><Box component="span" className="font-semibold min-w-[92px]">Self-employed:</Box><Box component="span">2 years ITR + 6 months bank statement</Box></Box>
                        </Box>
                      </Box>
                    )}
                  </Box>
                )}

                {selectedOption === "b" && hasOneTimeInAcademic && (
                  <Box className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-amber-50 border border-amber-200 p-3" data-testid="onetime-note">
                    <Typography variant="inherit" component="p" className="text-xs text-amber-800 leading-relaxed">
                      One-time fees ({academicOneTime.map((i) => i.name).join(", ")}) can&apos;t be auto-debited — pay them in full separately.
                    </Typography>
                    <Button onClick={() => startPay(academicOneTime.map((i) => i.fee_head_id))} data-testid="pay-onetime-btn"
                      variant="outline" className="h-8 rounded-lg border-amber-400 text-amber-800 hover:bg-amber-100 font-semibold text-xs">
                      Pay one-time now
                    </Button>
                  </Box>
                )}

                <Button onClick={proceedAcademic} disabled={!selectedOption} data-testid="proceed-breakdown-btn"
                  className="mt-5 h-11 px-6 rounded-xl bg-gradient-to-r from-[#5548D1] to-[#6E5FEA] hover:from-[#3F35A8] hover:to-[#5548D1] text-white font-semibold shadow-[0_10px_24px_-10px_rgba(85,72,209,0.7)] transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0">
                  {selectedOption === "a" ? "Start 0% EMI Application" : selectedOption === "c" ? "Pay Full Amount" : "Set Up Auto-Debit Plan"}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>

                {feeData?.scholarships?.length > 0 && (
                  <Box className="mt-4 flex items-start gap-2 text-[11px] text-slate-500">
                    <Sparkles className="h-3.5 w-3.5 text-[#5548D1] shrink-0 mt-0.5" />
                    <Box component="span">Scholarships available: {feeData.scholarships.map((s) => `${s.name} (${s.type === "percentage" ? s.value + "%" : inr(s.value)})`).join(" · ")}.</Box>
                  </Box>
                )}
              </Box>
            ) : (
              <Box className="mt-4 bg-white border border-border rounded-2xl p-8 text-center">
                <CheckCircle2 className="h-8 w-8 text-green-600 mx-auto" />
                <Typography variant="inherit" component="p" className="mt-3 font-semibold text-brand-navy">All academic dues cleared</Typography>
                <Typography variant="inherit" component="p" className="text-sm text-slate-500 mt-1">No pending core academic fees for this year.</Typography>
              </Box>
            )}
          </Box>

          {/* ============ Section 2: Other Fees ============ */}
          <Box component="section">
            <Box className="flex flex-wrap items-end justify-between gap-3">
              <Box className="flex items-center gap-2.5">
                <Box className="h-8 w-8 rounded-xl bg-[#EEF0FF] text-[#5548D1] flex items-center justify-center">
                  <Wallet className="h-4 w-4" />
                </Box>
                <Box>
                  <Typography variant="inherit" component="h2" className="font-head text-xl font-bold text-brand-navy leading-tight">Other Fees</Typography>
                  <Typography variant="inherit" component="p" className="text-sm text-slate-500">Transport, activities &amp; one-time collections. Quarterly items can be clubbed with tuition.</Typography>
                </Box>
              </Box>
              {otherPending.length > 0 && (
                <Box component="span" className="inline-flex items-center gap-1.5 rounded-full bg-[#EEF0FF] text-[#5548D1] px-2.5 py-1 text-[11px] font-bold">
                  {otherPending.length} pending
                </Box>
              )}
            </Box>

            {otherPending.length > 0 ? (
              <Box className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {otherPending.map((i, idx) => {
                  const { Icon, tint, fg } = addonMeta(i.name);
                  const quarterly = isQuarterly(i.frequency);
                  const oneTime = isOneTime(i.frequency);
                  const isClubbed = clubbed.includes(i.fee_head_id);
                  return (
                    <Box key={i.fee_head_id}
                      className={`card-lift reveal-${Math.min(idx + 1, 5)} relative bg-white rounded-2xl p-4 flex flex-col soft-shadow border-2 ${isClubbed ? "border-[#5548D1]" : "border-transparent"}`}
                      data-testid={`addon-${i.fee_head_id}`}>
                      <Box className="flex items-start gap-2.5">
                        <Box className="h-9 w-9 rounded-lg flex items-center justify-center shrink-0"
                          style={{ background: tint, color: fg }}>
                          <Icon className="h-4.5 w-4.5" />
                        </Box>
                        <Box className="min-w-0 flex-1">
                          <Typography variant="inherit" component="p" className="font-head font-bold text-[13.5px] text-brand-navy truncate leading-tight">{i.name}</Typography>
                          <Box className="mt-0.5 flex items-center gap-1.5 flex-wrap">
                            <Box component="span" className="text-[10.5px] text-slate-500">{i.frequency}</Box>
                            {oneTime && (
                              <Box component="span" className="text-[9px] font-bold text-amber-700 bg-amber-100 rounded-full px-1.5 py-0.5 uppercase tracking-wider">One-Time</Box>
                            )}
                          </Box>
                        </Box>
                      </Box>

                      <Box className="mt-3 flex items-baseline justify-between">
                        <Box component="span" className="font-head text-xl font-black text-brand-navy leading-none">{inr(i.amount)}</Box>
                        {isClubbed && (
                          <Box component="span" className="inline-flex items-center gap-1 text-[10px] font-bold text-[#5548D1]"><CheckCircle2 className="h-3 w-3" /> Clubbed</Box>
                        )}
                      </Box>

                      {quarterly && !isClubbed && (
                        <Box component="label" className="mt-2.5 flex items-center gap-2 cursor-pointer rounded-md bg-[#EEF0FF]/60 px-2 py-1.5"
                          data-testid={`club-label-${i.fee_head_id}`}>
                          <Checkbox checked={isClubbed} onCheckedChange={() => toggleClub(i.fee_head_id)}
                            data-testid={`club-${i.fee_head_id}`} className="h-3.5 w-3.5" />
                          <Box component="span" className="text-[10.5px] text-brand-navy font-medium leading-tight">Club with tuition plan</Box>
                        </Box>
                      )}

                      {!isClubbed && (
                        <Button onClick={() => startPay([i.fee_head_id])} data-testid={`pay-upfront-${i.fee_head_id}`}
                          className="mt-2.5 h-8 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] text-white font-semibold text-[11.5px] px-3 self-start transition-all duration-300 hover:-translate-y-0.5 shadow-[0_6px_14px_-8px_rgba(85,72,209,0.7)]">
                          Pay Upfront <ArrowRight className="h-3 w-3 ml-1" />
                        </Button>
                      )}
                    </Box>
                  );
                })}
              </Box>
            ) : (
              <Box className="mt-4 bg-white border border-border rounded-2xl p-8 text-center">
                <Wallet className="h-8 w-8 text-slate-300 mx-auto" />
                <Typography variant="inherit" component="p" className="mt-3 text-sm text-slate-500">No other fees pending.</Typography>
              </Box>
            )}
          </Box>
        </Box>
      )}

      {/* Pay dialog */}
      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent className="rounded-2xl">
          <DialogHeader><DialogTitle className="font-head">Fee breakdown</DialogTitle></DialogHeader>
          <Box className="space-y-3 py-1">
            <Box className="rounded-xl border border-border divide-y divide-border">
              {payItems.map((i) => (
                <Box key={i.fee_head_id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <Box component="span" className="text-slate-600">{i.name}</Box>
                  <Box component="span" className="font-semibold text-brand-navy">{inr(i.amount)}</Box>
                </Box>
              ))}
              <Box className="flex items-center justify-between px-4 py-2.5 text-sm">
                <Box component="span" className="text-slate-500">GST (18%)</Box>
                <Box component="span" className="text-slate-600">{inr(payGst)}</Box>
              </Box>
              <Box className="flex items-center justify-between px-4 py-3 bg-[#F8FAFC]">
                <Box component="span" className="font-head font-bold text-brand-navy">Total payable</Box>
                <Box component="span" className="font-head font-black text-brand-navy text-lg">{inr(payGross)}</Box>
              </Box>
              {useWallet && walletApplied > 0 && (
                <Box className="flex items-center justify-between px-4 py-2.5 text-sm bg-emerald-50">
                  <Box component="span" className="text-emerald-700 font-medium">Cashback wallet applied</Box>
                  <Box component="span" className="font-semibold text-emerald-700">-{inr(walletApplied)}</Box>
                </Box>
              )}
            </Box>
            {wallet > 0 && (
              <Box component="button" type="button" onClick={() => setUseWallet((v) => !v)} data-testid="use-wallet-toggle"
                className={`w-full flex items-center justify-between rounded-lg border-2 px-4 py-3 transition-colors ${
                  useWallet ? "border-emerald-500 bg-emerald-50" : "border-border bg-white hover:border-emerald-300"
                }`}>
                <Box component="span" className="flex items-center gap-2 text-sm font-semibold text-brand-navy">
                  <Wallet className="h-4 w-4 text-emerald-600" /> Use cashback wallet
                  <Box component="span" className="text-xs font-normal text-slate-500">({inr(wallet)} available)</Box>
                </Box>
                <Box component="span" className={`h-5 w-5 rounded-md border-2 flex items-center justify-center ${useWallet ? "border-emerald-500 bg-emerald-500 text-white" : "border-slate-300"}`}>
                  {useWallet && <Check className="h-3.5 w-3.5" />}
                </Box>
              </Box>
            )}
            <Select value={availableModes.includes(mode) ? mode : availableModes[0]} onValueChange={setMode}>
              <SelectTrigger className="rounded-lg" data-testid="mode-select"><SelectValue /></SelectTrigger>
              <SelectContent>{availableModes.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
            </Select>
            {payHasOneTime && (
              <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 px-1">One-time fees must be paid in full — AutoPay / eNACH is not available.</Typography>
            )}
            <Box className="bg-slate-50 rounded-lg p-3 text-xs text-slate-500 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[#5548D1]" /> Simulated gateway — no real charge is made.
            </Box>
            <Button onClick={pay} disabled={processing} data-testid="confirm-pay-btn"
              className="w-full h-11 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold">
              <CreditCard className="h-4 w-4 mr-2" />
              {processing ? "Processing..." : `Pay ${inr(finalPayable)}`}
            </Button>
          </Box>
        </DialogContent>
      </Dialog>

      {/* Financing wizard (5-step) */}
      <FinancingWizard
        open={finOpen}
        onOpenChange={setFinOpen}
        studentId={activeChild}
        studentName={child?.name}
        studentGrade={child?.grade}
        feeHeadIds={finHeadIds}
        academicTotal={finAmount}
        onSuccess={onFinancingSuccess}
      />

      {/* Receipt dialog — Approval Timeline for financing, simple receipt otherwise */}
      <Dialog open={!!receipt} onOpenChange={() => setReceipt(null)}>
        <DialogContent className="rounded-2xl max-w-lg">
          <DialogHeader className="sr-only"><DialogTitle>Payment confirmation</DialogTitle></DialogHeader>
          {receipt?.financing ? (
            <Box className="py-2" data-testid="approval-timeline">
              <Box className="flex items-center justify-center">
                <Box className="relative">
                  <Box className="h-16 w-16 rounded-full bg-[#EEF0FF] flex items-center justify-center">
                    <ShieldCheck className="h-8 w-8 text-[#5548D1]" />
                  </Box>
                  <Box className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full bg-emerald-500 flex items-center justify-center border-2 border-white">
                    <CheckCircle2 className="h-3.5 w-3.5 text-white" />
                  </Box>
                </Box>
              </Box>
              <Typography variant="inherit" component="h3" className="text-center font-head font-black text-brand-navy text-xl mt-4 tracking-tight">
                Application received
              </Typography>
              <Typography variant="inherit" component="p" className="text-center text-sm text-slate-500 mt-1">
                {receipt?.student_name}&apos;s 0% EMI plan · Receipt {receipt?.receipt_no}
              </Typography>

              {/* Quick summary chips */}
              <Box className="mt-5 grid grid-cols-3 gap-2 text-center">
                <Box className="rounded-lg bg-slate-50 border border-slate-100 py-2">
                  <Typography variant="inherit" component="p" className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Financed</Typography>
                  <Typography variant="inherit" component="p" className="font-head text-sm font-black text-brand-navy mt-0.5">{inr(receipt?.amount || 0)}</Typography>
                </Box>
                <Box className="rounded-lg bg-slate-50 border border-slate-100 py-2">
                  <Typography variant="inherit" component="p" className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Tenure</Typography>
                  <Typography variant="inherit" component="p" className="font-head text-sm font-black text-brand-navy mt-0.5">{receipt?.tenure || 12} mo</Typography>
                </Box>
                <Box className="rounded-lg bg-slate-50 border border-slate-100 py-2">
                  <Typography variant="inherit" component="p" className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Monthly EMI</Typography>
                  <Typography variant="inherit" component="p" className="font-head text-sm font-black text-[#5548D1] mt-0.5">{inr(receipt?.emi || 0)}</Typography>
                </Box>
              </Box>

              {/* Timeline */}
              <Box className="mt-6 relative">
                <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-3">What happens next</Typography>
                <Box className="absolute left-3.5 top-8 bottom-1 w-0.5 bg-slate-100" />
                <Box className="space-y-4 relative">
                  {[
                    { t: "Application received", s: "Just now", state: "done", d: "Your KYC, e-mandate and consent are recorded." },
                    { t: "NBFC underwriting", s: "Under 2 minutes", state: "active", d: "Our RBI-regulated partner runs a final policy check on your soft-pull profile." },
                    { t: "e-Mandate activation", s: "Same day", state: "upcoming", d: "UPI AutoPay or eNACH is armed for your monthly EMIs. Cancel anytime." },
                    { t: "School settled — full year", s: "T+1 working day", state: "upcoming", d: "The school gets 100% of the year&apos;s fees credited by Biglyp." },
                    { t: "First EMI scheduled", s: "Next month · 10th", state: "upcoming", d: "You&apos;ll get a pre-debit WhatsApp + SMS reminder 5 days before every EMI." },
                  ].map((row) => {
                    const done = row.state === "done";
                    const active = row.state === "active";
                    return (
                      <Box key={row.t} className="flex items-start gap-3">
                        <Box component="span" className={`h-7 w-7 rounded-full flex items-center justify-center shrink-0 border-2 border-white ring-2 ${
                          done ? "bg-emerald-500 text-white ring-emerald-100"
                            : active ? "bg-[#5548D1] text-white ring-[#EEF0FF] animate-pulse"
                            : "bg-white text-slate-400 ring-slate-100 border-slate-200"
                        }`}>
                          {done ? <Check className="h-3.5 w-3.5" /> : active ? <Zap className="h-3.5 w-3.5" /> : <Calendar className="h-3.5 w-3.5" />}
                        </Box>
                        <Box className="min-w-0 flex-1">
                          <Box className="flex items-center gap-2 flex-wrap">
                            <Typography variant="inherit" component="p" className={`font-head font-bold text-sm ${done || active ? "text-brand-navy" : "text-slate-500"}`}>{row.t}</Typography>
                            <Box component="span" className={`text-[10px] font-bold uppercase tracking-widest rounded-full px-2 py-0.5 ${
                              done ? "bg-emerald-100 text-emerald-700" : active ? "bg-[#EEF0FF] text-[#5548D1]" : "bg-slate-100 text-slate-500"
                            }`}>{row.s}</Box>
                          </Box>
                          <Typography variant="inherit" component="p" className="text-[12px] text-slate-500 mt-0.5 leading-relaxed" dangerouslySetInnerHTML={{ __html: row.d }} />
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
              </Box>

              <Box className="mt-6 rounded-lg bg-[#EEF0FF] border border-[#5548D1]/15 p-3 flex items-start gap-2.5">
                <Sparkles className="h-4 w-4 text-[#5548D1] shrink-0 mt-0.5" />
                <Typography variant="inherit" component="p" className="text-[12px] text-brand-navy leading-relaxed">
                  Track every EMI, download tax receipts and prepay any month early from your <b>Active Financing Schedule</b> tab.
                </Typography>
              </Box>

              <Box className="mt-5 grid grid-cols-2 gap-3">
                <Button variant="outline" onClick={() => setReceipt(null)} className="h-11 rounded-lg border-border text-slate-600 font-semibold" data-testid="receipt-close">
                  Close
                </Button>
                <Button onClick={() => { setReceipt(null); router.push("/app/financing"); }}
                  className="h-11 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8] font-semibold" data-testid="view-schedule-btn">
                  View schedule <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              </Box>
            </Box>
          ) : (
            <Box className="text-center py-4">
              <Box className="h-14 w-14 rounded-full bg-green-100 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </Box>
              <Typography variant="inherit" component="h3" className="font-head font-bold text-brand-navy text-xl mt-4">Payment successful</Typography>
              <Typography variant="inherit" component="p" className="text-sm text-slate-500 mt-1">Receipt {receipt?.receipt_no}</Typography>
              <Box className="bg-slate-50 rounded-xl p-4 mt-5 text-left text-sm space-y-1.5">
                <Box className="flex justify-between"><Box component="span" className="text-slate-500">Student</Box><Box component="span" className="font-medium">{receipt?.student_name}</Box></Box>
                <Box className="flex justify-between"><Box component="span" className="text-slate-500">Mode</Box><Box component="span" className="font-medium">{receipt?.mode}</Box></Box>
                <Box className="flex justify-between"><Box component="span" className="text-slate-500">Amount</Box><Box component="span" className="font-medium">{inr(receipt?.amount)}</Box></Box>
                <Box className="flex justify-between"><Box component="span" className="text-slate-500">GST</Box><Box component="span" className="font-medium">{inr(receipt?.gst)}</Box></Box>
              </Box>
              <Button onClick={() => setReceipt(null)} className="w-full mt-5 h-11 rounded-lg bg-[#5548D1] hover:bg-[#3F35A8]" data-testid="receipt-close">
                <Download className="h-4 w-4 mr-2" /> Done
              </Button>
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </ParentLayout>
  );
}
