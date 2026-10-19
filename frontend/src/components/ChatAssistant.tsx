import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { api, errorMessage } from "../api/client";
import type { components } from "../api/schema";
import { Dialog, Empty, ErrorState, Loading } from "./Common";

type Entry = Pick<
  components["schemas"]["ChatHistory"],
  "role" | "content" | "verified" | "tools"
>;
type Final = components["schemas"]["ChatFinal"];
const prompts = [
  "What renews this week?",
  "Yearly spend by category",
  "Which subscriptions are duplicates?",
  "Compare my budget",
];

export function ChatAssistant() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="chat-launcher primary" onClick={() => setOpen(true)}>
        <MessageCircle size={19} aria-hidden="true" /> Ask SubTrack
      </button>
      {open && (
        <Dialog
          title="Your subscription assistant"
          drawer
          onClose={() => setOpen(false)}
        >
          <ChatPanel />
        </Dialog>
      )}
    </>
  );
}

export function ChatPanel() {
  const client = useQueryClient();
  const config = useQuery({
    queryKey: ["chat-config"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/chat/config", { signal })).data!,
  });
  const history = useQuery({
    queryKey: ["chat-history"],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/chat/history", {
          signal,
          params: { query: { limit: 20, offset: 0 } },
        })
      ).data!,
  });
  const [messages, setMessages] = useState<Entry[]>([]);
  const [conversation, setConversation] = useState<string>();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [tools, setTools] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyBusy, setHistoryBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const loaded = useRef(false);
  const tail = useRef<HTMLDivElement>(null);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    if (history.data && !loaded.current) {
      loaded.current = true;
      setMessages([...history.data.items].reverse());
      setConversation(history.data.items[0]?.conversation_id);
      setHistoryOffset(history.data.items.length);
    }
  }, [history.data]);
  useEffect(() => {
    const region = tail.current?.parentElement;
    if (region) region.scrollTop = region.scrollHeight;
  }, [messages, busy]);

  async function send(value: string) {
    if (!value.trim() || busy) return;
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    setError("");
    setNotice("");
    setTools([]);
    setQuestion("");
    setMessages((items) => [
      ...items,
      { role: "user", content: value, verified: null, tools: [] },
    ]);
    try {
      const body: components["schemas"]["ChatRequest"] = {
        message: value,
        conversation_id: conversation,
      };
      const response = await api.POST("/api/v1/chat", {
        body,
        signal: controller.signal,
        parseAs: "stream",
      });
      if (!response.data)
        throw new Error("No response received. Please retry.");
      const reader = response.data.getReader();
      controller.signal.addEventListener(
        "abort",
        () => {
          void reader.cancel();
        },
        { once: true },
      );
      const decoder = new TextDecoder();
      let buffer = "",
        finished = false;
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        buffer += decoder
          .decode(part.value, { stream: true })
          .replace(/\r\n/g, "\n");
        let boundary: number;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const lines = block.split("\n");
          const name = lines
            .find((line) => line.startsWith("event: "))
            ?.slice(7);
          const data = JSON.parse(
            lines
              .filter((line) => line.startsWith("data: "))
              .map((line) => line.slice(6))
              .join("\n"),
          );
          if (name === "status") {
            const status = data as components["schemas"]["ChatStatus"];
            setTools((items) =>
              items.includes(status.tool) ? items : [...items, status.tool],
            );
          } else if (name === "final") {
            const result = data as Final;
            setMessages((items) => [
              ...items,
              {
                role: "assistant",
                content: result.answer,
                verified: result.verified,
                tools: result.tools,
              },
            ]);
            setConversation(result.conversation_id);
            finished = true;
          } else if (name === "error") {
            throw new Error(
              (data as components["schemas"]["ChatStreamError"]).message,
            );
          }
        }
      }
      if (!finished)
        throw new Error("The answer was interrupted. Please retry.");
      await client.invalidateQueries({ queryKey: ["chat-history"] });
      setHistoryOffset((value) => value + 2);
    } catch (caught) {
      if (controller.signal.aborted)
        setNotice("Stopped. You can ask another question.");
      else setError(errorMessage(caught));
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }

  async function clear() {
    setError("");
    setHistoryBusy(true);
    try {
      await api.DELETE("/api/v1/chat/history");
      setMessages([]);
      setConversation(undefined);
      setHistoryOffset(0);
      setNotice("Chat history cleared.");
      await client.invalidateQueries({ queryKey: ["chat-history"] });
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setHistoryBusy(false);
    }
  }

  if (config.isPending || history.isPending)
    return <Loading text="Opening your assistant…" />;
  if (config.isError || history.isError)
    return (
      <ErrorState
        error={config.error || history.error}
        retry={() => {
          void config.refetch();
          void history.refetch();
        }}
      />
    );
  const permitted = config.data.mode === "offline" || config.data.live_opt_in;
  return (
    <div className="chat-panel">
      <p className="notice-box">
        {config.data.mode === "offline"
          ? "Offline demo assistant — answers come from your data using built-in rules; no external AI."
          : "Live Claude assistant — your permission controls external data sharing."}
      </p>
      <details className="chat-disclosure" open={!permitted}>
        <summary>Data sharing and consent</summary>
        <p>{config.data.disclosure}</p>
        <p>
          Figures are checked against this answer�s data. Prose may still be
          wrong; review important details.
        </p>
        {config.data.mode === "live" && (
          <>
            {!config.data.live_opt_in && (
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                />{" "}
                I agree to send the disclosed data to Claude.
              </label>
            )}
            <button
              disabled={busy || (!config.data.live_opt_in && !consent)}
              onClick={async () => {
                try {
                  await api.PUT("/api/v1/chat/config", {
                    body: { live_opt_in: !config.data.live_opt_in },
                  });
                  await client.invalidateQueries({ queryKey: ["chat-config"] });
                } catch (caught) {
                  setError(errorMessage(caught));
                }
              }}
            >
              {config.data.live_opt_in
                ? "Withdraw live AI consent"
                : "Enable live AI"}
            </button>
          </>
        )}
      </details>
      <div className="chat-toolbar">
        <button disabled={busy || historyBusy} onClick={() => void clear()}>
          Clear history
        </button>
        {historyOffset < history.data.total && (
          <button
            disabled={busy || historyBusy}
            onClick={async () => {
              setHistoryBusy(true);
              try {
                const response = (
                  await api.GET("/api/v1/chat/history", {
                    params: { query: { limit: 20, offset: historyOffset } },
                  })
                ).data!;
                setMessages((items) => [...response.items.reverse(), ...items]);
                setHistoryOffset(historyOffset + response.items.length);
              } catch (caught) {
                setError(errorMessage(caught));
              } finally {
                setHistoryBusy(false);
              }
            }}
          >
            Earlier messages
          </button>
        )}
      </div>
      <div
        className="chat-messages"
        tabIndex={0}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {!messages.length && (
          <Empty>
            Ask about renewals, recurring spend, duplicates or your budget.
          </Empty>
        )}
        {messages.map((item, index) => (
          <article
            className={`chat-message ${item.role}`}
            key={index}
            aria-label={
              item.role === "user" ? "Your question" : "SubTrack answer"
            }
          >
            <strong>{item.role === "user" ? "You" : "SubTrack"}</strong>
            {item.verified === false && (
              <p className="notice-box">
                Could not verify the model’s answer. The server returned a
                data-only fallback.
              </p>
            )}
            <p className="chat-text">{item.content}</p>
            {item.tools.length > 0 && (
              <small>
                Based on:{" "}
                {item.tools.map((tool) => tool.replaceAll("_", " ")).join(", ")}
              </small>
            )}
          </article>
        ))}
        <div ref={tail} />
      </div>
      {busy && (
        <div role="status" className="chat-status">
          {tools.length
            ? tools.map((tool) => (
                <span className="badge" key={tool}>
                  Checked {tool.replaceAll("_", " ")}…
                </span>
              ))
            : "Checking your question…"}
          <p>Answer text appears after server verification.</p>
        </div>
      )}
      {notice && (
        <p role="status" className="success">
          {notice}
        </p>
      )}
      {error && <ErrorState error={new Error(error)} />}
      <div className="chat-prompts">
        {prompts.map((prompt) => (
          <button
            disabled={busy || !permitted}
            key={prompt}
            onClick={() => setQuestion(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void send(question);
        }}
      >
        <label>
          Ask about your subscriptions
          <textarea
            maxLength={2000}
            required
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            disabled={!permitted}
            rows={2}
          />
        </label>
        <div className="action-row">
          <button
            className="primary"
            disabled={busy || !permitted || !question.trim()}
          >
            Send question
          </button>
          {busy && (
            <button type="button" onClick={() => abort.current?.abort()}>
              Stop answer
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
