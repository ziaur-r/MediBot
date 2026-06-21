export type Role =
  | "doctor"
  | "nurse"
  | "billing_executive"
  | "technician"
  | "admin";

export type SourceCitation = {
  source_document: string;
  section_title: string;
  collection: string;
};

export type ChatResponse = {
  answer: string;
  sources: SourceCitation[];
  retrieval_type: string;
  role: Role;
};

export type LoginResponse = {
  token: string;
  role: Role;
};

export type CollectionsResponse = {
  role: Role;
  collections: string[];
};

export type AdminIndexStatus = {
  index_ready: boolean;
  service_loaded: boolean;
  build_in_progress: boolean;
};

export type AdminBuildResponse = {
  status: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

async function throwWithApiMessage(response: Response, fallback: string): Promise<never> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    throw new Error(payload.detail || payload.message || fallback);
  } catch {
    throw new Error(fallback);
  }
}

export async function login(username: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username }),
  });

  if (!response.ok) {
    await throwWithApiMessage(response, "Login failed");
  }

  return response.json();
}

export async function getCollections(role: Role, token: string): Promise<CollectionsResponse> {
  const response = await fetch(`${API_BASE_URL}/collections/${role}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await throwWithApiMessage(response, "Failed to load collections");
  }

  return response.json();
}

export async function askQuestion(question: string, token: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    await throwWithApiMessage(response, "Backend request failed");
  }

  return response.json();
}

export async function getAdminIndexStatus(token: string): Promise<AdminIndexStatus> {
  const response = await fetch(`${API_BASE_URL}/admin/rag/status`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await throwWithApiMessage(response, "Failed to load indexing status");
  }

  return response.json();
}

export async function runAdminReindex(token: string): Promise<AdminBuildResponse> {
  const response = await fetch(`${API_BASE_URL}/admin/rag/build`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await throwWithApiMessage(response, "Failed to start re-indexing");
  }

  return response.json();
}
