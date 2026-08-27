'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from "react";
import api from "@/lib/api";
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
import { School, Plus, Pencil, Trash2, Save, Landmark, X, ArrowUp } from "lucide-react";

const blankForm = () => ({ name: "", financing_enabled: true, banks: [] });

export default function SchoolFinancing() {
  const [schools, setSchools] = useState([]);
  const [dummyBanks, setDummyBanks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null); // school id or null (new)
  const [form, setForm] = useState(blankForm());
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/credit/fin-schools")
      .then(({ data }) => setSchools(data))
      .catch(() => toast.error("Failed to load schools"))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
    api.get("/credit/dummy-banks")
      .then(({ data }) => setDummyBanks(data))
      .catch(() => {});
  }, []);

  const bankName = (id) => dummyBanks.find((b) => b.id === id)?.name || id;

  const openNew = () => { setEditing(null); setForm(blankForm()); setOpen(true); };
  const openEdit = (s) => {
    setEditing(s.id);
    setForm({
      name: s.name || "",
      financing_enabled: !!s.financing_enabled,
      banks: (s.banks || []).map((b) => ({
        bank_id: b.bank_id, interest_rate: b.interest_rate, priority: b.priority,
      })),
    });
    setOpen(true);
  };

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setBank = (i, k, v) =>
    setForm((f) => ({ ...f, banks: f.banks.map((b, idx) => (idx === i ? { ...b, [k]: v } : b)) }));
  const addBankRow = () =>
    setForm((f) => ({ ...f, banks: [...f.banks, { bank_id: "", interest_rate: 12, priority: f.banks.length + 1 }] }));
  const removeBankRow = (i) =>
    setForm((f) => ({ ...f, banks: f.banks.filter((_, idx) => idx !== i) }));

  const save = async () => {
    if (!form.name.trim()) { toast.error("School name is required"); return; }
    for (const b of form.banks) {
      if (!b.bank_id) { toast.error("Pick a bank for every attached row (or remove empty rows)"); return; }
    }
    const ids = form.banks.map((b) => b.bank_id);
    if (new Set(ids).size !== ids.length) { toast.error("The same bank is attached more than once"); return; }
    const payload = {
      name: form.name.trim(),
      financing_enabled: form.financing_enabled,
      banks: form.banks.map((b) => ({
        bank_id: b.bank_id,
        bank_name: bankName(b.bank_id),
        interest_rate: Number(b.interest_rate) || 0,
        priority: Number(b.priority) || 1,
      })),
    };
    setSaving(true);
    try {
      if (editing) { await api.put(`/credit/fin-schools/${editing}`, payload); toast.success(`${payload.name} updated`); }
      else { await api.post("/credit/fin-schools", payload); toast.success(`${payload.name} added`); }
      setOpen(false);
      load();
    } catch {
      toast.error("Could not save the school");
    } finally {
      setSaving(false);
    }
  };

  const toggleFinancing = async (s) => {
    try {
      await api.put(`/credit/fin-schools/${s.id}`, {
        name: s.name,
        financing_enabled: !s.financing_enabled,
        banks: (s.banks || []).map((b) => ({
          bank_id: b.bank_id, bank_name: b.bank_name, interest_rate: b.interest_rate, priority: b.priority,
        })),
      });
      toast.success(`Financing ${!s.financing_enabled ? "enabled" : "disabled"} for ${s.name}`);
      load();
    } catch {
      toast.error("Could not update financing toggle");
    }
  };

  const remove = async (s) => {
    if (typeof window !== "undefined" && !window.confirm(`Delete "${s.name}"? This cannot be undone.`)) return;
    try { await api.delete(`/credit/fin-schools/${s.id}`); toast.success("School deleted"); load(); }
    catch { toast.error("Could not delete the school"); }
  };

  return (
    <Box>
      <Typography variant="inherit" component="p" className="text-sm text-muted-foreground mb-4">
        Manage schools and the banks that fund their fee financing. Each bank has an independent
        interest rate and a priority used for auto-selection. Toggle financing on/off per school.
      </Typography>
      <Box className="flex justify-end mb-4">
        <Button onClick={openNew} data-testid="add-school-btn" className="rounded-sm bg-brand-blue hover:bg-brand-navy">
          <Plus className="h-4 w-4 mr-2" /> Add School
        </Button>
      </Box>

      {loading ? (
        <Box className="text-sm text-muted-foreground">Loading…</Box>
      ) : schools.length === 0 ? (
        <Box className="text-sm text-muted-foreground border border-dashed rounded-md p-10 text-center" data-testid="schools-empty">
          No schools yet. Click <b>Add School</b> to create one.
        </Box>
      ) : (
        <Box className="space-y-3" data-testid="schools-list">
          {schools.map((s) => (
            <Box key={s.id} data-testid={`school-row-${s.id}`} className="bg-white border border-border rounded-md p-4">
              <Box className="flex items-start justify-between gap-4">
                <Box className="min-w-0">
                  <Box className="flex items-center gap-2 flex-wrap">
                    <School className="h-4 w-4 text-brand-blue" />
                    <Typography variant="inherit" component="h3" className="font-head font-bold text-brand-navy" data-testid={`school-name-${s.id}`}>{s.name}</Typography>
                    <Badge
                      data-testid={`school-financing-badge-${s.id}`}
                      className={s.financing_enabled ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-100" : "bg-slate-100 text-slate-500 hover:bg-slate-100"}>
                      Financing {s.financing_enabled ? "On" : "Off"}
                    </Badge>
                    <Box component="span" className="text-xs text-muted-foreground">· {(s.banks || []).length} bank{(s.banks || []).length === 1 ? "" : "s"} attached</Box>
                  </Box>
                </Box>
                <Box className="flex items-center gap-3 shrink-0">
                  <Box className="flex items-center gap-2">
                    <Box component="span" className="text-xs text-muted-foreground">{s.financing_enabled ? "On" : "Off"}</Box>
                    <Switch checked={!!s.financing_enabled} onCheckedChange={() => toggleFinancing(s)} data-testid={`toggle-financing-${s.id}`} />
                  </Box>
                  <Button variant="outline" size="sm" onClick={() => openEdit(s)} data-testid={`edit-school-${s.id}`}>
                    <Pencil className="h-3.5 w-3.5 mr-1" /> Edit
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => remove(s)} data-testid={`delete-school-${s.id}`} className="text-red-600 border-red-200 hover:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </Box>
              </Box>

              {(s.banks || []).length > 0 && (
                <Box className="mt-3 rounded-md border border-border divide-y divide-border" data-testid={`school-banks-${s.id}`}>
                  <Box className="grid grid-cols-12 px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground bg-slate-50">
                    <Box className="col-span-1">#</Box>
                    <Box className="col-span-7">Bank</Box>
                    <Box className="col-span-4 text-right">Interest rate</Box>
                  </Box>
                  {(s.banks || []).map((b) => (
                    <Box key={b.bank_id} className="grid grid-cols-12 px-3 py-2 text-sm items-center" data-testid={`school-${s.id}-bank-${b.bank_id}`}>
                      <Box className="col-span-1">
                        <Box component="span" className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-tint text-brand-blue text-xs font-bold">{b.priority}</Box>
                      </Box>
                      <Box className="col-span-7 flex items-center gap-2">
                        <Landmark className="h-3.5 w-3.5 text-brand-blue" />
                        <Box component="span" className="font-medium text-brand-navy">{b.bank_name}</Box>
                      </Box>
                      <Box className="col-span-4 text-right font-semibold text-brand-navy">{Number(b.interest_rate).toFixed(2)}%</Box>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          ))}
        </Box>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="school-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit School" : "Add School"}</DialogTitle>
          </DialogHeader>

          <Box className="space-y-5 py-1">
            <Box>
              <Label className="text-sm font-medium text-brand-navy">School name</Label>
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Horizon International School" className="mt-1.5 rounded-md" data-testid="school-name" />
            </Box>

            <Box className="flex items-center justify-between gap-4 rounded-md border border-border p-3">
              <Box>
                <Label className="text-sm font-medium text-brand-navy">Fee financing</Label>
                <Typography variant="inherit" component="p" className="text-xs text-muted-foreground mt-0.5">Enable or disable the 0% EMI fee financing product for this school.</Typography>
              </Box>
              <Box className="flex items-center gap-2 shrink-0">
                <Box component="span" className="text-xs text-muted-foreground w-7 text-right">{form.financing_enabled ? "On" : "Off"}</Box>
                <Switch checked={!!form.financing_enabled} onCheckedChange={(v) => set("financing_enabled", v)} data-testid="school-financing-toggle" />
              </Box>
            </Box>

            <Box className="rounded-md border border-border p-3 space-y-3">
              <Box className="flex items-center justify-between">
                <Typography variant="inherit" component="p" className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Attached banks</Typography>
                <Button variant="outline" size="sm" onClick={addBankRow} data-testid="add-bank-row-btn">
                  <Plus className="h-3.5 w-3.5 mr-1" /> Attach bank
                </Button>
              </Box>

              {form.banks.length === 0 ? (
                <Box className="text-xs text-muted-foreground py-2">No banks attached yet. Use <b>Attach bank</b> to add one with its own rate and priority.</Box>
              ) : (
                <Box className="space-y-2" data-testid="bank-rows">
                  <Box className="grid grid-cols-12 gap-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground px-1">
                    <Box className="col-span-6">Bank</Box>
                    <Box className="col-span-3">Interest %</Box>
                    <Box className="col-span-2 flex items-center gap-1">Priority <ArrowUp className="h-3 w-3" /></Box>
                    <Box className="col-span-1" />
                  </Box>
                  {form.banks.map((b, i) => (
                    <Box key={i} className="grid grid-cols-12 gap-2 items-center" data-testid={`bank-row-${i}`}>
                      <Box className="col-span-6">
                        <Select value={b.bank_id} onValueChange={(v) => setBank(i, "bank_id", v)}>
                          <SelectTrigger className="rounded-md w-full" data-testid={`bank-select-${i}`}><SelectValue placeholder="Select bank" /></SelectTrigger>
                          <SelectContent>
                            {dummyBanks.map((db) => (
                              <SelectItem key={db.id} value={db.id} data-testid={`bank-option-${db.id}`}>{db.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Box>
                      <Box className="col-span-3">
                        <Input type="number" step="0.01" min={0} value={b.interest_rate} onChange={(e) => setBank(i, "interest_rate", e.target.value)} className="rounded-md" data-testid={`bank-rate-${i}`} />
                      </Box>
                      <Box className="col-span-2">
                        <Input type="number" min={1} value={b.priority} onChange={(e) => setBank(i, "priority", e.target.value)} className="rounded-md" data-testid={`bank-priority-${i}`} />
                      </Box>
                      <Box className="col-span-1 flex justify-end">
                        <Button variant="ghost" size="sm" onClick={() => removeBankRow(i)} data-testid={`remove-bank-${i}`} className="text-red-600 hover:bg-red-50 px-2">
                          <X className="h-4 w-4" />
                        </Button>
                      </Box>
                    </Box>
                  ))}
                  <Typography variant="inherit" component="p" className="text-[11px] text-muted-foreground pt-1">Lower priority number = selected first during auto-selection.</Typography>
                </Box>
              )}
            </Box>
          </Box>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} data-testid="cancel-school-btn">Cancel</Button>
            <Button onClick={save} disabled={saving} data-testid="save-school-btn" className="bg-brand-blue hover:bg-brand-navy">
              {saving ? "Saving…" : (<><Save className="h-4 w-4 mr-2" /> Save School</>)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
