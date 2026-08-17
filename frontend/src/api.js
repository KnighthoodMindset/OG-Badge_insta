const API_BASE =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export function getToken() {
  return localStorage.getItem("token") || "";
}

export function setToken(token) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
}

export function fileUrl(pathOrUrl) {
  if (!pathOrUrl) return "";
  if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://"))
    return pathOrUrl;
  if (pathOrUrl.startsWith("/")) return `${API_BASE}${pathOrUrl}`;
  return `${API_BASE}/${pathOrUrl}`;
}

async function parseRes(res) {
  const ct = res.headers.get("content-type") || "";
  const isJson = ct.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const msg =
      (data &&
        data.detail &&
        (typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail))) ||
      (typeof data === "string" ? data : "Request failed");
    throw new Error(msg);
  }

  return data;
}

export async function apiGet(path, token = "") {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  return parseRes(res);
}

export async function apiPostJson(path, body, token = "") {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  return parseRes(res);
}

export async function apiPutJson(path, body, token = "") {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  return parseRes(res);
}

export async function apiPostForm(path, formData, token = "") {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });
  return parseRes(res);
}

export async function apiDelete(path, token = "") {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  return parseRes(res);
}

export const api = {
  register: (payload) => apiPostJson("/api/auth/register", payload),
  login: (payload) => apiPostJson("/api/auth/login", payload),
  me: (token) => apiGet("/api/auth/me", token),

  badgeStatus: (token) => apiGet("/api/badge/status", token),
  applyBadge: (payload, token) => apiPostJson("/api/badge/apply", payload, token),

  // ✅ posts
  feed: (token) => apiGet("/api/feed?limit=50&offset=0", token),
  myPosts: (token) => apiGet("/api/me/posts?limit=50&offset=0", token),
  deletePost: (postId, token) => apiDelete(`/api/posts/${postId}`, token),

  // ✅ edit caption
  editPostCaption: (postId, caption, token) =>
    apiPutJson(`/api/posts/${postId}`, { caption }, token),
};
