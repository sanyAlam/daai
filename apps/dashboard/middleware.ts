import { NextResponse, type NextRequest } from 'next/server';

import { updateSupabaseSession } from '@/lib/supabase/middleware';

const DEFAULT_DASHBOARD_BASE_URL = 'http://localhost:3000';
const DASHBOARD_HOST_FALLBACK = 'localhost';
const LANDING_HOSTS = new Set<string>();

function normalizeBaseUrl(value: string | undefined, fallback: string): string {
  const trimmed = value?.trim();
  const baseUrl = trimmed || fallback;
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

function dashboardBaseUrl(): string {
  return normalizeBaseUrl(process.env.DAAI_DASHBOARD_BASE_URL, DEFAULT_DASHBOARD_BASE_URL);
}

function dashboardHostname(): string {
  try {
    return new URL(dashboardBaseUrl()).hostname.toLowerCase();
  } catch {
    return DASHBOARD_HOST_FALLBACK;
  }
}

function isDashboardHost(hostname: string): boolean {
  const normalized = hostname.toLowerCase();
  return normalized === DASHBOARD_HOST_FALLBACK || normalized === dashboardHostname();
}

function isLandingHost(hostname: string): boolean {
  return LANDING_HOSTS.has(hostname.toLowerCase());
}

function forwardedValue(value: string | null): string | null {
  const firstValue = value?.split(',')[0]?.trim();
  return firstValue || null;
}

function hostnameFromHeader(value: string | null): string | null {
  const headerValue = forwardedValue(value);
  return headerValue?.split(':')[0]?.toLowerCase() || null;
}

function requestHostname(request: NextRequest): string {
  return (
    hostnameFromHeader(request.headers.get('x-forwarded-host')) ??
    hostnameFromHeader(request.headers.get('host')) ??
    request.nextUrl.hostname.toLowerCase()
  );
}

function publicRequestUrl(request: NextRequest): URL {
  const url = request.nextUrl.clone();
  const forwardedHost =
    hostnameFromHeader(request.headers.get('x-forwarded-host')) ??
    hostnameFromHeader(request.headers.get('host'));
  const forwardedProtocol = forwardedValue(request.headers.get('x-forwarded-proto'));

  if (forwardedHost) {
    url.hostname = forwardedHost;
    url.port = '';
  }

  if (forwardedProtocol) {
    url.protocol = `${forwardedProtocol}:`;
    if (forwardedProtocol === 'https' || forwardedProtocol === 'http') {
      url.port = '';
    }
  }

  return url;
}

function redirectWithSession(
  request: NextRequest,
  response: NextResponse,
  pathname: string,
): NextResponse {
  const url = publicRequestUrl(request);
  url.pathname = pathname;
  url.search = '';

  const redirectResponse = NextResponse.redirect(url);
  response.cookies.getAll().forEach((cookie) => {
    redirectResponse.cookies.set(cookie);
  });
  return redirectResponse;
}

function redirectToUrlWithSession(
  response: NextResponse,
  target: URL,
): NextResponse {
  const redirectResponse = NextResponse.redirect(target);
  response.cookies.getAll().forEach((cookie) => {
    redirectResponse.cookies.set(cookie);
  });
  return redirectResponse;
}

function isProtectedPath(pathname: string): boolean {
  return (
    pathname === '/home' ||
    pathname === '/admin' ||
    pathname === '/account' ||
    pathname.startsWith('/workspaces/') ||
    pathname === '/dashboard' ||
    (pathname.startsWith('/dashboard/') && pathname !== '/dashboard/documentation')
  );
}

export async function middleware(request: NextRequest) {
  const { response, user } = await updateSupabaseSession(request);
  const pathname = request.nextUrl.pathname;
  const hostname = requestHostname(request);

  const isAuthPath =
    pathname === '/login' || pathname === '/signup' || pathname === '/forgot-password';
  const protectedPath = isProtectedPath(pathname);

  if (hostname === 'www.daaihq.com') {
    const canonicalUrl = publicRequestUrl(request);
    canonicalUrl.hostname = 'daaihq.com';
    canonicalUrl.port = '';
    return redirectToUrlWithSession(response, canonicalUrl);
  }

  if (isLandingHost(hostname) && (isAuthPath || protectedPath)) {
    const dashboardUrl = new URL(dashboardBaseUrl());
    dashboardUrl.pathname = pathname;
    dashboardUrl.search = request.nextUrl.search;
    return redirectToUrlWithSession(response, dashboardUrl);
  }

  if (isDashboardHost(hostname) && pathname === '/') {
    return redirectWithSession(request, response, user ? '/home' : '/login');
  }

  if (!user && protectedPath) {
    return redirectWithSession(request, response, '/login');
  }

  if (user && isAuthPath) {
    return redirectWithSession(request, response, '/home');
  }

  return response;
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
