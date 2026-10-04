export type SupabaseUser = {
  id: string;
  email: string | null;
};

export type SupabaseSession = {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: SupabaseUser;
};

export type SupabaseAuthResult<T> = {
  data: T | null;
  error: string | null;
};
