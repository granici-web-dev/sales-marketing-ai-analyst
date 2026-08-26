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

/* Разделы, которые удостоверяет движок, а не этот кабинет.
 *
 * Портал принадлежит учётной записи Davoq: что куплено, знает движок, и
 * токен аналитика об этом не говорит ничего. Требовать его здесь значило бы
 * закрыть портал от того, у кого есть ровно та учётная запись, которая для
 * портала и нужна.
 *
 * Проверка не переносится сюда, а остаётся там, где берутся данные. Токен
 * движка непрозрачен — судить о нём может только сам движок, и запрос к нему
 * на каждый переход по кабинету поставил бы движок на пути каждой страницы.
 * Без действующей сессии страница не покажет ни одного агента: она получит
 * 401 и нарисует форму входа. Пустить сюда без сессии нечего — показывать
 * там нечего. */
const ENGINE_AUTH_PATHS = ["/", "/agents", "/portal", "/subscription", "/settings"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip auth check for public paths and static assets
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (isPublic) {
    return NextResponse.next();
  }

  if (ENGINE_AUTH_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get("access_token")?.value;
  if (!accessToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  /* Отсутствующий секрет — это поломка настройки, а не неверный токен,
     и вести себя как неверный токен он не должен. `!` в
     `process.env.JWT_SECRET_KEY!` — утверждение TypeScript, оно ничего не
     проверяет: без переменной jwtVerify получал бы кодировку строки
     "undefined" и отвергал КАЖДЫЙ верный токен, отправляя человека на вход
     по кругу без единого объяснения. Ровно это и происходило, пока файл
     лежал не там и не исполнялся. */
  const rawSecret = process.env.JWT_SECRET_KEY;
  if (!rawSecret) {
    throw new Error(
      "JWT_SECRET_KEY не задан — проверить токен невозможно. " +
        "Смотрите frontend/.env.example: значение обязано совпадать с секретом бэкенда.",
    );
  }

  try {
    await jwtVerify(accessToken, new TextEncoder().encode(rawSecret));
  } catch {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
