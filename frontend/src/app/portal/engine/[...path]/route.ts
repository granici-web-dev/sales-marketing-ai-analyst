/**
 * Мост к API движка.
 *
 * Экраны агентов рисует портал, а данные для них лежат в движке. Ходить туда
 * из браузера напрямую нельзя по той же причине, что и при входе: печенье
 * сессии принадлежит домену портала, и отдавать его чужому origin значило бы
 * либо расширять его область, либо ослаблять SameSite. Поэтому запрос идёт
 * сюда, а отсюда — на сервер движка, с печеньем в заголовке.
 *
 * Префикс `/admin/api/` подставляется здесь и не приходит снаружи: адрес
 * собирается из пути, а всё, что похоже на выход за пределы, отвергается.
 * Мост, принимающий произвольный путь, — это доступ ко всему, что слушает
 * движок, включая то, что не предназначено клиенту.
 */
import { NextResponse } from "next/server";
import { ENGINE_SESSION_COOKIE, engineBaseUrl } from "@/lib/engine";

/** Сегмент пути: буквы, цифры, дефис, подчёркивание, точка. Ни слэшей, ни `..`. */
const SEGMENT = /^[A-Za-z0-9._-]+$/;

/** Заголовки, которые имеет смысл переносить в обе стороны. */
const CONTENT_HEADERS = ["content-type", "content-disposition", "content-length"];

async function forward(request: Request, path: string[]): Promise<Response> {
  if (path.length === 0 || !path.every((s) => SEGMENT.test(s) && s !== "..")) {
    return NextResponse.json({ error: "bad_path" }, { status: 404 });
  }

  const token = request.headers
    .get("cookie")
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${ENGINE_SESSION_COOKIE}=`))
    ?.slice(ENGINE_SESSION_COOKIE.length + 1);

  if (!token) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const query = new URL(request.url).search;
  const headers = new Headers({ cookie: `${ENGINE_SESSION_COOKIE}=${token}` });
  for (const name of CONTENT_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const response = await fetch(`${engineBaseUrl()}/admin/api/${path.join("/")}${query}`, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    // Права и настройки меняются нажатием кнопки. Кешированный ответ здесь —
    // это показанное старое состояние сразу после того, как его поменяли.
    cache: "no-store",
  });

  const out = new Headers();
  for (const name of CONTENT_HEADERS) {
    const value = response.headers.get(name);
    if (value) out.set(name, value);
  }
  return new Response(response.body, { status: response.status, headers: out });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, ctx: Ctx): Promise<Response> {
  return forward(request, (await ctx.params).path);
}
export async function POST(request: Request, ctx: Ctx): Promise<Response> {
  return forward(request, (await ctx.params).path);
}
export async function PATCH(request: Request, ctx: Ctx): Promise<Response> {
  return forward(request, (await ctx.params).path);
}
export async function PUT(request: Request, ctx: Ctx): Promise<Response> {
  return forward(request, (await ctx.params).path);
}
export async function DELETE(request: Request, ctx: Ctx): Promise<Response> {
  return forward(request, (await ctx.params).path);
}
