const API_BASE_URL = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

export function getAuthToken() {
  return localStorage.getItem("access_token");
}

export function getActiveUser() {
  const user = localStorage.getItem("active_user");
  return user ? JSON.parse(user) : null;
}

export async function fetchApi(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
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
    throw new Error(errorData.detail || "Something went wrong");
  }

  // Handle cases where response has no body (e.g. 204 No Content or empty)
  if (response.status === 204) {
    return null;
  }

  return response.json();
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
