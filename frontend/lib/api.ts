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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export async function login(username: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username }),
  });

  if (!response.ok) {
    throw new Error("Login failed");
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
    throw new Error("Failed to load collections");
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
    throw new Error("Backend request failed");
  }

  return response.json();
}
