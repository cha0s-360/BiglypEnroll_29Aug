'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, FilePlus2, FolderKanban, SlidersHorizontal, LogOut,
  ArrowLeft, Landmark, ShieldCheck,
} from "lucide-react";

export function CreditLayout({ children, title, subtitle }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isLender = user?.role === "lender";
  const isAdmin = ["super_admin", "credit_ops"].includes(user?.role);

  const nav = [
    { to: "/credit", label: "Dashboard", icon: LayoutDashboard, testid: "cnav-dashboard" },
    { to: "/credit/applications", label: "Applications", icon: FolderKanban, testid: "cnav-apps" },
    ...(!isLender ? [{ to: "/credit/new", label: "New Application", icon: FilePlus2, testid: "cnav-new" }] : []),
    ...(isAdmin ? [{ to: "/credit/policies", label: "Lender Policies", icon: SlidersHorizontal, testid: "cnav-policies" }] : []),
    ...(isAdmin ? [{ to: "/credit/banks", label: "Financing Banks", icon: Landmark, testid: "cnav-banks" }] : []),
  ];

  return (
    <Box className="min-h-screen flex bg-slate-50">
      <Box component="aside" className="w-64 shrink-0 bg-brand-navy text-white flex-col hidden md:flex sticky top-0 h-screen">
        <Box className="p-6 border-b border-white/10">
          <Box className="flex items-center gap-2">
            <Box className="h-9 w-9 rounded-xl bg-white/95 flex items-center justify-center">
              <Landmark className="h-5 w-5" style={{ color: "#5548D1" }} />
            </Box>
            <Box>
              <Typography variant="inherit" component="p" className="font-head font-extrabold leading-none text-lg">Biglyp</Typography>
              <Typography variant="inherit" component="p" className="text-[10px] tracking-[0.25em] uppercase text-white/50 mt-1">Credit Engine</Typography>
            </Box>
          </Box>
        </Box>
        <Box component="nav" className="flex-1 p-3 space-y-1">
          {nav.map((item) => {
            const active = pathname === item.to;
            const Icon = item.icon;
            return (
              <Link key={item.to} href={item.to} data-testid={item.testid}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-full text-[13px] font-semibold transition-colors ${
                  active ? "bg-brand-blue text-white shadow-md shadow-black/20" : "text-white/70 hover:bg-white/10 hover:text-white"}`}>
                <Icon className="h-4 w-4" /> {item.label}
              </Link>
            );
          })}
          {!isLender && (
            <Link href="/dashboard" data-testid="cnav-back"
              className="flex items-center gap-3 px-4 py-2.5 rounded-full text-[13px] font-semibold text-white/50 hover:bg-white/10 hover:text-white transition-colors mt-4">
              <ArrowLeft className="h-4 w-4" /> School Console
            </Link>
          )}
        </Box>
        <Box className="p-4 border-t border-white/10">
          <Box className="px-2 mb-3 flex items-center gap-2.5">
            <Box className="h-8 w-8 rounded-full bg-brand-blue flex items-center justify-center font-head font-bold text-sm">
              {user?.name?.[0] || "U"}
            </Box>
            <Box className="min-w-0">
              <Typography variant="inherit" component="p" className="text-sm font-semibold truncate">{user?.name}</Typography>
              <Typography variant="inherit" component="p" className="text-[11px] text-white/50 capitalize flex items-center gap-1">
                {isLender && <ShieldCheck className="h-3 w-3" />}{user?.role?.replace("_", " ")}
              </Typography>
            </Box>
          </Box>
          <Box component="button" data-testid="credit-logout" onClick={() => { logout(); router.push("/login"); }}
            className="flex items-center gap-2 px-4 py-2 w-full rounded-full text-[13px] text-white/70 hover:bg-white/10 hover:text-white transition-colors">
            <LogOut className="h-4 w-4" /> Sign out
          </Box>
        </Box>
      </Box>

      <Box className="flex-1 min-w-0">
        <Box component="header" className="min-h-16 bg-white border-b border-border flex items-center justify-between px-6 py-3 sticky top-0 z-10">
          <Box>
            <Typography variant="inherit" component="h1" className="font-head text-xl font-black tracking-tight text-brand-navy" data-testid="credit-page-title">{title}</Typography>
            {subtitle && <Typography variant="inherit" component="p" className="text-xs text-muted-foreground mt-0.5">{subtitle}</Typography>}
          </Box>
          <Box component="span" className="text-[11px] px-3 py-1.5 rounded-full bg-brand-tint text-brand-blue font-bold uppercase tracking-widest">RBI DLG · DPDP compliant</Box>
        </Box>
        <Box component="main" className="p-6">{children}</Box>
      </Box>
    </Box>
  );
}
