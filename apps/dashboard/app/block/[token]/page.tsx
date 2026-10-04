import { PublicDecisionPage } from '@/components/public-decision-page';

export default async function BlockTokenPage(
  props: {
    params: Promise<{ token: string }>;
  }
) {
  const params = await props.params;
  return <PublicDecisionPage decision="block" token={params.token} />;
}
