"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  askQuestion,
  getAdminIndexStatus,
  getCollections,
  login,
  runAdminReindex,
  type AdminIndexStatus,
  type ChatResponse,
  type Role,
} from "../lib/api";

const DEMO_USERS = [
  "dr.mehta",
  "nurse.priya",
  "billing.ravi",
  "tech.anand",
  "admin.sys",
] as const;

const ROLE_INFO: Record<string, { icon: string; label: string; collections: string[]; capabilities: string[]; sqlAccess: boolean }> = {
  doctor: {
    icon: "🩺",
    label: "Doctor",
    collections: ["clinical", "nursing", "general"],
    capabilities: [
      "Patient treatment protocols",
      "Clinical guidelines & procedures",
      "Nursing care documentation",
      "General hospital policies",
    ],
    sqlAccess: false,
  },
  nurse: {
    icon: "💊",
    label: "Nurse",
    collections: ["nursing", "general"],
    capabilities: [
      "Nursing care standards",
      "Medication administration",
      "Patient care checklists",
      "General hospital policies",
    ],
    sqlAccess: false,
  },
  billing_executive: {
    icon: "🧾",
    label: "Billing Executive",
    collections: ["billing", "general"],
    capabilities: [
      "Insurance claim procedures",
      "Billing codes & guidelines",
      "Revenue cycle queries",
      "SQL analytics on billing data",
    ],
    sqlAccess: true,
  },
  technician: {
    icon: "🔧",
    label: "Technician",
    collections: ["equipment", "general"],
    capabilities: [
      "Equipment maintenance guides",
      "Device operation manuals",
      "Safety compliance procedures",
      "General hospital policies",
    ],
    sqlAccess: false,
  },
  admin: {
    icon: "⚙️",
    label: "Administrator",
    collections: ["clinical", "nursing", "billing", "equipment", "general"],
    capabilities: [
      "Full access to all departments",
      "Clinical & nursing documentation",
      "Billing & equipment records",
      "SQL analytics on all data",
    ],
    sqlAccess: true,
  },
};

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  response?: ChatResponse;
  timestamp: Date;
}

