import type {
  Act,
  ActType,
  Assignment,
  ConstructionObject,
  CreatedUserResponse,
  DashboardSummary,
  DocKind,
  IncomingDoc,
  ItemType,
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
  item_type?: ItemType;
  /** true — только позиции без определённого типа */
  untyped?: boolean;
}

export const itemsApi = {
  list: (objectId: number, filters?: ItemFilters) => {
    const query = new URLSearchParams();
    if (filters?.section) query.set("section", String(filters.section));
    if (filters?.tracked !== undefined) query.set("tracked", String(filters.tracked));
    if (filters?.source_file) query.set("source_file", String(filters.source_file));
    if (filters?.item_type) query.set("item_type", filters.item_type);
    if (filters?.untyped !== undefined) query.set("untyped", String(filters.untyped));
    const qs = query.toString();
    return request<SourceItem[]>(`/objects/${objectId}/items${qs ? `?${qs}` : ""}`);
  },
  update: (objectId: number, itemId: number, patch: Record<string, unknown>) =>
    request<SourceItem>(`/objects/${objectId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  setType: (
    objectId: number,
    payload: { item_type: ItemType | null; section_id?: number; ids?: number[]; only_untyped?: boolean }
  ) =>
    request<{ updated: number }>(`/objects/${objectId}/items/set-type`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  setTracked: (objectId: number, payload: { tracked: boolean; section_id?: number; ids?: number[] }) =>
    request<{ updated: number }>(`/objects/${objectId}/items/set-tracked`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ---------- Документы (пул паспортов/сертификатов) ----------
export interface DocListOptions {
  q?: string;
  item_id?: number;
}

export const docsApi = {
  list: (objectId: number, opts?: DocListOptions) => {
    const query = new URLSearchParams();
    if (opts?.q) query.set("q", opts.q);
    if (opts?.item_id) query.set("item_id", String(opts.item_id));
    const qs = query.toString();
    return request<IncomingDoc[]>(`/objects/${objectId}/docs${qs ? `?${qs}` : ""}`);
  },

  async upload(
    objectId: number,
    file: File,
    extra?: { doc_number?: string; doc_title?: string }
  ): Promise<IncomingDoc> {
    const fd = new FormData();
    if (extra?.doc_number) fd.append("doc_number", extra.doc_number);
    if (extra?.doc_title) fd.append("doc_title", extra.doc_title);
    fd.append("file", file);

    const doFetch = (token?: string | null) => {
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      return fetch(`/api/v1/objects/${objectId}/docs`, {
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
    return (await resp.json()) as IncomingDoc;
  },

  attach: (objectId: number, docId: number, itemIds: number[]) =>
    request<{ linked_items: number }>(`/objects/${objectId}/docs/${docId}/attach`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds }),
    }),

  detach: (objectId: number, docId: number, itemIds: number[]) =>
    request<{ linked_items: number }>(`/objects/${objectId}/docs/${docId}/detach`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds }),
    }),

  remove: (objectId: number, docId: number) =>
    request<void>(`/objects/${objectId}/docs/${docId}`, { method: "DELETE" }),

  async download(objectId: number, doc: IncomingDoc): Promise<void> {
    if (!doc.file_id) return;
    const fake = { id: doc.file_id, original_filename: doc.original_filename ?? "doc.pdf" } as ObjectFile;
    await filesApi.download(objectId, fake);
  },
};

export const actsApi = {
  list: (objectId: number, actType?: ActType) =>
    request<Act[]>(
      `/objects/${objectId}/acts${actType ? `?act_type=${actType}` : ""}`
    ),
  create: (
    objectId: number,
    payload: { act_type: ActType; doc_number?: string; doc_date?: string | null; item_ids: number[] }
  ) =>
    request<Act>(`/objects/${objectId}/acts`, { method: "POST", body: JSON.stringify(payload) }),
  update: (objectId: number, actId: number, patch: Record<string, unknown>) =>
    request<Act>(`/objects/${objectId}/acts/${actId}`, { method: "PATCH", body: JSON.stringify(patch) }),
  items: (objectId: number, actId: number) => request<SourceItem[]>(`/objects/${objectId}/acts/${actId}/items`),
  addItems: (objectId: number, actId: number, itemIds: number[]) =>
    request<{ linked_items: number }>(`/objects/${objectId}/acts/${actId}/items`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds }),
    }),
  removeItems: (objectId: number, actId: number, itemIds: number[]) =>
    request<{ linked_items: number }>(`/objects/${objectId}/acts/${actId}/items/remove`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds }),
    }),
  remove: (objectId: number, actId: number) =>
    request<void>(`/objects/${objectId}/acts/${actId}`, { method: "DELETE" }),

  async generate(objectId: number, act: Act): Promise<void> {
    const headers: Record<string, string> = {};
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    const resp = await fetch(`/api/v1/objects/${objectId}/acts/${act.id}/generate`, {
      headers,
      credentials: "include",
    });
    if (!resp.ok) throw new ApiError(resp.status, `Ошибка ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `act_${act.act_type}_${act.doc_number ?? act.id}.docx`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const dashboardApi = {
  summary: () => request<DashboardSummary>("/dashboard/summary"),
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
