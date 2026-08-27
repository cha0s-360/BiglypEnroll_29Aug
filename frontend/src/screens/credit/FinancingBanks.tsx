'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from "react";
import api, { inr } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Landmark, Plus, Pencil, Trash2, Save } from "lucide-react";

const NAME_MATCH_OPTIONS = [
  { value: "profile", label: "Profile name" },
  { value: "pan", label: "PAN name" },
  { value: "aadhaar", label: "Aadhaar name" },
];

const MATRIX_ROWS = [
  ["high_cibil_high_income", "CIBIL ≥ threshold  &  Income ≥ threshold"],
  ["high_cibil_low_income", "CIBIL ≥ threshold  &  Income < threshold"],
  ["low_cibil_high_income", "CIBIL < threshold  &  Income ≥ threshold"],
  ["low_cibil_low_income", "CIBIL < threshold  &  Income < threshold"],
];

const blankBank = () => ({
  name: "",
  active: true,
  advance_emi: false,
  min_loan_amount: 25000,
  location_match_aadhaar: false,
  name_match_rule: "aadhaar",
  income_proof: {
    cibil_threshold: 750,
    income_threshold: 750000,
    required_matrix: {
      high_cibil_high_income: false,
      high_cibil_low_income: true,
      low_cibil_high_income: true,
      low_cibil_low_income: true,
    },
  },
  fund_release: { multi_account_allowed: false, vendor_external_allowed: false },
});

function SectionTitle({ children }) {
  return (
    <Typography variant="inherit" component="p" className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mt-1">
      {children}
    </Typography>
  );
}

function ToggleRow({ label, help, checked, onChange, testid }) {
  return (
    <Box className="flex items-center justify-between gap-4 py-1.5">
      <Box className="min-w-0">
        <Label className="text-sm font-medium text-brand-navy">{label}</Label>
        {help && <Typography variant="inherit" component="p" className="text-xs text-muted-foreground mt-0.5">{help}</Typography>}
      </Box>
      <Box className="flex items-center gap-2 shrink-0">
        <Box component="span" className="text-xs text-muted-foreground w-7 text-right">{checked ? "Yes" : "No"}</Box>
        <Switch checked={!!checked} onCheckedChange={onChange} data-testid={testid} />
      </Box>
    </Box>
  );
}

