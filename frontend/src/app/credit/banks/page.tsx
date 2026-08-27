import { ProtectedRoute } from '@/components/ProtectedRoute';
import { CreditLayout } from '@/components/CreditLayout';
import FinancingBanks from '@/screens/credit/FinancingBanks';
import { POLICY_ROLES } from '@/lib/roles';
export default function Page() {
  return (
    <ProtectedRoute roles={POLICY_ROLES}>
      <CreditLayout title="Financing Banks">
        <FinancingBanks />
      </CreditLayout>
    </ProtectedRoute>
  );
}
