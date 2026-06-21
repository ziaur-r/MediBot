import ChatBox from "../components/ChatBox";

export default function HomePage() {
  return (
    <main>
      <section className="card">
        <h1>AI MediAssist</h1>
        <p>
          Enterprise internal assistant with RBAC-enforced hybrid retrieval,
          SQL-RAG for analytics, and source-grounded answers.
        </p>
        <ChatBox />
      </section>
    </main>
  );
}
