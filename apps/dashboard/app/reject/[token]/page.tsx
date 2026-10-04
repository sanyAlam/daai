import { PublicDecisionPage } from '@/components/public-decision-page';

export default async function RejectTokenPage(
  props: {
    params: Promise<{ token: string }>;
  }
) {
  const params = await props.params;
  return <PublicDecisionPage decision="reject" token={params.token} />;
}
