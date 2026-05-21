/**
 * API client with 401 interceptor for transparent token refresh (D-02).
 * On 401: calls POST /api/v1/auth/refresh (refresh_token HttpOnly cookie sent automatically),
 * retries original request once. On second 401: clears access_token cookie, redirects to /login.
 */

async function apiFetch(url: string, options?: RequestInit): Promise<Response> {
  const response = await fetch(url, {
    ...options,
    credentials: "include", // send cookies automatically
  });

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

      // Retry original request with refreshed token
      return fetch(url, {
        ...options,
        credentials: "include",
      });
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
