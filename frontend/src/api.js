const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

export function getAuthToken() {
  return localStorage.getItem("access_token");
}

export function getActiveUser() {
  const user = localStorage.getItem("active_user");
  try { return user ? JSON.parse(user) : null; } catch { localStorage.removeItem("active_user"); return null; }
}

export async function fetchApi(endpoint, options = {}) {
  const { responseType, ...requestOptions } = options;
  const token = getAuthToken();
  const headers = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
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
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail || `Request failed (${response.status})`);
  }

  // Handle cases where response has no body (e.g. 204 No Content or empty)
  if (response.status === 204) {
    return null;
  }

  return responseType === "blob" ? response.blob() : response.json();
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
