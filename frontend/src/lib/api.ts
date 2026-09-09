import type {
  Assignment,
  ConstructionObject,
  CreatedUserResponse,
  DocKind,
  ObjectFile,
  ObjectStatus,
  ResetPasswordResponse,
  Section,
  SourceItem,
  TokenResponse,
  User,
} from "./types";

/**
 * API-клиент с прозрачным refresh-механизмом.
 * access-токен хранится в памяти (переменная модуля), refresh — в httpOnly cookie.
 */

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function refreshSession(): Promise<boolean> {
  const resp = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
  if (!resp.ok) {
    setAccessToken(null);
    return false;
  }
  const data = (await resp.json()) as TokenResponse;
  setAccessToken(data.access_token);
  return true;
}

async function request<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  const resp = await fetch(`/api/v1${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (resp.status === 401 && !retried) {
    const ok = await refreshSession();
    if (ok) return request<T>(path, init, true);
  }

  if (!resp.ok) {
    let detail = `Ошибка ${resp.status}`;
    try {
      const body = await resp.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ---------- Auth ----------
export const authApi = {
  async login(email: string, password: string): Promise<User> {
    const data = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    return data.user;
  },

  me: () => request<User>("/auth/me"),

  async logout(): Promise<void> {
    try {
      await request<void>("/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
    }
  },

  async bootstrap(): Promise<User | null> {
    // Пытаемся восстановить сессию по refresh-cookie, затем получить профиль
    if (!accessToken) {
      const ok = await refreshSession();
      if (!ok) return null;
    }
    try {
      return await authApi.me();
    } catch {
      setAccessToken(null);
      return null;
    }
  },
};

// ---------- Objects ----------
export interface ObjectPayload {
  name: string;
  code?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: ObjectStatus;
}

export const objectsApi = {
  list: (params?: { q?: string; status?: ObjectStatus }) => {
    const query = new URLSearchParams();
    if (params?.q) query.set("q", params.q);
    if (params?.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ConstructionObject[]>(`/objects${qs ? `?${qs}` : ""}`);
  },
  get: (id: number) => request<ConstructionObject>(`/objects/${id}`),
  create: (payload: ObjectPayload) =>
    request<ConstructionObject>("/objects", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: Partial<ObjectPayload>) =>
    request<ConstructionObject>(`/objects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  listAssignments: (id: number) => request<Assignment[]>(`/objects/${id}/assignments`),
  addAssignment: (id: number, userId: number) =>
    request<Assignment>(`/objects/${id}/assignments`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
  removeAssignment: (id: number, userId: number) =>
    request<void>(`/objects/${id}/assignments/${userId}`, { method: "DELETE" }),
};

// ---------- Files & Items (Спринт 2) ----------
export const filesApi = {
  list: (objectId: number) => request<ObjectFile[]>(`/objects/${objectId}/files`),

  async upload(objectId: number, kind: DocKind, file: File, sectionId?: number): Promise<ObjectFile> {
    const fd = new FormData();
    fd.append("kind", kind);
    if (sectionId) fd.append("section_id", String(sectionId));
    fd.append("file", file);

    const doFetch = (token?: string | null) => {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      return fetch(`/api/v1/objects/${objectId}/files`, {
        method: "POST",
        headers,
        body: fd,
        credentials: "include",
      });
    };

    let resp = await doFetch(accessToken);
    if (resp.status === 401) {
      const ok = await refreshSession();
      if (ok) resp = await doFetch(accessToken);
    }
    if (!resp.ok) {
      let detail = `Ошибка ${resp.status}`;
      try {
        const body = await resp.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* не JSON */
      }
      throw new ApiError(resp.status, detail);
    }
    return (await resp.json()) as ObjectFile;
  },

  parse: (objectId: number, fileId: number) =>
    request<ObjectFile>(`/objects/${objectId}/files/${fileId}/parse`, { method: "POST" }),

  remove: (objectId: number, fileId: number) =>
    request<void>(`/objects/${objectId}/files/${fileId}`, { method: "DELETE" }),

  move: (objectId: number, fileId: number, sectionId: number | null) =>
    request<ObjectFile>(`/objects/${objectId}/files/${fileId}`, {
      method: "PATCH",
      body: JSON.stringify({ section_id: sectionId }),
    }),

  async download(objectId: number, file: ObjectFile): Promise<void> {
    const headers: Record<string, string> = {};
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    const resp = await fetch(`/api/v1/objects/${objectId}/files/${file.id}/download`, {
      headers,
      credentials: "include",
    });
    if (!resp.ok) throw new ApiError(resp.status, `Ошибка ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.original_filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const sectionsApi = {
  list: (objectId: number) => request<Section[]>(`/objects/${objectId}/sections`),
  create: (objectId: number, payload: { code: string; name?: string; sort_order?: number }) =>
    request<Section>(`/objects/${objectId}/sections`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  remove: (objectId: number, sectionId: number) =>
    request<void>(`/objects/${objectId}/sections/${sectionId}`, { method: "DELETE" }),
};

export interface ItemFilters {
  section?: number;
  tracked?: boolean;
  source_file?: number;
}

export const itemsApi = {
  list: (objectId: number, filters?: ItemFilters) => {
    const query = new URLSearchParams();
    if (filters?.section) query.set("section", String(filters.section));
    if (filters?.tracked !== undefined) query.set("tracked", String(filters.tracked));
    if (filters?.source_file) query.set("source_file", String(filters.source_file));
    const qs = query.toString();
    return request<SourceItem[]>(`/objects/${objectId}/items${qs ? `?${qs}` : ""}`);
  },
  update: (objectId: number, itemId: number, patch: Record<string, unknown>) =>
    request<SourceItem>(`/objects/${objectId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  setTracked: (objectId: number, payload: { tracked: boolean; section_id?: number; ids?: number[] }) =>
    request<{ updated: number }>(`/objects/${objectId}/items/set-tracked`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ---------- Users ----------
export interface UserPayload {
  email: string;
  full_name: string;
  role: User["role"];
}

export const usersApi = {
  list: () => request<User[]>("/users"),
  create: (payload: UserPayload) =>
    request<CreatedUserResponse>("/users", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: { full_name?: string; role?: string; is_active?: boolean }) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  resetPassword: (id: number) =>
    request<ResetPasswordResponse>(`/users/${id}/reset-password`, { method: "POST" }),
};
