import { PublicDecisionPage } from '@/components/public-decision-page';

export default async function ApproveTokenPage(
  props: {
    params: Promise<{ token: string }>;
  }
) {
  const params = await props.params;
  return <PublicDecisionPage decision="approve" token={params.token} />;
}
