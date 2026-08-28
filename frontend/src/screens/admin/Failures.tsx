'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle, Gauge, IdCard, Landmark, X, Calendar, GraduationCap,
  User, ChevronRight, ShieldAlert, Info,
} from "lucide-react";

/**
 * ============================================================================
 * OPS Failure Dashboard — Failed / Rejected EMI applications
 * ============================================================================
 * Ops-only view. NONE of this detail (scores, mismatch reasons, bank codes) is
 * ever surfaced on parent-facing screens — parents only ever see the neutral
 * "not available" messaging.
 *
 * FAILURE-EVENT CONTRACT (to wire later — currently MOCK data below):
 * Each of the three parent-journey steps should POST a failure event on failure:
 *
 *   POST /api/ops/failures
 *   {
 *     application_id:  string,          // links back to the loan/EMI application
 *     applicant_name:  string,
 *     school_id:       string,
 *     school_name:     string,
 *     category:        "credit_score" | "kyc" | "bank",
 *     reason:          string,          // category-specific short reason (see below)
 *     detail:          object,          // category-specific structured payload:
 *        // credit_score -> { score:number, threshold:number, bureau:string }
 *        // kyc          -> { mismatch_type:"dob"|"name"|"location",
 *        //                    submitted:string, on_record:string }
 *        // bank         -> { code:string,       // e.g. ADV_NACH_ACCOUNT_MISMATCH
 *        //                    advance_account:string, nach_account:string,
 *        //                    lender:string }
 *     occurred_at:     ISO-8601 datetime
 *   }
 *
 * Sources:
 *   - credit_score : Eligibility & Details step  (CIBIL/credit-score threshold)
 *   - kyc          : KYC & Verification step      (DOB / Name / Location mismatch)
 *   - bank         : Accept & Pay step            (1st-installment/advance a/c != NACH a/c, etc.)
 *
 * GET /api/ops/failures?category=... will return the list this dashboard reads.
 * ============================================================================
 */

type Category = "credit_score" | "kyc" | "bank";

interface FailureRecord {
  id: string;
  application_id: string;
  applicant_name: string;
  school_name: string;
  occurred_at: string; // ISO
  category: Category;
  reason: string;
  detail: Record<string, any>;
}

