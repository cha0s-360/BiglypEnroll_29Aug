import { ProtectedRoute } from '@/components/ProtectedRoute';
import { DashboardLayout } from '@/components/DashboardLayout';
import Failures from '@/screens/admin/Failures';
import { POLICY_ROLES } from '@/lib/roles';

export default function Page() {
  return (
    <ProtectedRoute roles={POLICY_ROLES}>
      <DashboardLayout title="Failures">
        <Failures />
      </DashboardLayout>
    </ProtectedRoute>
  );
}
