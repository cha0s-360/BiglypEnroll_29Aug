import { ProtectedRoute } from '@/components/ProtectedRoute';
import FinancingBanks from '@/screens/credit/FinancingBanks';
import { POLICY_ROLES } from '@/lib/roles';
export default function Page() { return <ProtectedRoute roles={POLICY_ROLES}><FinancingBanks /></ProtectedRoute>; }