// ---------------------------------------------------------------------------
// MOCK DATA (replace with GET /api/ops/failures once the steps log events)
// ---------------------------------------------------------------------------
const MOCK_FAILURES: FailureRecord[] = [
  // ---- Credit Score Failures (Eligibility & Details step) ----
  {
    id: "f1", application_id: "APP-24817", applicant_name: "Rajesh Malhotra",
    school_name: "Horizon International School", occurred_at: "2026-08-27T10:24:00",
    category: "credit_score", reason: "Score below threshold",
    detail: { score: 682, threshold: 750, bureau: "TransUnion CIBIL" },
  },
  {
    id: "f2", application_id: "APP-24790", applicant_name: "Sneha Iyer",
    school_name: "Greenwood Academy", occurred_at: "2026-08-27T09:05:00",
    category: "credit_score", reason: "Score below threshold",
    detail: { score: 711, threshold: 750, bureau: "CRIF High Mark" },
  },
  {
    id: "f3", application_id: "APP-24765", applicant_name: "Imran Sheikh",
    school_name: "Horizon International School", occurred_at: "2026-08-26T16:48:00",
    category: "credit_score", reason: "Thin file / no score",
    detail: { score: 0, threshold: 750, bureau: "TransUnion CIBIL" },
  },
  {
    id: "f4", application_id: "APP-24702", applicant_name: "Kavita Reddy",
    school_name: "St. Xavier's High", occurred_at: "2026-08-25T13:12:00",
    category: "credit_score", reason: "Score below threshold",
    detail: { score: 640, threshold: 720, bureau: "Experian" },
  },

  // ---- KYC Failures (KYC & Verification step) ----
  {
    id: "f5", application_id: "APP-24811", applicant_name: "Anita Deshmukh",
    school_name: "Greenwood Academy", occurred_at: "2026-08-27T11:40:00",
    category: "kyc", reason: "DOB Mismatch",
    detail: { mismatch_type: "dob", submitted: "14 Mar 1986", on_record: "14 May 1986" },
  },
  {
    id: "f6", application_id: "APP-24788", applicant_name: "Vikram Nair",
    school_name: "Horizon International School", occurred_at: "2026-08-27T08:22:00",
    category: "kyc", reason: "Name Mismatch",
    detail: { mismatch_type: "name", submitted: "Vikram Nair", on_record: "Vikram Krishnan Nair" },
  },
  {
    id: "f7", application_id: "APP-24744", applicant_name: "Pooja Agarwal",
    school_name: "St. Xavier's High", occurred_at: "2026-08-26T15:03:00",
    category: "kyc", reason: "Location Mismatch",
    detail: { mismatch_type: "location", submitted: "Pune, MH", on_record: "Nagpur, MH" },
  },
  {
    id: "f8", application_id: "APP-24710", applicant_name: "Suresh Menon",
    school_name: "Greenwood Academy", occurred_at: "2026-08-25T10:55:00",
    category: "kyc", reason: "DOB Mismatch",
    detail: { mismatch_type: "dob", submitted: "02 Jan 1979", on_record: "20 Jan 1979" },
  },

  // ---- Bank Rejections (Accept & Pay step) ----
  {
    id: "f9", application_id: "APP-24815", applicant_name: "Deepak Chopra",
    school_name: "Horizon International School", occurred_at: "2026-08-27T12:10:00",
    category: "bank", reason: "Advance a/c ≠ NACH mandate a/c",
    detail: {
      code: "ADV_NACH_ACCOUNT_MISMATCH",
      advance_account: "HDFC ••••4521",
      nach_account: "ICICI ••••8890",
      lender: "HDFC Bank",
    },
  },
  {
    id: "f10", application_id: "APP-24779", applicant_name: "Meera Joshi",
    school_name: "St. Xavier's High", occurred_at: "2026-08-26T18:30:00",
    category: "bank", reason: "Advance a/c ≠ NACH mandate a/c",
    detail: {
      code: "ADV_NACH_ACCOUNT_MISMATCH",
      advance_account: "SBI ••••1102",
      nach_account: "SBI ••••7734",
      lender: "Axis Bank",
    },
  },
  {
    id: "f11", application_id: "APP-24756", applicant_name: "Arjun Pillai",
    school_name: "Greenwood Academy", occurred_at: "2026-08-26T09:47:00",
    category: "bank", reason: "Mandate registration declined",
    detail: {
      code: "NACH_MANDATE_REJECTED",
      advance_account: "Kotak ••••3320",
      nach_account: "Kotak ••••3320",
      lender: "ICICI Bank",
    },
  },
  {
    id: "f12", application_id: "APP-24698", applicant_name: "Fatima Khan",
    school_name: "Horizon International School", occurred_at: "2026-08-24T14:15:00",
    category: "bank", reason: "Insufficient funds on advance debit",
    detail: {
      code: "ADVANCE_DEBIT_FAILED",
      advance_account: "Yes Bank ••••6650",
      nach_account: "Yes Bank ••••6650",
      lender: "Aditya Birla NBFC",
    },
  },
];

const TABS: { key: Category; label: string; icon: any; tint: string; fg: string; ring: string }[] = [
  { key: "credit_score", label: "Credit Score Failures", icon: Gauge, tint: "bg-rose-50", fg: "text-rose-600", ring: "ring-rose-200" },
  { key: "kyc", label: "KYC Failures", icon: IdCard, tint: "bg-amber-50", fg: "text-amber-600", ring: "ring-amber-200" },
  { key: "bank", label: "Bank Rejections", icon: Landmark, tint: "bg-indigo-50", fg: "text-indigo-600", ring: "ring-indigo-200" },
];

const fmtDate = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
};

