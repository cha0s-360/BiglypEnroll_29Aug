'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useEffect, useMemo, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  Bell, Mail, MessageSquare, Save, Loader2, Play, Clock, Info,
  Code2, CheckCircle2, Ban, ChevronRight,
} from "lucide-react";

const VARIABLES = ["parent_name", "student_name", "emi_amount", "due_date", "school_name"];

export default function Notifications() {
  const [list, setList] = useState<any[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [runDay, setRunDay] = useState<string>("10");
  const [jobResult, setJobResult] = useState<any>(null);

  useEffect(() => {
    api.get("/ops/notifications").then(({ data }) => {
      setList(data);
      if (data[0]) { setSelectedType(data[0].type); setCfg(structuredClone(data[0])); }
    }).catch((e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail)));
  }, []);

  const selectType = (t: string) => {
    const found = list.find((n) => n.type === t);
    if (found) { setSelectedType(t); setCfg(structuredClone(found)); setJobResult(null); }
  };

  const setEmail = (patch: any) => setCfg((c: any) => ({ ...c, email: { ...c.email, ...patch } }));
  const setSms = (patch: any) => setCfg((c: any) => ({ ...c, sms: { ...c.sms, ...patch } }));

  const save = async () => {
    if (!cfg) return;
    setSaving(true);
    try {
      const { data } = await api.put(`/ops/notifications/${cfg.type}`, {
        name: cfg.name, description: cfg.description, email: cfg.email, sms: cfg.sms,
      });
      setList((l) => l.map((n) => (n.type === data.type ? data : n)));
      setCfg(structuredClone(data));
      toast.success("Notification config saved");
    } catch (e: any) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setSaving(false); }
  };

  const runJob = async () => {
    if (!cfg) return;
    setRunning(true);
    setJobResult(null);
    try {
      const dayNum = runDay === "" ? undefined : Number(runDay);
      const { data } = await api.post(`/ops/notifications/${cfg.type}/run`,
        dayNum === undefined ? {} : { run_day: dayNum });
      setJobResult(data);
      if (data.ran) toast.success(`Job ran — ${data.sends.length} recipient(s)`);
      else toast(`Job skipped — ${data.reason}`);
    } catch (e: any) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setRunning(false); }
  };

  const bothDisabled = cfg && !cfg.email?.enabled && !cfg.sms?.enabled;

  if (!cfg) {
    return <Box className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-brand-blue" /></Box>;
  }

  return (
    <Box className="space-y-6" data-testid="notifications-screen">
      {/* Header */}
      <Box className="flex items-start gap-3">
        <Box className="h-11 w-11 rounded-2xl bg-[#EEF0FF] text-[#5548D1] flex items-center justify-center shrink-0">
          <Bell className="h-5 w-5" />
        </Box>
        <Box>
          <Typography variant="inherit" component="h2" className="font-head text-2xl font-black tracking-tight text-brand-navy leading-tight">
            Notifications
          </Typography>
          <Typography variant="inherit" component="p" className="text-sm text-slate-500 mt-0.5 max-w-2xl">
            Configure every automated message the system sends. Toggle Email &amp; SMS independently per notification.
          </Typography>
        </Box>
      </Box>

      <Box className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Left — notification type list */}
        <Box className="space-y-2" data-testid="notification-list">
          <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-[0.14em] text-slate-400 font-bold px-1">Notification types</Typography>
          {list.map((n) => {
            const active = n.type === selectedType;
            return (
              <Box component="button" key={n.type} data-testid={`notif-type-${n.type}`}
                onClick={() => selectType(n.type)}
                className={`w-full text-left rounded-2xl border-2 p-4 transition-all ${
                  active ? "border-[#5548D1] bg-white soft-shadow-lg" : "border-transparent bg-white soft-shadow hover:border-slate-200"
                }`}>
                <Box className="flex items-center justify-between">
                  <Typography variant="inherit" component="p" className="font-bold text-brand-navy text-sm">{n.name}</Typography>
                  <ChevronRight className={`h-4 w-4 ${active ? "text-[#5548D1]" : "text-slate-300"}`} />
                </Box>
                <Box className="mt-2 flex gap-1.5">
                  <Box component="span" className={`text-[10px] font-bold uppercase tracking-wide rounded-full px-2 py-0.5 ${n.email?.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400"}`}>Email {n.email?.enabled ? "on" : "off"}</Box>
                  <Box component="span" className={`text-[10px] font-bold uppercase tracking-wide rounded-full px-2 py-0.5 ${n.sms?.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400"}`}>SMS {n.sms?.enabled ? "on" : "off"}</Box>
                </Box>
              </Box>
            );
          })}
        </Box>

        {/* Right — edit form */}
        <Box className="space-y-5" data-testid="notification-editor">
          <Box>
            <Typography variant="inherit" component="p" className="font-head text-lg font-black text-brand-navy">{cfg.name}</Typography>
            <Typography variant="inherit" component="p" className="text-xs text-slate-500">{cfg.description}</Typography>
          </Box>

          {/* Available variables reference */}
          <Box className="rounded-xl bg-slate-50 border border-border/70 p-3">
            <Typography variant="inherit" component="p" className="text-[11px] uppercase tracking-wider text-slate-500 font-bold flex items-center gap-1.5 mb-2">
              <Code2 className="h-3.5 w-3.5" /> Available variables
            </Typography>
            <Box className="flex flex-wrap gap-1.5">
              {VARIABLES.map((v) => (
                <Box component="code" key={v} className="text-[11px] font-mono bg-white border border-border rounded-md px-2 py-1 text-[#5548D1]">{`{{${v}}}`}</Box>
              ))}
            </Box>
          </Box>

          {/* EMAIL block */}
          <Box className="rounded-2xl border border-border bg-white soft-shadow overflow-hidden" data-testid="email-block">
            <Box className="flex items-center justify-between gap-3 px-5 py-4 border-b border-border/70 bg-slate-50/60">
              <Box className="flex items-center gap-2.5">
                <Box className="h-9 w-9 rounded-xl bg-[#EEF0FF] text-[#5548D1] flex items-center justify-center"><Mail className="h-4 w-4" /></Box>
                <Box>
                  <Typography variant="inherit" component="p" className="font-bold text-brand-navy text-sm">Email</Typography>
                  <Typography variant="inherit" component="p" className="text-[11px] text-slate-400">Sent via email provider</Typography>
                </Box>
              </Box>
              <Box className="flex items-center gap-2">
                <Typography variant="inherit" component="span" className="text-[11px] font-semibold text-slate-500">{cfg.email?.enabled ? "Enabled" : "Disabled"}</Typography>
                <Switch checked={!!cfg.email?.enabled} onCheckedChange={(v: boolean) => setEmail({ enabled: v })} data-testid="email-toggle" />
              </Box>
            </Box>
            <Box className={`p-5 space-y-4 ${cfg.email?.enabled ? "" : "opacity-50 pointer-events-none"}`}>
              <Box className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Box>
                  <Label className="text-xs font-semibold text-slate-600">To</Label>
                  <Input value={cfg.email?.to || ""} onChange={(e: any) => setEmail({ to: e.target.value })} data-testid="email-to"
                    placeholder="{{parent_email}}" className="mt-1.5" />
                </Box>
                <Box>
                  <Label className="text-xs font-semibold text-slate-600">From</Label>
                  <Input value={cfg.email?.from_addr || ""} onChange={(e: any) => setEmail({ from_addr: e.target.value })} data-testid="email-from"
                    placeholder="fees@biglyp.com" className="mt-1.5" />
                </Box>
              </Box>
              <Box>
                <Label className="text-xs font-semibold text-slate-600">Subject</Label>
                <Input value={cfg.email?.subject || ""} onChange={(e: any) => setEmail({ subject: e.target.value })} data-testid="email-subject"
                  className="mt-1.5" />
              </Box>
              <Box>
                <Label className="text-xs font-semibold text-slate-600">HTML body</Label>
                <Textarea value={cfg.email?.body_html || ""} onChange={(e: any) => setEmail({ body_html: e.target.value })} data-testid="email-body"
                  rows={9} className="mt-1.5 font-mono text-[12.5px] leading-relaxed" />
                <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 mt-1.5">Supports HTML and {`{{variable}}`} placeholders.</Typography>
              </Box>
            </Box>
          </Box>

          {/* SMS block */}
          <Box className="rounded-2xl border border-border bg-white soft-shadow overflow-hidden" data-testid="sms-block">
            <Box className="flex items-center justify-between gap-3 px-5 py-4 border-b border-border/70 bg-slate-50/60">
              <Box className="flex items-center gap-2.5">
                <Box className="h-9 w-9 rounded-xl bg-[#EEF0FF] text-[#5548D1] flex items-center justify-center"><MessageSquare className="h-4 w-4" /></Box>
                <Box>
                  <Typography variant="inherit" component="p" className="font-bold text-brand-navy text-sm">SMS</Typography>
                  <Typography variant="inherit" component="p" className="text-[11px] text-slate-400">DLT-approved template — copy lives with the SMS provider</Typography>
                </Box>
              </Box>
              <Box className="flex items-center gap-2">
                <Typography variant="inherit" component="span" className="text-[11px] font-semibold text-slate-500">{cfg.sms?.enabled ? "Enabled" : "Disabled"}</Typography>
                <Switch checked={!!cfg.sms?.enabled} onCheckedChange={(v: boolean) => setSms({ enabled: v })} data-testid="sms-toggle" />
              </Box>
            </Box>
            <Box className={`p-5 ${cfg.sms?.enabled ? "" : "opacity-50 pointer-events-none"}`}>
              <Box className="max-w-sm">
                <Label className="text-xs font-semibold text-slate-600">Template ID</Label>
                <Input value={cfg.sms?.template_id || ""} onChange={(e: any) => setSms({ template_id: e.target.value })} data-testid="sms-template-id"
                  placeholder="1707160000000012345" className="mt-1.5 font-mono" />
                <Typography variant="inherit" component="p" className="text-[11px] text-slate-400 mt-1.5">The DLT-approved template identifier registered with your SMS provider.</Typography>
              </Box>
            </Box>
          </Box>

          {bothDisabled && (
            <Box className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 p-3">
              <Ban className="h-4 w-4 text-amber-600 shrink-0" />
              <Typography variant="inherit" component="span" className="text-[12px] text-amber-800">Both channels are disabled — the reminder job will skip this notification entirely.</Typography>
            </Box>
          )}

          <Box className="flex justify-end">
            <Button onClick={save} disabled={saving} data-testid="save-notification"
              className="h-11 px-6 rounded-xl bg-[#5548D1] hover:bg-[#3F35A8] text-white font-semibold">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />} Save configuration
            </Button>
          </Box>

          {/* Reminder job runner */}
          <Box className="rounded-2xl border border-border bg-white soft-shadow p-5 space-y-4" data-testid="job-runner">
            <Box className="flex items-start gap-2.5">
              <Box className="h-9 w-9 rounded-xl bg-brand-navy text-white flex items-center justify-center shrink-0"><Clock className="h-4 w-4" /></Box>
              <Box>
                <Typography variant="inherit" component="p" className="font-bold text-brand-navy text-sm">EMI reminder job</Typography>
                <Typography variant="inherit" component="p" className="text-[12px] text-slate-500 mt-0.5">
                  Fixed window: reminders go out on <b>day 5–24</b> of the cycle. From day 25 it&apos;s bank-led (out of scope). Uses a mock provider — sends are logged, not dispatched.
                </Typography>
              </Box>
            </Box>
            <Box className="flex flex-wrap items-end gap-3">
              <Box>
                <Label className="text-xs font-semibold text-slate-600">Simulate run on day-of-month</Label>
                <Input type="number" min={1} max={31} value={runDay} onChange={(e: any) => setRunDay(e.target.value)} data-testid="run-day"
                  className="mt-1.5 w-40" />
              </Box>
              <Button onClick={runJob} disabled={running} data-testid="run-job"
                className="h-11 px-6 rounded-xl bg-brand-navy hover:bg-brand-navy/90 text-white font-semibold">
                {running ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />} Run reminder job
              </Button>
            </Box>

            {/* Job result */}
            {jobResult && (
              <Box className="rounded-xl border border-border/70 bg-slate-50 p-4 space-y-3" data-testid="job-result">
                <Box className="flex items-center gap-2">
                  {jobResult.ran
                    ? <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    : <Ban className="h-4 w-4 text-amber-600" />}
                  <Typography variant="inherit" component="span" className="text-[12.5px] font-semibold text-brand-navy">
                    Day {jobResult.run_day} · window {jobResult.window?.start}–{jobResult.window?.end} · {jobResult.window_open ? "open" : "closed"}
                  </Typography>
                </Box>
                <Typography variant="inherit" component="p" className="text-[12px] text-slate-600 flex items-start gap-1.5">
                  <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-slate-400" />{jobResult.reason}
                </Typography>

                {jobResult.sends?.map((s: any, i: number) => (
                  <Box key={i} className="rounded-lg border border-border bg-white p-3" data-testid={`job-send-${i}`}>
                    <Typography variant="inherit" component="p" className="text-[12px] font-bold text-brand-navy">{s.recipient} · <span className="text-slate-400 font-normal">{s.application_id} · due {s.due_date}</span></Typography>
                    {s.channels.map((c: any, j: number) => (
                      <Box key={j} className="mt-2 rounded-md bg-slate-50 border border-border/70 p-2.5">
                        {c.channel === "email" ? (
                          <>
                            <Box component="span" className="inline-block text-[10px] font-bold uppercase tracking-wide bg-[#EEF0FF] text-[#5548D1] rounded px-1.5 py-0.5">Email</Box>
                            <Typography variant="inherit" component="p" className="text-[11.5px] text-slate-600 mt-1.5"><b>To:</b> {c.to || "(blank)"} · <b>From:</b> {c.from_addr}</Typography>
                            <Typography variant="inherit" component="p" className="text-[11.5px] text-slate-600"><b>Subject:</b> {c.subject}</Typography>
                            <Box className="mt-2 rounded bg-white border border-border/70 p-2 text-[12px] text-slate-700" dangerouslySetInnerHTML={{ __html: c.body_html }} />
                          </>
                        ) : (
                          <>
                            <Box component="span" className="inline-block text-[10px] font-bold uppercase tracking-wide bg-emerald-100 text-emerald-700 rounded px-1.5 py-0.5">SMS</Box>
                            <Typography variant="inherit" component="p" className="text-[11.5px] text-slate-600 mt-1.5"><b>To:</b> {c.to} · <b>Template ID:</b> <span className="font-mono">{c.template_id}</span></Typography>
                          </>
                        )}
                      </Box>
                    ))}
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
