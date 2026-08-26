// proxy.ts (NOT middleware.ts — Next.js 16 renamed this file per D-03)
//
// Кабинет закрыт сессией движка. Своего токена у него больше нет: личность
// удостоверяет движок, а здесь только проверяется, что печенье вообще есть.
//
// Судить о самом токене отсюда нельзя и не нужно. Он непрозрачен — знает о
// нём только движок, — а запрос к движку на каждый переход по кабинету
// поставил бы движок на путь каждой страницы. Настоящая проверка стоит там,
// где берутся данные: бэкенд разбирает сессию на каждом запросе и отвечает
// 401, если она недействительна.
//
// Пускать сюда с недействительным печеньем безопасно: показать всё равно
// будет нечего.
import { type NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "aw_session";

/* Открытые пути. `/portal` — это вход и мост к движку: закрыть их проверкой
   сессии значило бы требовать сессию для того, чтобы её получить.

   Вывезено наружу не для чужого кода, а для проверки: расширение этого
   списка — единственный способ снять защиту с кабинета, не тронув ни строки
   логики ниже. Тест сверяет его состав и ломается на любой правке. */
export const PUBLIC_PATHS = ["/login", "/portal", "/api"] as const;

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  if (!request.cookies.get(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