export default function Failures() {
  const [tab, setTab] = useState<Category>("credit_score");
  const [selected, setSelected] = useState<FailureRecord | null>(null);

  const counts = useMemo(() => {
    const c: Record<Category, number> = { credit_score: 0, kyc: 0, bank: 0 };
    MOCK_FAILURES.forEach((f) => { c[f.category] += 1; });
    return c;
  }, []);

  const rows = useMemo(
    () => MOCK_FAILURES.filter((f) => f.category === tab)
      .sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1)),
    [tab]
  );

  const activeTab = TABS.find((t) => t.key === tab)!;

  return (
    <Box className="space-y-6" data-testid="failures-dashboard">
      {/* Header */}
      <Box className="flex flex-wrap items-start justify-between gap-4">
        <Box className="flex items-start gap-3">
          <Box className="h-11 w-11 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
            <ShieldAlert className="h-5 w-5" />
          </Box>
          <Box>
            <Typography variant="inherit" component="h2" className="font-head text-2xl font-black tracking-tight text-brand-navy leading-tight">
              Application Failures
            </Typography>
            <Typography variant="inherit" component="p" className="text-sm text-slate-500 mt-0.5 max-w-xl">
              Every failed or rejected financing application, grouped for review &amp; follow-up. Ops-only — none of this is shown to parents.
            </Typography>
          </Box>
        </Box>
        <Box className="inline-flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 px-3 py-2">
          <Info className="h-4 w-4 text-amber-600 shrink-0" />
          <Typography variant="inherit" component="span" className="text-[11px] font-semibold text-amber-800 leading-tight">
            Showing sample data — wires to live failure events once logged.
          </Typography>
        </Box>
      </Box>

      {/* Tabs */}
      <Box className="grid grid-cols-1 sm:grid-cols-3 gap-3" data-testid="failure-tabs">
        {TABS.map((t) => {
          const active = tab === t.key;
          const Icon = t.icon;
          return (
            <Box component="button" key={t.key} data-testid={`tab-${t.key}`}
              onClick={() => setTab(t.key)}
              className={`text-left rounded-2xl border-2 p-4 transition-all duration-200 ${
                active
                  ? "border-brand-navy bg-white soft-shadow-lg -translate-y-0.5"
                  : "border-transparent bg-white soft-shadow hover:border-slate-200"
              }`}>
              <Box className="flex items-center justify-between">
                <Box className={`h-9 w-9 rounded-xl ${t.tint} ${t.fg} flex items-center justify-center`}>
                  <Icon className="h-4 w-4" />
                </Box>
                <Box component="span" className={`font-head text-2xl font-black tabular-nums ${active ? "text-brand-navy" : "text-slate-400"}`}>
                  {counts[t.key]}
                </Box>
              </Box>
              <Typography variant="inherit" component="p" className={`mt-3 text-sm font-bold ${active ? "text-brand-navy" : "text-slate-500"}`}>
                {t.label}
              </Typography>
            </Box>
          );
        })}
      </Box>

      {/* Table */}
      <Box className="bg-white rounded-2xl soft-shadow border border-border/70 overflow-hidden" data-testid="failure-table">
        <Box className="hidden md:grid grid-cols-[1.4fr_1.4fr_1.1fr_1.5fr_auto] gap-4 px-5 py-3 bg-slate-50 border-b border-border/70 text-[11px] uppercase tracking-[0.12em] font-bold text-slate-500">
          <Box component="span">Applicant</Box>
          <Box component="span">School</Box>
          <Box component="span">Date / Time</Box>
          <Box component="span">{activeTab.label.replace(" Failures", "").replace(" Rejections", "")} reason</Box>
          <Box component="span" className="text-right">Detail</Box>
        </Box>

        {rows.length === 0 ? (
          <Box className="p-12 text-center">
            <AlertTriangle className="h-8 w-8 text-slate-300 mx-auto" />
            <Typography variant="inherit" component="p" className="mt-3 text-sm text-slate-500">No failures in this category.</Typography>
          </Box>
        ) : (
          <Box className="divide-y divide-border/70">
            {rows.map((r) => (
              <Box component="button" key={r.id} data-testid={`failure-row-${r.id}`}
                onClick={() => setSelected(r)}
                className="w-full text-left grid grid-cols-1 md:grid-cols-[1.4fr_1.4fr_1.1fr_1.5fr_auto] gap-1.5 md:gap-4 px-5 py-3.5 hover:bg-slate-50/70 transition-colors items-center">
                <Box className="flex items-center gap-2.5 min-w-0">
                  <Box className="h-8 w-8 rounded-lg bg-[#EEF0FF] text-[#5548D1] flex items-center justify-center shrink-0">
                    <User className="h-4 w-4" />
                  </Box>
                  <Box className="min-w-0">
                    <Typography variant="inherit" component="p" className="text-sm font-bold text-brand-navy truncate">{r.applicant_name}</Typography>
                    <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 tabular-nums">{r.application_id}</Typography>
                  </Box>
                </Box>
                <Box className="flex items-center gap-1.5 text-sm text-slate-600 min-w-0">
                  <GraduationCap className="h-3.5 w-3.5 text-slate-400 shrink-0 hidden md:block" />
                  <Box component="span" className="truncate">{r.school_name}</Box>
                </Box>
                <Box className="flex items-center gap-1.5 text-[13px] text-slate-500">
                  <Calendar className="h-3.5 w-3.5 text-slate-400 shrink-0 hidden md:block" />
                  {fmtDate(r.occurred_at)}
                </Box>
                <Box>
                  <Box component="span" className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${activeTab.tint} ${activeTab.fg}`}>
                    {r.reason}
                  </Box>
                </Box>
                <Box className="hidden md:flex justify-end">
                  <ChevronRight className="h-4 w-4 text-slate-300" />
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </Box>

      {/* Detail dialog */}
      <Dialog open={!!selected} onOpenChange={(o) => { if (!o) setSelected(null); }}>
        <DialogContent className="sm:max-w-lg" data-testid="failure-detail">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-head text-brand-navy">
              <ShieldAlert className="h-5 w-5 text-rose-600" />
              Failure detail
            </DialogTitle>
          </DialogHeader>

          {selected && (
            <Box className="space-y-4">
              <Box className="rounded-xl border border-border/70 p-4">
                <Box className="flex items-center justify-between gap-3">
                  <Box>
                    <Typography variant="inherit" component="p" className="font-head text-lg font-black text-brand-navy">{selected.applicant_name}</Typography>
                    <Typography variant="inherit" component="p" className="text-xs text-slate-400 tabular-nums">{selected.application_id}</Typography>
                  </Box>
                  <Box component="span" className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${activeTab.tint} ${activeTab.fg}`}>
                    {activeTab.label}
                  </Box>
                </Box>
                <Box className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <Box>
                    <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">School</Typography>
                    <Typography variant="inherit" component="p" className="text-brand-navy font-medium">{selected.school_name}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">Occurred</Typography>
                    <Typography variant="inherit" component="p" className="text-brand-navy font-medium">{fmtDate(selected.occurred_at)}</Typography>
                  </Box>
                </Box>
              </Box>

              {/* Category-specific ops-only detail */}
              <Box className="rounded-xl bg-slate-50 border border-border/70 p-4 space-y-2.5" data-testid="failure-detail-specific">
                <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-wider text-slate-500 font-bold flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5" /> Reason: {selected.reason}
                </Typography>

                {selected.category === "credit_score" && (
                  <Box className="space-y-1.5 text-sm">
                    <DetailRow label="Bureau" value={selected.detail.bureau} />
                    <DetailRow label="Applicant score" value={selected.detail.score === 0 ? "No score / thin file" : selected.detail.score}
                      valueClass="text-rose-600 font-bold" />
                    <DetailRow label="Required threshold" value={selected.detail.threshold} />
                    <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 pt-1">
                      Ops-only visibility — the parent only saw a neutral {'"EMI not available"'} message.
                    </Typography>
                  </Box>
                )}

                {selected.category === "kyc" && (
                  <Box className="space-y-1.5 text-sm">
                    <DetailRow label="Mismatch type" value={
                      { dob: "DOB Mismatch", name: "Name Mismatch", location: "Location Mismatch" }[selected.detail.mismatch_type as string]
                    } valueClass="text-amber-700 font-bold" />
                    <DetailRow label="Submitted" value={selected.detail.submitted} />
                    <DetailRow label="On record" value={selected.detail.on_record} />
                  </Box>
                )}

                {selected.category === "bank" && (
                  <Box className="space-y-1.5 text-sm">
                    <DetailRow label="Bank / lender" value={selected.detail.lender} />
                    <DetailRow label="Rejection code" value={selected.detail.code} valueClass="font-mono text-[12px] text-indigo-700 font-bold" />
                    <DetailRow label="1st installment (advance) a/c" value={selected.detail.advance_account} />
                    <DetailRow label="NACH mandate a/c" value={selected.detail.nach_account}
                      valueClass={selected.detail.code === "ADV_NACH_ACCOUNT_MISMATCH" ? "text-rose-600 font-bold" : ""} />
                    {selected.detail.code === "ADV_NACH_ACCOUNT_MISMATCH" && (
                      <Typography variant="inherit" component="p" className="text-[11px] text-rose-600 pt-1">
                        Advance-payment account does not match the NACH mandate account.
                      </Typography>
                    )}
                  </Box>
                )}
              </Box>

              <Box className="flex justify-end gap-2 pt-1">
                <Button variant="outline" onClick={() => setSelected(null)} data-testid="failure-detail-close"
                  className="h-10 rounded-xl">
                  <X className="h-4 w-4 mr-1.5" /> Close
                </Button>
                <Button data-testid="failure-detail-followup"
                  className="h-10 rounded-xl bg-brand-navy hover:bg-brand-navy/90 text-white">
                  Mark for follow-up
                </Button>
              </Box>
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}

function DetailRow({ label, value, valueClass = "" }: { label: string; value: any; valueClass?: string }) {
  return (
    <Box className="flex items-center justify-between gap-4">
      <Typography variant="inherit" component="span" className="text-slate-500">{label}</Typography>
      <Typography variant="inherit" component="span" className={`text-brand-navy tabular-nums text-right ${valueClass}`}>{String(value)}</Typography>
    </Box>
  );
}