export default function ChatBox() {
  const [username, setUsername] = useState<string>(DEMO_USERS[0]);
  const [token, setToken] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [collections, setCollections] = useState<string[]>([]);
  const [indexStatus, setIndexStatus] = useState<AdminIndexStatus | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [reindexLoading, setReindexLoading] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const refreshAdminStatus = async (accessToken: string) => {
    setStatusLoading(true);
    setInfo("");
    try {
      const status = await getAdminIndexStatus(accessToken);
      setIndexStatus(status);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load indexing status."
      );
      setIndexStatus(null);
    } finally {
      setStatusLoading(false);
    }
  };

  const handleReindex = async () => {
    if (!token) return;
    setReindexLoading(true);
    setError("");
    setInfo("");
    try {
      const res = await runAdminReindex(token);
      setInfo(res.status || "Re-indexing started.");
      await refreshAdminStatus(token);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start re-indexing."
      );
    } finally {
      setReindexLoading(false);
    }
  };

  const handleLogin = async () => {
    setAuthLoading(true);
    setError("");
    setInfo("");
    setMessages([]);
    try {
      const auth = await login(username);
      const access = await getCollections(auth.role, auth.token);
      setToken(auth.token);
      setRole(auth.role);
      setCollections(access.collections);
      setInfo(`Welcome ${username}! Logged in as ${auth.role}`);
      if (auth.role === "admin") {
        await refreshAdminStatus(auth.token);
      } else {
        setIndexStatus(null);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Login failed. Please verify demo username selection."
      );
      setToken("");
      setRole("");
      setCollections([]);
      setIndexStatus(null);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setToken("");
    setRole("");
    setCollections([]);
    setIndexStatus(null);
    setMessages([]);
    setError("");
    setInfo("");
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!question.trim() || !token) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const userQuery = question;
    setQuestion("");
    setLoading(true);
    setError("");
    setInfo("");

    try {
      const response = await askQuestion(userQuery, token);
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: response.answer,
        response: response,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to fetch answer from backend. Please login again."
      );
    } finally {
      setLoading(false);
    }
  };

  const lastMessage = messages[messages.length - 1];
  const lastResponse = lastMessage?.response;
  const showResponseDetails =
    Boolean(lastResponse) && lastResponse?.retrieval_type !== "greeting_welcome";

  return (
    <main>
      <div className="chat-shell">
        <div className="sidebar">
          <div className="sidebar-header">
            <span className="sidebar-logo-icon">🏥</span>
            <div>
              <h1>MediAssist</h1>
              <p>Enterprise Medical AI</p>
            </div>
          </div>

          <div className="sidebar-content">
            {!token ? (
              <section className="login-panel">
                <p className="sidebar-label">Demo Identity</p>
                <select
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={authLoading}
                >
                  {DEMO_USERS.map((user) => (
                    <option value={user} key={user}>{user}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="login-btn"
                  onClick={handleLogin}
                  disabled={authLoading}
                >
                  {authLoading ? "Signing in…" : "Sign In →"}
                </button>
                {error && <p className="sidebar-error">{error}</p>}
              </section>
            ) : (
              <>
                <div className="user-identity">
                  <div className="user-avatar">{ROLE_INFO[role]?.icon ?? "👤"}</div>
                  <div className="user-info">
                    <span className="user-name">{username}</span>
                    <span className="user-role-label">{ROLE_INFO[role]?.label ?? role}</span>
                  </div>
                  <button
                    className="logout-btn"
                    type="button"
                    onClick={handleLogout}
                    title="Sign out"
                    aria-label="Sign out"
                  >
                    Sign out
                  </button>
                </div>

                {role === "admin" && (
                  <section className="admin-panel">
                    <p className="sidebar-label">Index Management</p>
                    <div className="index-status-grid">
                      <div className="index-status-item">
                        <span className={`status-dot ${indexStatus?.index_ready ? "green" : "red"}`} />
                        <span>Index {indexStatus?.index_ready ? "Ready" : "Not Ready"}</span>
                      </div>
                      <div className="index-status-item">
                        <span className={`status-dot ${indexStatus?.service_loaded ? "green" : "red"}`} />
                        <span>Service {indexStatus?.service_loaded ? "Loaded" : "Offline"}</span>
                      </div>
                    </div>
                    {indexStatus?.build_in_progress && (
                      <div className="index-building-pill">⚙ Building…</div>
                    )}
                    <div className="admin-actions">
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => refreshAdminStatus(token)}
                        disabled={statusLoading || !token}
                      >
                        {statusLoading ? "…" : "↻ Refresh"}
                      </button>
                      <button
                        type="button"
                        className="btn-warning"
                        onClick={handleReindex}
                        disabled={
                          reindexLoading ||
                          !token ||
                          Boolean(indexStatus?.build_in_progress)
                        }
                      >
                        {reindexLoading ? "Starting…" : "Re-index"}
                      </button>
                    </div>
                  </section>
                )}

                {ROLE_INFO[role] && (
                  <section className="access-profile">
                    <p className="sidebar-label">Access Profile</p>
                    <div className="collection-tags">
                      {ROLE_INFO[role].collections.map((c) => (
                        <span key={c} className="collection-tag">{c}</span>
                      ))}
                    </div>
                    <div className="capabilities-list">
                      {ROLE_INFO[role].capabilities.map((cap) => (
                        <span key={cap} className="capability-item">✓ {cap}</span>
                      ))}
                    </div>
                    {ROLE_INFO[role].sqlAccess && (
                      <div className="sql-badge">📊 SQL Analytics</div>
                    )}
                  </section>
                )}

                {info && <p className="sidebar-info">{info}</p>}
              </>
            )}
          </div>
        </div>

        {token ? (
          <div className="chat-area">
            <div className="messages-container">
              {messages.length === 0 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-secondary)",
                    textAlign: "center",
                  }}
                >
                  <div>
                    <h2 style={{ margin: "0 0 0.5rem" }}>
                      Welcome to MediAssist
                    </h2>
                    <p>
                      Ask medical policy, clinical, or analytical questions
                    </p>
                  </div>
                </div>
              )}

              {messages.map((msg) => {
                const isWelcomeMessage =
                  msg.type === "assistant" &&
                  msg.response?.retrieval_type === "greeting_welcome";
                return (
                <div
                  key={msg.id}
                  className={`message ${msg.type}${isWelcomeMessage ? " welcome" : ""}`}
                >
                  <div className="message-content">
                    <div className="message-bubble">
                      {isWelcomeMessage && <div className="welcome-eyebrow">Welcome</div>}
                      {msg.content}
                    </div>
                    <div className="message-meta">
                      {msg.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </div>
                </div>
              );
              })}

              {loading && (
                <div className="message assistant">
                  <div className="message-content">
                    <div className="message-bubble">
                      <span style={{ opacity: 0.7 }}>Thinking...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {showResponseDetails && (
              <div className="response-section">
                <h4>Response Details</h4>
                <p>
                  <strong>Retrieval Type:</strong> {lastResponse.retrieval_type}
                </p>
                {lastResponse.sources.length > 0 && (
                  <div>
                    <strong>Sources:</strong>
                    <ul className="sources-list">
                      {lastResponse.sources.map((source, idx) => (
                        <li key={idx}>
                          <strong>{source.source_document}</strong> •{" "}
                          {source.collection} • {source.section_title}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {error && <div className="error">{error}</div>}
            {info && <div className="info">{info}</div>}

            <div className="input-area">
              <form onSubmit={onSubmit} className="input-form">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask your question..."
                  disabled={loading}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !loading) {
                      e.preventDefault();
                      onSubmit(e as any);
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={loading || !question.trim()}
                >
                  {loading ? "..." : "Send"}
                </button>
              </form>
            </div>
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-secondary)",
              textAlign: "center",
            }}
          >
            <div>
              <h2>Please log in to start</h2>
              <p>Select a user and click Login on the left sidebar</p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