export default function FinancingBanks() {
  const [banks, setBanks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null); // bank id or null (new)
  const [form, setForm] = useState(blankBank());
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/credit/financing-banks")
      .then(({ data }) => setBanks(data))
      .catch(() => toast.error("Failed to load financing banks"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(blankBank()); setOpen(true); };
  const openEdit = (b) => {
    const base = blankBank();
    setEditing(b.id);
    setForm({
      ...base, ...b,
      income_proof: {
        ...base.income_proof, ...(b.income_proof || {}),
        required_matrix: { ...base.income_proof.required_matrix, ...((b.income_proof || {}).required_matrix || {}) },
      },
      fund_release: { ...base.fund_release, ...(b.fund_release || {}) },
    });
    setOpen(true);
  };

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setIP = (k, v) => setForm((f) => ({ ...f, income_proof: { ...f.income_proof, [k]: v } }));
  const setMatrix = (k, v) => setForm((f) => ({ ...f, income_proof: { ...f.income_proof, required_matrix: { ...f.income_proof.required_matrix, [k]: v } } }));
  const setFR = (k, v) => setForm((f) => ({ ...f, fund_release: { ...f.fund_release, [k]: v } }));

  const save = async () => {
    if (!form.name.trim()) { toast.error("Bank name is required"); return; }
    const payload = {
      ...form,
      min_loan_amount: Number(form.min_loan_amount) || 0,
      income_proof: {
        ...form.income_proof,
        cibil_threshold: Number(form.income_proof.cibil_threshold) || 0,
        income_threshold: Number(form.income_proof.income_threshold) || 0,
      },
    };
    setSaving(true);
    try {
      if (editing) { await api.put(`/credit/financing-banks/${editing}`, payload); toast.success(`${payload.name} updated`); }
      else { await api.post("/credit/financing-banks", payload); toast.success(`${payload.name} added`); }
      setOpen(false);
      load();
    } catch {
      toast.error("Could not save the bank");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (b) => {
    if (typeof window !== "undefined" && !window.confirm(`Delete "${b.name}"? This cannot be undone.`)) return;
    try { await api.delete(`/credit/financing-banks/${b.id}`); toast.success("Bank deleted"); load(); }
    catch { toast.error("Could not delete the bank"); }
  };

  return (
    <Box>
      <Typography variant="inherit" component="p" className="text-sm text-muted-foreground mb-4">
        Configure banks that fund the 0% EMI financing flow — all fields editable anytime.
      </Typography>
      <Box className="flex justify-end mb-4">
        <Button onClick={openNew} data-testid="add-bank-btn" className="rounded-sm bg-brand-blue hover:bg-brand-navy">
          <Plus className="h-4 w-4 mr-2" /> Add Bank
        </Button>
      </Box>

      {loading ? (
        <Box className="text-sm text-muted-foreground">Loading…</Box>
      ) : banks.length === 0 ? (
        <Box className="text-sm text-muted-foreground border border-dashed rounded-md p-10 text-center" data-testid="banks-empty">
          No financing banks yet. Click <b>Add Bank</b> to create one.
        </Box>
      ) : (
        <Box className="space-y-3" data-testid="banks-list">
          {banks.map((b) => (
            <Box key={b.id} data-testid={`bank-row-${b.id}`} className="bg-white border border-border rounded-md p-4 flex items-start justify-between gap-4">
              <Box className="min-w-0">
                <Box className="flex items-center gap-2 flex-wrap">
                  <Landmark className="h-4 w-4 text-brand-blue" />
                  <Typography variant="inherit" component="h3" className="font-head font-bold text-brand-navy" data-testid={`bank-name-${b.id}`}>{b.name}</Typography>
                  <Badge className={b.active ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-100" : "bg-slate-100 text-slate-500 hover:bg-slate-100"}>{b.active ? "Active" : "Inactive"}</Badge>
                </Box>
                <Box className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                  <Box component="span">Advance EMI: <b className="text-brand-navy">{b.advance_emi ? "Yes" : "No"}</b></Box>
                  <Box component="span">Min loan: <b className="text-brand-navy">{inr(b.min_loan_amount)}</b></Box>
                  <Box component="span">Location-match: <b className="text-brand-navy">{b.location_match_aadhaar ? "Yes" : "No"}</b></Box>
                  <Box component="span">Name-match: <b className="text-brand-navy">{NAME_MATCH_OPTIONS.find((o) => o.value === b.name_match_rule)?.label || b.name_match_rule}</b></Box>
                  <Box component="span">CIBIL ≥ <b className="text-brand-navy">{b.income_proof?.cibil_threshold}</b></Box>
                  <Box component="span">Income ≥ <b className="text-brand-navy">{inr(b.income_proof?.income_threshold)}</b></Box>
                  <Box component="span">Multi-account: <b className="text-brand-navy">{b.fund_release?.multi_account_allowed ? "Yes" : "No"}</b></Box>
                  <Box component="span">Vendor a/c: <b className="text-brand-navy">{b.fund_release?.vendor_external_allowed ? "Yes" : "No"}</b></Box>
                </Box>
              </Box>
              <Box className="flex gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={() => openEdit(b)} data-testid={`edit-bank-${b.id}`}>
                  <Pencil className="h-3.5 w-3.5 mr-1" /> Edit
                </Button>
                <Button variant="outline" size="sm" onClick={() => remove(b)} data-testid={`delete-bank-${b.id}`} className="text-red-600 border-red-200 hover:bg-red-50">
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </Box>
            </Box>
          ))}
        </Box>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="bank-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Financing Bank" : "Add Financing Bank"}</DialogTitle>
          </DialogHeader>

          <Box className="space-y-5 py-1">
            {/* Basics */}
            <Box className="space-y-2">
              <Box>
                <Label className="text-sm font-medium text-brand-navy">Bank name</Label>
                <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. CSB Bank Limited" className="mt-1.5 rounded-md" data-testid="bank-name" />
              </Box>
              <ToggleRow label="Status — Active" help="Only active banks are used by the financing flow." checked={form.active} onChange={(v) => set("active", v)} testid="bank-active" />
            </Box>

            {/* Screen 1 controls */}
            <Box className="rounded-md border border-border p-3 space-y-1">
              <SectionTitle>Screen 1 — Amount & EMI</SectionTitle>
              <ToggleRow
                label="Advance EMI"
                help='Yes → parent pays a mandatory "1st Installment (Advance)" (counts as EMI #1). No → optional Down Payment (loan = fee − down payment).'
                checked={form.advance_emi} onChange={(v) => set("advance_emi", v)} testid="bank-advance-emi" />
              <Box className="pt-1">
                <Label className="text-sm font-medium text-brand-navy">Minimum loan amount (₹)</Label>
                <Input type="number" min={0} value={form.min_loan_amount} onChange={(e) => set("min_loan_amount", e.target.value)} className="mt-1.5 rounded-md w-48" data-testid="bank-min-loan" />
              </Box>
            </Box>

            {/* KYC controls */}
            <Box className="rounded-md border border-border p-3 space-y-1">
              <SectionTitle>Screen 3 — KYC matching</SectionTitle>
              <ToggleRow label="Location match to Aadhaar" help="Require the applicant's live location to match their Aadhaar-registered area." checked={form.location_match_aadhaar} onChange={(v) => set("location_match_aadhaar", v)} testid="bank-location-match" />
              <Box className="pt-1">
                <Label className="text-sm font-medium text-brand-navy">Name-match rule</Label>
                <Select value={form.name_match_rule} onValueChange={(v) => set("name_match_rule", v)}>
                  <SelectTrigger className="mt-1.5 rounded-md w-full" data-testid="bank-name-match"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {NAME_MATCH_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value} data-testid={`name-match-${o.value}`}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Box>
            </Box>

            {/* Income proof */}
            <Box className="rounded-md border border-border p-3 space-y-3">
              <SectionTitle>Screen 2 — Income proof criteria</SectionTitle>
              <Box className="flex flex-wrap gap-4">
                <Box>
                  <Label className="text-sm font-medium text-brand-navy">CIBIL threshold</Label>
                  <Input type="number" min={300} max={900} value={form.income_proof.cibil_threshold} onChange={(e) => setIP("cibil_threshold", e.target.value)} className="mt-1.5 rounded-md w-40" data-testid="bank-cibil-threshold" />
                </Box>
                <Box>
                  <Label className="text-sm font-medium text-brand-navy">Income threshold (₹ / year)</Label>
                  <Input type="number" min={0} value={form.income_proof.income_threshold} onChange={(e) => setIP("income_threshold", e.target.value)} className="mt-1.5 rounded-md w-52" data-testid="bank-income-threshold" />
                </Box>
              </Box>
              <Box>
                <Typography variant="inherit" component="p" className="text-xs text-muted-foreground mb-1">Is income proof <b>required</b> for each combination?</Typography>
                <Box className="rounded-md border border-border divide-y divide-border">
                  {MATRIX_ROWS.map(([key, label]) => (
                    <Box key={key} className="px-3">
                      <ToggleRow label={label} checked={form.income_proof.required_matrix[key]} onChange={(v) => setMatrix(key, v)} testid={`bank-matrix-${key}`} />
                    </Box>
                  ))}
                </Box>
              </Box>
            </Box>

            {/* Fund release */}
            <Box className="rounded-md border border-border p-3 space-y-1">
              <SectionTitle>Fund release rules</SectionTitle>
              <ToggleRow label="Multiple accounts allowed" help="Allow disbursement/collection across more than one account." checked={form.fund_release.multi_account_allowed} onChange={(v) => setFR("multi_account_allowed", v)} testid="bank-multi-account" />
              <ToggleRow label="Vendor / external accounts allowed" help="Allow fund release to vendor or external (third-party) accounts." checked={form.fund_release.vendor_external_allowed} onChange={(v) => setFR("vendor_external_allowed", v)} testid="bank-vendor-external" />
            </Box>
          </Box>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} data-testid="cancel-bank-btn">Cancel</Button>
            <Button onClick={save} disabled={saving} data-testid="save-bank-btn" className="bg-brand-blue hover:bg-brand-navy">
              {saving ? "Saving…" : (<><Save className="h-4 w-4 mr-2" /> Save Bank</>)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
