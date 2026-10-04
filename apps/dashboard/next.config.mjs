/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_DAAI_SUPABASE_URL: process.env.DAAI_SUPABASE_URL,
    NEXT_PUBLIC_DAAI_SUPABASE_ANON_KEY: process.env.DAAI_SUPABASE_ANON_KEY,
  },
};

export default nextConfig;
