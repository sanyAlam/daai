import { redirect } from 'next/navigation';

export default function DashboardCompatRedirectPage() {
  redirect('/home');
}
