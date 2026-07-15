import { useState } from "react";

const quickPrompts = [
  "What can you help me with?",
  "Summarize my recent activity",
  "Help me plan my day",
];

const styles = {
  page: {
    minHeight: "100vh",
    display: "grid",
    gridTemplateRows: "auto 1fr",
    background: "#f5f7fb",
    color: "#172033",
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "16px clamp(20px, 5vw, 64px)",
    background: "#ffffff",
    borderBottom: "1px solid #e6eaf0",
  },
  logo: {
    width: 38,
    height: 38,
    display: "grid",
    placeItems: "center",
    borderRadius: 12,
    background: "linear-gradient(135deg, #5b6df8, #7c3aed)",
    color: "white",
    fontWeight: 800,
  },
  title: { margin: 0, fontSize: 18, letterSpacing: "-0.01em" },
  status: { margin: "2px 0 0", color: "#667085", fontSize: 12 },
  shell: {
    width: "min(880px, calc(100% - 32px))",
    height: "min(760px, calc(100vh - 112px))",
    minHeight: 520,
    margin: "24px auto",
    display: "grid",
    gridTemplateRows: "1fr auto",
    overflow: "hidden",
    background: "#ffffff",
    border: "1px solid #e2e7ef",
    borderRadius: 20,
    boxShadow: "0 18px 50px rgba(23, 32, 51, 0.08)",
  },
  conversation: {
    overflowY: "auto",
    padding: "clamp(24px, 5vw, 52px)",
  },
  welcome: { maxWidth: 600, margin: "0 auto 32px", textAlign: "center" },
  botIcon: {
    width: 52,
    height: 52,
    margin: "0 auto 16px",
    display: "grid",
    placeItems: "center",
    borderRadius: 16,
    background: "#eef0ff",
    color: "#5965e8",
    fontSize: 24,
  },
  welcomeTitle: { margin: "0 0 8px", fontSize: "clamp(24px, 4vw, 32px)" },
  welcomeText: { margin: 0, color: "#667085", lineHeight: 1.6 },
  prompts: {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 10,
    marginTop: 22,
  },
  prompt: {
    padding: "10px 14px",
    border: "1px solid #dfe3eb",
    borderRadius: 999,
    background: "white",
    color: "#344054",
    cursor: "pointer",
    fontSize: 13,
  },
  messageRow: { display: "flex", marginBottom: 16 },
  message: {
    maxWidth: "76%",
    padding: "12px 16px",
    borderRadius: 16,
    lineHeight: 1.5,
    fontSize: 14,
    whiteSpace: "pre-wrap",
  },
  composerArea: { padding: "16px 20px 20px", borderTop: "1px solid #edf0f4" },
  form: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "7px 7px 7px 16px",
    border: "1px solid #d7dce5",
    borderRadius: 16,
    background: "#fafbfc",
  },
  input: {
    flex: 1,
    minWidth: 0,
    padding: "8px 0",
    border: 0,
    outline: 0,
    background: "transparent",
    color: "#172033",
    fontSize: 15,
  },
  send: {
    width: 40,
    height: 40,
    border: 0,
    borderRadius: 12,
    background: "#5965e8",
    color: "white",
    cursor: "pointer",
    fontSize: 18,
  },
  hint: { margin: "9px 0 0", textAlign: "center", color: "#98a2b3", fontSize: 11 },
};

function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { id: 1, role: "assistant", text: "Hi! I’m Jarvis. How can I help you today?" },
  ]);

  const sendMessage = (text) => {
    const cleanText = text.trim();
    if (!cleanText) return;

    setMessages((current) => [
      ...current,
      { id: Date.now(), role: "user", text: cleanText },
      {
        id: Date.now() + 1,
        role: "assistant",
        text: "Thanks for your message. Connect me to your chatbot service and I’ll respond here.",
      },
    ]);
    setInput("");
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    sendMessage(input);
  };

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div style={styles.logo} aria-hidden="true">J</div>
        <div>
          <h1 style={styles.title}>PA Jarvis</h1>
          <p style={styles.status}>● Online and ready to help</p>
        </div>
      </header>

      <section style={styles.shell} aria-label="Chat with Jarvis">
        <div style={styles.conversation} aria-live="polite">
          <div style={styles.welcome}>
            <div style={styles.botIcon} aria-hidden="true">✦</div>
            <h2 style={styles.welcomeTitle}>How can I help?</h2>
            <p style={styles.welcomeText}>
              Ask a question, organize your thoughts, or get help with your next task.
            </p>
            <div style={styles.prompts}>
              {quickPrompts.map((prompt) => (
                <button key={prompt} type="button" style={styles.prompt} onClick={() => sendMessage(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {messages.map((message) => {
            const isUser = message.role === "user";
            return (
              <div
                key={message.id}
                style={{ ...styles.messageRow, justifyContent: isUser ? "flex-end" : "flex-start" }}
              >
                <div
                  style={{
                    ...styles.message,
                    background: isUser ? "#5965e8" : "#f0f2f6",
                    color: isUser ? "white" : "#344054",
                    borderBottomRightRadius: isUser ? 4 : 16,
                    borderBottomLeftRadius: isUser ? 16 : 4,
                  }}
                >
                  {message.text}
                </div>
              </div>
            );
          })}
        </div>

        <div style={styles.composerArea}>
          <form style={styles.form} onSubmit={handleSubmit}>
            <input
              style={styles.input}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Message Jarvis..."
              aria-label="Message Jarvis"
            />
            <button style={{ ...styles.send, opacity: input.trim() ? 1 : 0.5 }} type="submit" aria-label="Send message">
              ↑
            </button>
          </form>
          <p style={styles.hint}>Jarvis may make mistakes. Check important information.</p>
        </div>
      </section>
    </main>
  );
}

export default App;
