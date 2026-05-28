/**
 * API client with 401 interceptor for transparent token refresh (D-02).
 * On 401: calls POST /api/v1/auth/refresh (refresh_token HttpOnly cookie sent automatically),
 * retries original request once. On second 401: clears access_token cookie, redirects to /login.
 *
 * Auth: backend expects Authorization: Bearer <access_token>. The token lives in a
 * non-HttpOnly access_token cookie (set by LoginForm + refresh handler); we read it
 * here and forward it as a Bearer header on every request.
 */

function readAccessToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function withAuthHeader(options?: RequestInit): RequestInit {
  const token = readAccessToken();
  if (!token) {
    return { ...options, credentials: "include" };
  }
  const headers = new Headers(options?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return { ...options, headers, credentials: "include" };
}

async function apiFetch(url: string, options?: RequestInit): Promise<Response> {
  const response = await fetch(url, withAuthHeader(options));

  if (response.status === 401) {
    // Attempt token refresh (D-02)
    const refreshResponse = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    });

    if (refreshResponse.ok) {
      const data = await refreshResponse.json();
      // Store new access token in non-HttpOnly cookie (proxy.ts reads it server-side)
      document.cookie = `access_token=${data.access_token}; path=/; SameSite=Lax`;

      // Retry original request with refreshed token in Authorization header
      return fetch(url, withAuthHeader(options));
    } else {
      // Refresh failed — clear access token and redirect to login
      document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
      window.location.href = "/login";
      // Return the original 401 response (redirect will happen before it's used)
      return response;
    }
  }

  return response;
}

export const apiClient = {
  get: (url: string) => apiFetch(url),
  post: (url: string, body: unknown) =>
    apiFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  put: (url: string, body: unknown) =>
    apiFetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  delete: (url: string) =>
    apiFetch(url, {
      method: "DELETE",
    }),
};
