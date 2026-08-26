/**
 * Вход в портал — против учётной записи движка.
 *
 * Браузер сюда, кабинет в движок, печенье обратно на свой домен. Так область
 * печенья не приходится расширять до общего домена второго уровня и не
 * приходится ослаблять SameSite ради кросс-доменного запроса: снаружи это
 * обычная форма на своём сайте, а разговор с движком идёт со стороны сервера.
 *
 * Значение печенья то же самое, что выдал движок: это его сессия, мы её не
 * переподписываем и не заводим свою. Отзыв в движке действует немедленно —
 * следующий же запрос получит 401.
 *
 * Лежит вне /api намеренно: там rewrite отправляет всё в бэкенд аналитика.
 */
import { NextResponse } from "next/server";
import { ENGINE_SESSION_COOKIE, engineBaseUrl } from "@/lib/engine";

// Совпадает с SESSION_TTL_DAYS движка. Разойдётся — ничего не сломается:
// печенье, пережившее сессию, получит 401 и приведёт человека ко входу.
const SESSION_TTL_SECONDS = 14 * 24 * 60 * 60;

function cookieOptions() {
  return {
    httpOnly: true,
    sameSite: "strict" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
  };
}

/** Достать значение сессии из ответа движка, не доверяя порядку заголовков. */
function sessionFrom(setCookies: string[]): string | null {
  for (const raw of setCookies) {
    const [pair] = raw.split(";");
    if (!pair) continue;
    const eq = pair.indexOf("=");
    if (eq === -1) continue;
    if (pair.slice(0, eq).trim() !== ENGINE_SESSION_COOKIE) continue;
    const value = pair.slice(eq + 1).trim();
    return value.length > 0 ? value : null;
  }
  return null;
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const { email, password } = (body ?? {}) as { email?: unknown; password?: unknown };
  if (typeof email !== "string" || typeof password !== "string" || !email || !password) {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const response = await fetch(`${engineBaseUrl()}/admin/api/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (response.status === 401) {
    return NextResponse.json({ error: "invalid_credentials" }, { status: 401 });
  }
  if (!response.ok) {
    return NextResponse.json({ error: "engine_unavailable" }, { status: 502 });
  }

  const token = sessionFrom(response.headers.getSetCookie());
  if (!token) {
    // Движок ответил «вошёл», но сессии не дал. Пускать в этом случае нельзя:
    // следующий запрос всё равно получит 401, а человек будет думать, что вошёл.
    return NextResponse.json({ error: "engine_unavailable" }, { status: 502 });
  }

  const ok = NextResponse.json({ ok: true });
  ok.cookies.set(ENGINE_SESSION_COOKIE, token, {
    ...cookieOptions(),
    maxAge: SESSION_TTL_SECONDS,
  });
  return ok;
}

export async function DELETE(request: Request): Promise<NextResponse> {
  const token = request.headers
    .get("cookie")
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${ENGINE_SESSION_COOKIE}=`))
    ?.slice(ENGINE_SESSION_COOKIE.length + 1);

  if (token) {
    // Сессию гасим в движке, а не только у себя: иначе украденное печенье
    // продолжает работать после выхода.
    await fetch(`${engineBaseUrl()}/admin/api/logout`, {
      method: "POST",
      headers: { cookie: `${ENGINE_SESSION_COOKIE}=${token}` },
    }).catch(() => undefined);
  }

  const done = NextResponse.json({ ok: true });
  done.cookies.set(ENGINE_SESSION_COOKIE, "", { ...cookieOptions(), maxAge: 0 });
  return done;
}
