"use client";

import { FormEvent, useState } from "react";
import { askQuestion, getCollections, login, type ChatResponse, type Role } from "../lib/api";

const DEMO_USERS = [
  "dr.mehta",
  "nurse.priya",
  "billing.ravi",
  "tech.anand",
  "admin.sys",
] as const;

export default function ChatBox() {
  const [username, setUsername] = useState<string>(DEMO_USERS[0]);
  const [token, setToken] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [collections, setCollections] = useState<string[]>([]);

  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setAuthLoading(true);
    setError("");
    setResult(null);

    try {
      const auth = await login(username);
      const access = await getCollections(auth.role, auth.token);
      setToken(auth.token);
      setRole(auth.role);
      setCollections(access.collections);
    } catch {
      setError("Login failed. Please verify demo username selection.");
      setToken("");
      setRole("");
      setCollections([]);
    } finally {
      setAuthLoading(false);
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!question.trim() || !token) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await askQuestion(question, token);
      setResult(response);
    } catch {
      setError("Failed to fetch answer from backend. Please login again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-shell">
      <section className="login-panel">
        <h2>Login</h2>
        <p className="muted">Use one of the demo identities to start.</p>
        <div className="login-row">
          <select value={username} onChange={(e) => setUsername(e.target.value)}>
            {DEMO_USERS.map((user) => (
              <option value={user} key={user}>
                {user}
              </option>
            ))}
          </select>
          <button type="button" onClick={handleLogin} disabled={authLoading}>
            {authLoading ? "Signing in..." : "Login"}
          </button>
        </div>
        {role ? <p className="badge">Role: {role}</p> : null}
        {collections.length > 0 ? (
          <p className="muted">Accessible collections: {collections.join(", ")}</p>
        ) : null}
      </section>

      <form onSubmit={onSubmit} style={{ display: "grid", gap: "0.75rem" }}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask policy or analytical questions..."
          rows={5}
          style={{
            width: "100%",
            borderRadius: "10px",
            border: "1px solid var(--border)",
            padding: "0.8rem",
            resize: "vertical",
          }}
        />
        <button
          type="submit"
          disabled={loading || !token}
          style={{
            width: "fit-content",
            border: "none",
            background: "var(--accent)",
            color: "white",
            borderRadius: "999px",
            padding: "0.6rem 1rem",
            cursor: "pointer",
          }}
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      {error ? <p style={{ color: "#c21f39" }}>{error}</p> : null}

      {result ? (
        <div style={{ marginTop: "1rem" }}>
          <h3>Answer</h3>
          <p>{result.answer}</p>

          <p className="badge">Retrieval: {result.retrieval_type}</p>

          <h4>Sources</h4>
          <ul className="sources-list">
            {result.sources.map((source) => (
              <li key={`${source.source_document}-${source.section_title}-${source.collection}`}>
                <strong>{source.source_document}</strong> | {source.collection} | {source.section_title}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
