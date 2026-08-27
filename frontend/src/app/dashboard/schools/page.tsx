import { ProtectedRoute } from '@/components/ProtectedRoute';
import { DashboardLayout } from '@/components/DashboardLayout';
import SchoolFinancing from '@/screens/credit/SchoolFinancing';
import { POLICY_ROLES } from '@/lib/roles';
export default function Page() {
  return (
    <ProtectedRoute roles={POLICY_ROLES}>
      <DashboardLayout title="Schools">
        <SchoolFinancing />
      </DashboardLayout>
    </ProtectedRoute>
  );
}
