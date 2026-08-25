// proxy.ts (NOT middleware.ts — Next.js 16 renamed this file per D-03)
// Runtime: nodejs (edge NOT supported for jose JWT verify)
import { type NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

/* Посредника next-intl здесь нет намеренно.
 *
 * `localePrefix: "never"` и в приложении нет сегмента [locale] — маршруты
 * лежат в группах (auth) и (dashboard). Посредник переписывал бы /login
 * в /ro/login, чего в дереве маршрутов не существует, и отдавал 404.
 * Локаль приходит из src/i18n/request.ts, посредник для неё не нужен.
 *
 * Раньше это не проявлялось: файл лежал в корне проекта, а Next ищет его
 * рядом с app/, то есть в src/. Он не запускался ни разу — вместе с
 * проверкой токена. */

const PUBLIC_PATHS = ["/login", "/api/v1/auth", "/api"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip auth check for public paths and static assets
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (isPublic) {
    return NextResponse.next();
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

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
