'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from "@/context/AuthContext";
import { Logo } from "@/components/Logo";
import {
  LayoutDashboard, Wallet, GraduationCap, Users, Settings, LogOut, School, UserCog, Landmark, Bell, Building2, AlertTriangle, MailWarning,
} from "lucide-react";

const ADMIN_NAV = [
  { to: "/dashboard", label: "Analytics", icon: LayoutDashboard, testid: "nav-analytics" },
  { to: "/dashboard/fees", label: "Fee Structure", icon: Wallet, testid: "nav-fees" },
  { to: "/dashboard/students", label: "Students", icon: Users, testid: "nav-students" },
  { to: "/dashboard/reminders", label: "Fee Reminders", icon: Bell, testid: "nav-reminders" },
  { to: "/dashboard/team", label: "Team", icon: UserCog, testid: "nav-team" },
  { to: "/credit", label: "Fee Financing", icon: Landmark, testid: "nav-credit" },
  { to: "/dashboard/onboarding", label: "School Setup", icon: School, testid: "nav-onboarding" },
];

export function DashboardLayout({ children, title }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  // Biglyp Ops / Credit Ops manage the financing-bank config right here in the console.
  const isOps = ["super_admin", "credit_ops"].includes(user?.role);
  const nav = isOps
    ? [
        ...ADMIN_NAV.slice(0, 6),
        { to: "/dashboard/financing-banks", label: "Financing Banks", icon: Building2, testid: "nav-financing-banks" },
        { to: "/dashboard/schools", label: "Schools", icon: GraduationCap, testid: "nav-schools" },
        { to: "/dashboard/failures", label: "Failures", icon: AlertTriangle, testid: "nav-failures" },
        { to: "/dashboard/notifications", label: "Notifications", icon: MailWarning, testid: "nav-notifications" },
        ...ADMIN_NAV.slice(6),
      ]
    : ADMIN_NAV;

  return (
    <Box className="min-h-screen flex bg-slate-50">
      {/* Sidebar */}
      <Box component="aside" className="w-64 shrink-0 bg-brand-navy text-white flex-col hidden md:flex sticky top-0 h-screen">
        <Box className="p-6 border-b border-white/10">
          <Box className="flex items-center gap-2">
            <Box className="h-9 w-9 rounded-xl bg-white/95 flex items-center justify-center">
              <School className="h-5 w-5" style={{ color: "#5548D1" }} />
            </Box>
            <Box>
              <Typography variant="inherit" component="p" className="font-head font-extrabold text-white leading-none text-lg">Biglyp</Typography>
              <Typography variant="inherit" component="p" className="text-[10px] tracking-[0.25em] uppercase text-white/50 mt-1">Institute Console</Typography>
            </Box>
          </Box>
        </Box>
        <Box component="nav" className="flex-1 p-3 space-y-1">
          {nav.map((item) => {
            const active = pathname === item.to;
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                href={item.to}
                data-testid={item.testid}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-full text-[13px] font-semibold transition-colors ${
                  active
                    ? "bg-brand-blue text-white shadow-md shadow-black/20"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </Box>
        <Box className="p-4 border-t border-white/10">
          <Box className="px-2 mb-3 flex items-center gap-2.5">
            <Box className="h-8 w-8 rounded-full bg-brand-blue flex items-center justify-center font-head font-bold text-sm">
              {user?.name?.[0] || "U"}
            </Box>
            <Box className="min-w-0">
              <Typography variant="inherit" component="p" className="text-sm font-semibold truncate">{user?.name}</Typography>
              <Typography variant="inherit" component="p" className="text-[11px] text-white/50 capitalize">{user?.role?.replace("_", " ")}</Typography>
            </Box>
          </Box>
          <Box component="button"
            data-testid="logout-btn"
            onClick={() => { logout(); router.push("/login"); }}
            className="flex items-center gap-2 px-4 py-2 w-full rounded-full text-[13px] text-white/70 hover:bg-white/10 hover:text-white transition-colors"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </Box>
        </Box>
      </Box>

      {/* Main */}
      <Box className="flex-1 min-w-0">
        <Box component="header" className="h-16 bg-white border-b border-border flex items-center justify-between px-6 sticky top-0 z-10">
          <Typography variant="inherit" component="h1" className="font-head text-xl font-black tracking-tight text-brand-navy" data-testid="page-title">
            {title}
          </Typography>
          <Box className="flex items-center gap-3">
            <Box component="span" className="text-[11px] px-3 py-1.5 rounded-full bg-brand-tint text-brand-blue font-bold uppercase tracking-widest">
              AY 2025-26
            </Box>
            <Box className="h-9 w-9 rounded-full bg-brand-blue text-white flex items-center justify-center text-sm font-bold">
              {user?.name?.[0] || "U"}
            </Box>
          </Box>
        </Box>
        <Box component="main" className="p-6">{children}</Box>
      </Box>
    </Box>
  );
}
