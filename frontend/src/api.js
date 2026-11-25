const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api").replace(
  /\/$/,
  "",
);

export function getAuthToken() {
  return localStorage.getItem("access_token");
}

export function getActiveUser() {
  const user = localStorage.getItem("active_user");
  try {
    return user ? JSON.parse(user) : null;
  } catch {
    localStorage.removeItem("active_user");
    return null;
  }
}

export async function fetchApi(endpoint, options = {}) {
  const { responseType, ...requestOptions } = options;
  const token = getAuthToken();
  const headers = {
    ...(options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...requestOptions,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("active_user");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail.map((item) => item.msg).join("; ")
        : detail || `Request failed (${response.status})`,
    );
  }

  // Handle cases where response has no body (e.g. 204 No Content or empty)
  if (response.status === 204) {
    return null;
  }

  if (responseType === "blob") return response.blob();
  const data = await response.json();
  return responseType === "page"
    ? { data, nextOffset: response.headers.get("X-Next-Offset") }
    : data;
}

export async function loginApi(email, password) {
  const data = await fetchApi("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (data && data.access_token) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("active_user", JSON.stringify(data.user));
    return data.user;
  }
  throw new Error("Invalid response from server");
}

export function logoutApi() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("active_user");
  window.location.href = "/login";
}

export async function fetchAllApi(endpoint) {
  const items = [];
  let offset = 0;
  for (;;) {
    const separator = endpoint.includes("?") ? "&" : "?";
    const page = await fetchApi(
      `${endpoint}${separator}limit=500&offset=${offset}`,
      { responseType: "page" },
    );
    items.push(...page.data);
    if (page.nextOffset === null) return items;
    if (items.length >= 5000)
      throw new Error(
        "This collection exceeds the console's 5000-record limit; use API pagination.",
      );
    offset = Number(page.nextOffset);
  }
}
