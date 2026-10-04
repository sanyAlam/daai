type SupabaseConfig = {
  url: string;
  anonKey: string;
};

export function getSupabaseConfig(): SupabaseConfig {
  const url = process.env.DAAI_SUPABASE_URL;
  const anonKey = process.env.DAAI_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error(
      'Missing Supabase dashboard auth env vars. Set DAAI_SUPABASE_URL and DAAI_SUPABASE_ANON_KEY in apps/dashboard/.env.local.',
    );
  }

  return { url, anonKey };
}
