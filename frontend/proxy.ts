// proxy.ts (NOT middleware.ts — Next.js 16 renamed this file per D-03)
// Runtime: nodejs (edge NOT supported for jose JWT verify)
import createMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";
import { routing } from "./src/i18n/routing";

const handleI18nRouting = createMiddleware(routing);

const PUBLIC_PATHS = ["/login", "/api/v1/auth", "/api"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip auth check for public paths and static assets
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (isPublic) {
    return handleI18nRouting(request);
  }

  const accessToken = request.cookies.get("access_token")?.value;
  if (!accessToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const secret = new TextEncoder().encode(process.env.JWT_SECRET_KEY!);
    await jwtVerify(accessToken, secret);
  } catch {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return handleI18nRouting(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
