import { ProtectedRoute } from '@/components/ProtectedRoute';
import { DashboardLayout } from '@/components/DashboardLayout';
import Notifications from '@/screens/admin/Notifications';
import { POLICY_ROLES } from '@/lib/roles';

export default function Page() {
  return (
    <ProtectedRoute roles={POLICY_ROLES}>
      <DashboardLayout title="Notifications">
        <Notifications />
      </DashboardLayout>
    </ProtectedRoute>
  );
}
