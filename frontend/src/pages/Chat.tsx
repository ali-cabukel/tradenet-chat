import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { Markdown, QueryGuardrail, splitCypherBlocks } from "@/components/markdown";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { ChatMessage, ChatThread, PendingApproval, PendingToolCall } from "@/lib/api";

const RECOMMENDATIONS: { group: string; prompts: string[] }[] = [
  {
    group: "Trade graph",
    prompts: [
      "Which countries export the most energy to Germany?",
      "Show food trade from the USA to Türkiye",
      "What are the top partners for US machinery exports?",
      "List node labels and relationship types in the graph",
    ],
  },
  {
    group: "News",
    prompts: [
      "What is the latest news on US–China trade?",
      "Any recent headlines about Turkish energy exports?",
    ],
  },
  {
    group: "Country facts",
    prompts: [
      "What is Türkiye's population and GDP?",
      "Give a short profile of Germany (capital, population)",
    ],
  },
];

function Recommendations({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="mx-auto w-full max-w-2xl text-left">
      <p className="mb-3 text-[11px] font-medium tracking-wide text-slate-500 uppercase">
        Recommended questions
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {RECOMMENDATIONS.map((section) => (
          <section key={section.group} className="min-w-0">
            <h3 className="mb-2 text-xs font-semibold text-slate-600">{section.group}</h3>
            <div className="flex flex-col gap-2">
              {section.prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onPick(prompt)}
                  className="card px-3 py-2.5 text-left text-sm leading-snug text-slate-700 hover:border-teal-300 hover:bg-teal-50/50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function ChatBubble({
  role,
  content,
  queries = [],
  feedback = null,
  regenerateCount = 0,
  canRegenerate = false,
  regenerating = false,
  onFeedback,
  onRegenerate,
}: {
  role: "user" | "assistant";
  content: string;
  queries?: string[];
  feedback?: "up" | "down" | null;
  regenerateCount?: number;
  canRegenerate?: boolean;
  regenerating?: boolean;
  onFeedback?: (rating: "up" | "down" | null) => void;
  onRegenerate?: () => void;
}) {
  const isUser = role === "user";
  const split = isUser ? null : splitCypherBlocks(content, queries);
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`card min-w-0 p-4 ${
          isUser ? "max-w-[min(36rem,85%)] bg-teal-50/80" : "w-full max-w-3xl"
        }`}
      >
        <p
          className={`mb-2 text-[11px] font-medium tracking-wide uppercase ${
            isUser ? "text-right text-teal-800" : "text-slate-500"
          }`}
        >
          {isUser ? "You" : "Agent"}
        </p>
        {regenerating ? (
          <Spinner label="Regenerating…" />
        ) : isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{content}</p>
        ) : (
          <>
            <Markdown content={split?.content || content} />
            {split && split.queries.length > 0 ? (
              <div className="mt-3">
                <QueryGuardrail queries={split.queries} />
              </div>
            ) : null}
          </>
        )}
        {!isUser && !regenerating ? (
          <MessageActions
            content={split?.content || content}
            feedback={feedback}
            regenerateCount={regenerateCount}
            canRegenerate={canRegenerate}
            onFeedback={onFeedback}
            onRegenerate={onRegenerate}
          />
        ) : null}
      </div>
    </div>
  );
}

function MessageActions({
  content,
  feedback,
  regenerateCount,
  canRegenerate,
  onFeedback,
  onRegenerate,
}: {
  content: string;
  feedback: "up" | "down" | null;
  regenerateCount: number;
  canRegenerate: boolean;
  onFeedback?: (rating: "up" | "down" | null) => void;
  onRegenerate?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    const markCopied = () => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    };
    try {
      await navigator.clipboard.writeText(content);
      markCopied();
      return;
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = content;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.top = "0";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      const ok = document.execCommand("copy");
      textarea.remove();
      if (ok) markCopied();
    }
  }

  const toggle = (rating: "up" | "down") => {
    onFeedback?.(feedback === rating ? null : rating);
  };

  return (
    <div className="mt-3 flex items-center gap-1 border-t border-stone-100 pt-2">
      {onFeedback ? (
        <>
          <button
            type="button"
            className={`icon-btn ${feedback === "up" ? "bg-teal-50 text-teal-700 hover:bg-teal-50 hover:text-teal-800" : ""}`}
            aria-label="Thumbs up"
            aria-pressed={feedback === "up"}
            title="Good response"
            onClick={() => toggle("up")}
          >
            <ThumbUpIcon filled={feedback === "up"} />
          </button>
          <button
            type="button"
            className={`icon-btn ${feedback === "down" ? "bg-red-50 text-red-700 hover:bg-red-50 hover:text-red-800" : ""}`}
            aria-label="Thumbs down"
            aria-pressed={feedback === "down"}
            title="Bad response"
            onClick={() => toggle("down")}
          >
            <ThumbDownIcon filled={feedback === "down"} />
          </button>
        </>
      ) : null}
      <button
        type="button"
        className={`icon-btn ${copied ? "text-teal-700" : ""}`}
        aria-label={copied ? "Copied" : "Copy response"}
        title={copied ? "Copied" : "Copy"}
        onClick={() => void copy()}
      >
        {copied ? <CheckIcon /> : <CopyIcon />}
      </button>
      {canRegenerate && onRegenerate ? (
        <button
          type="button"
          className="icon-btn"
          aria-label="Regenerate response"
          title="Regenerate"
          onClick={onRegenerate}
        >
          <RegenerateIcon />
        </button>
      ) : null}
      {regenerateCount > 0 ? (
        <span className="ml-1 text-[11px] text-slate-400">
          Regenerated{regenerateCount > 1 ? ` ×${regenerateCount}` : ""}
        </span>
      ) : null}
    </div>
  );
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
      <path
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 8h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2ZM16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
      <path
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m5 13 4 4L19 7"
      />
    </svg>
  );
}

function ThumbUpIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7 10v11H4.5A1.5 1.5 0 0 1 3 19.5v-8A1.5 1.5 0 0 1 4.5 10H7Zm0 0 4.4-7.2A2.2 2.2 0 0 1 13.3 2 2.3 2.3 0 0 1 15.6 4.2V8h4.1a2 2 0 0 1 2 2.3l-1.1 7.2A2 2 0 0 1 18.6 19H7"
      />
    </svg>
  );
}

function ThumbDownIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M17 14V3h2.5A1.5 1.5 0 0 1 21 4.5v8A1.5 1.5 0 0 1 19.5 14H17Zm0 0-4.4 7.2A2.2 2.2 0 0 1 10.7 22 2.3 2.3 0 0 1 8.4 19.8V16H4.3a2 2 0 0 1-2-2.3l1.1-7.2A2 2 0 0 1 5.4 5H17"
      />
    </svg>
  );
}

function RegenerateIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
      <path
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.02 9.35h5v.01M2.99 19.64v-5h.01m0 0h5m-5 0 3.18 3.18a8.25 8.25 0 0 0 13.8-3.7M4.03 9.87a8.25 8.25 0 0 1 13.8-3.7l3.18 3.18"
      />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
      <path
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 6h18M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6"
      />
    </svg>
  );
}

function argPreview(call: PendingToolCall): string {
  const args = call.args ?? {};
  if (call.name === "run_cypher" && typeof args.cypher === "string") {
    return `\`\`\`cypher\n${args.cypher.trim()}\n\`\`\``;
  }
  const query = args.query;
  if (typeof query === "string" && query.trim()) {
    return query.trim();
  }
  const entries = Object.entries(args);
  if (entries.length === 0) return "_No arguments_";
  return entries
    .map(([key, value]) => {
      const shown = typeof value === "string" ? value : JSON.stringify(value);
      return `**${key}:** \`${shown}\``;
    })
    .join("\n\n");
}

function ApprovalCard({
  approval,
  busy,
  onDecision,
}: {
  approval: PendingApproval;
  busy: boolean;
  onDecision: (decision: "accept" | "reject") => void;
}) {
  return (
    <div className="card w-full max-w-3xl border-teal-200 bg-teal-50/40 p-4">
      <p className="text-[11px] font-medium tracking-wide text-teal-800 uppercase">Approval needed</p>
      <p className="mt-1 text-sm text-slate-700">
        The agent wants to run {approval.tools.length === 1 ? "this tool" : "these tools"}. Approve
        to continue, or reject to skip them.
      </p>
      <ul className="mt-3 space-y-3">
        {approval.tools.map((call) => (
          <li key={call.id} className="rounded-lg border border-stone-200 bg-white p-3">
            <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{call.label}</p>
            <div className="mt-2">
              <Markdown content={argPreview(call)} />
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          className="btn-secondary"
          disabled={busy}
          onClick={() => onDecision("reject")}
        >
          Reject
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={busy}
          onClick={() => onDecision("accept")}
        >
          {busy ? "Working…" : "Approve"}
        </button>
      </div>
    </div>
  );
}

function ConfirmDelete({
  title,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4"
      role="presentation"
      onClick={onCancel}
    >
      <div
        role="alertdialog"
        aria-labelledby="delete-thread-title"
        aria-describedby="delete-thread-desc"
        className="card w-full max-w-sm p-5 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="delete-thread-title" className="text-sm font-semibold text-slate-900">
          Delete this chat?
        </h2>
        <p id="delete-thread-desc" className="mt-2 text-sm text-slate-600">
          “{title}” and its messages will be removed. This cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn-danger" disabled={busy} onClick={onConfirm}>
            {busy ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ThreadSidebar({
  threads,
  loading,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  creating,
}: {
  threads: ChatThread[];
  loading: boolean;
  activeId: string | null;
  onSelect: (thread: ChatThread) => void;
  onNewChat: () => void;
  onDelete: (thread: ChatThread) => void;
  creating: boolean;
}) {
  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-r border-stone-200 bg-white lg:w-72">
      <div className="border-b border-stone-200 p-3">
        <button type="button" className="btn-primary w-full" onClick={onNewChat} disabled={creating}>
          {creating ? "…" : "New chat"}
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4">
            <Spinner label="Loading threads…" />
          </div>
        ) : threads.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-slate-500">
            No threads yet. Ask a question to start.
          </p>
        ) : (
          threads.map((thread) => {
            const active = thread.id === activeId;
            return (
              <div
                key={thread.id}
                className={`group flex items-stretch ${
                  active ? "border-l-2 border-teal-700 bg-teal-50" : "border-l-2 border-transparent"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(thread)}
                  className={`min-w-0 flex-1 truncate py-2.5 pr-2 pl-[14px] text-left text-sm ${
                    active ? "text-teal-900" : "text-slate-700 hover:bg-stone-50"
                  }`}
                >
                  {thread.title || "New chat"}
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${thread.title || "New chat"}`}
                  title="Delete chat"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(thread);
                  }}
                  className={`icon-btn m-1 shrink-0 hover:bg-red-50 hover:text-red-700 ${
                    active
                      ? "text-teal-800"
                      : "text-slate-400 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
                  }`}
                >
                  <TrashIcon />
                </button>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}

export default function Chat() {
  const { user, signOut } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const threadId = searchParams.get("thread");
  const [draft, setDraft] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ChatThread | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const threadsQuery = useQuery({ queryKey: ["chat-threads"], queryFn: api.listThreads });
  const threads = useMemo(() => threadsQuery.data ?? [], [threadsQuery.data]);
  const activeThread = useMemo(
    () => threads.find((thread) => thread.id === threadId) ?? null,
    [threads, threadId],
  );

  const messagesQuery = useQuery({
    queryKey: ["chat-messages", threadId],
    queryFn: () => api.listMessages(threadId as string),
    enabled: Boolean(threadId),
  });

  const approvalQuery = useQuery({
    queryKey: ["chat-approval", threadId],
    queryFn: () => api.getApproval(threadId as string),
    enabled: Boolean(threadId),
  });
  const pendingApproval =
    approvalQuery.data && approvalQuery.data.tools.length > 0 ? approvalQuery.data : null;

  const openThread = (thread: ChatThread) => {
    setSearchParams({ thread: thread.id });
  };

  const newChat = useMutation({
    mutationFn: () => api.createThread(),
    onSuccess: async (thread) => {
      await queryClient.invalidateQueries({ queryKey: ["chat-threads"] });
      openThread(thread);
    },
  });

  const send = useMutation({
    mutationFn: (vars: { threadId: string; content: string }) =>
      api.sendMessage(vars.threadId, vars.content),
    onSuccess: async (data, vars) => {
      queryClient.setQueryData(["chat-approval", vars.threadId], data.pending_approval);
      await queryClient.invalidateQueries({ queryKey: ["chat-messages", vars.threadId] });
      await queryClient.invalidateQueries({ queryKey: ["chat-threads"] });
    },
  });

  const approve = useMutation({
    mutationFn: (decision: "accept" | "reject") =>
      api.resolveApproval(threadId as string, decision),
    onSuccess: async (data) => {
      queryClient.setQueryData(["chat-approval", threadId], data.pending_approval);
      await queryClient.invalidateQueries({ queryKey: ["chat-messages", threadId] });
      await queryClient.invalidateQueries({ queryKey: ["chat-threads"] });
    },
  });

  const setFeedback = useMutation({
    mutationFn: (vars: { messageId: number; rating: "up" | "down" | null }) =>
      api.setMessageFeedback(threadId as string, vars.messageId, vars.rating),
    onMutate: async (vars) => {
      await queryClient.cancelQueries({ queryKey: ["chat-messages", threadId] });
      const previous = queryClient.getQueryData<ChatMessage[]>(["chat-messages", threadId]);
      queryClient.setQueryData<ChatMessage[]>(["chat-messages", threadId], (current) =>
        (current ?? []).map((message) =>
          message.id === vars.messageId
            ? {
                ...message,
                feedback: vars.rating,
                feedback_at: vars.rating ? new Date().toISOString() : null,
              }
            : message,
        ),
      );
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["chat-messages", threadId], context.previous);
      }
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<ChatMessage[]>(["chat-messages", threadId], (current) =>
        (current ?? []).map((message) => (message.id === updated.id ? updated : message)),
      );
    },
  });

  const regenerate = useMutation({
    mutationFn: (messageId: number) => api.regenerateMessage(threadId as string, messageId),
    onSuccess: async (data) => {
      queryClient.setQueryData(["chat-approval", threadId], data.pending_approval);
      await queryClient.invalidateQueries({ queryKey: ["chat-messages", threadId] });
      await queryClient.invalidateQueries({ queryKey: ["chat-threads"] });
    },
  });

  const removeThread = useMutation({
    mutationFn: (thread: ChatThread) => api.deleteThread(thread.id),
    onSuccess: async (_data, thread) => {
      setPendingDelete(null);
      await queryClient.invalidateQueries({ queryKey: ["chat-threads"] });
      queryClient.removeQueries({ queryKey: ["chat-messages", thread.id] });
      queryClient.removeQueries({ queryKey: ["chat-approval", thread.id] });
      if (threadId === thread.id) {
        setSearchParams({});
      }
    },
  });

  const messages: ChatMessage[] = messagesQuery.data ?? [];
  const pendingUserMessage = send.isPending ? (send.variables?.content ?? null) : null;
  const lastMessage = messages.at(-1) ?? null;
  const lastAssistantId =
    lastMessage?.role === "assistant" && !pendingApproval && !send.isPending && !approve.isPending
      ? lastMessage.id
      : null;
  const regeneratingId = regenerate.isPending ? (regenerate.variables ?? null) : null;
  const hideLastAssistantForApproval =
    Boolean(pendingApproval) && lastMessage?.role === "assistant" && !regenerate.isPending;

  useEffect(() => {
    if (!pendingDelete) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPendingDelete(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pendingDelete]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length, send.isPending, approve.isPending, regenerate.isPending, pendingApproval]);

  const submit = () => {
    const content = draft.trim();
    if (!content || !threadId) return;
    setDraft("");
    send.mutate({ threadId, content });
  };

  const startWithDraft = () => {
    const content = draft.trim();
    if (!content) return;
    void api.createThread().then(async (thread) => {
      await queryClient.invalidateQueries({ queryKey: ["chat-threads"] });
      setDraft("");
      setSearchParams({ thread: thread.id });
      send.mutate({ threadId: thread.id, content });
    });
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-stone-200 bg-white px-4 py-3">
        <div>
          <h1 className="text-sm font-semibold text-teal-800">Tradenet Chat</h1>
          <p className="text-xs text-slate-500">Read-only Neo4j · tradenet graph</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-slate-500 sm:inline">{user?.email}</span>
          <button type="button" className="btn-ghost text-xs" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="hidden lg:flex">
          <ThreadSidebar
            threads={threads}
            loading={threadsQuery.isLoading}
            activeId={threadId}
            onSelect={openThread}
            onNewChat={() => newChat.mutate()}
            onDelete={setPendingDelete}
            creating={newChat.isPending}
          />
        </div>

        <section className="flex min-w-0 flex-1 flex-col bg-stone-50">
          {send.isError ? (
            <div className="px-4 pt-3">
              <ErrorNote error={send.error} />
            </div>
          ) : null}
          {regenerate.isError ? (
            <div className="px-4 pt-3">
              <ErrorNote error={regenerate.error} />
            </div>
          ) : null}
          {setFeedback.isError ? (
            <div className="px-4 pt-3">
              <ErrorNote error={setFeedback.error} />
            </div>
          ) : null}
          {approve.isError ? (
            <div className="px-4 pt-3">
              <ErrorNote error={approve.error} />
            </div>
          ) : null}
          {removeThread.isError ? (
            <div className="px-4 pt-3">
              <ErrorNote error={removeThread.error} />
            </div>
          ) : null}

          {activeThread ? (
            <>
              <div className="flex items-center justify-between gap-3 border-b border-stone-200 bg-white px-5 py-3">
                <h2 className="truncate text-sm font-medium text-slate-800">
                  {activeThread.title ?? "New chat"}
                </h2>
                <button
                  type="button"
                  className="icon-btn shrink-0 text-slate-400 hover:bg-red-50 hover:text-red-700"
                  aria-label="Delete chat"
                  title="Delete chat"
                  onClick={() => setPendingDelete(activeThread)}
                >
                  <TrashIcon />
                </button>
              </div>
              <div ref={transcriptRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                {messagesQuery.isLoading ? (
                  <Spinner label="Loading messages…" />
                ) : messages.length === 0 && !pendingUserMessage ? (
                  <div className="mx-auto flex max-w-3xl flex-col items-center px-1 py-8">
                    <h2 className="text-center text-lg font-medium text-slate-800">New chat</h2>
                    <p className="mt-1 mb-6 max-w-sm text-center text-sm text-slate-500">
                      Pick a recommendation, or type your own question below.
                    </p>
                    <Recommendations onPick={setDraft} />
                  </div>
                ) : (
                  <div className="mx-auto max-w-3xl space-y-4">
                    {messages.map((message) => {
                      if (
                        hideLastAssistantForApproval &&
                        message.id === lastMessage?.id &&
                        message.role === "assistant"
                      ) {
                        return null;
                      }
                      const isAssistant = message.role !== "user";
                      return (
                        <ChatBubble
                          key={message.id}
                          role={isAssistant ? "assistant" : "user"}
                          content={message.content}
                          queries={message.queries ?? []}
                          feedback={message.feedback ?? null}
                          regenerateCount={message.regenerate_count ?? 0}
                          canRegenerate={isAssistant && message.id === lastAssistantId}
                          regenerating={isAssistant && message.id === regeneratingId}
                          onFeedback={
                            isAssistant
                              ? (rating) => setFeedback.mutate({ messageId: message.id, rating })
                              : undefined
                          }
                          onRegenerate={
                            isAssistant && message.id === lastAssistantId
                              ? () => regenerate.mutate(message.id)
                              : undefined
                          }
                        />
                      );
                    })}
                    {pendingUserMessage ? (
                      <>
                        <ChatBubble role="user" content={pendingUserMessage} />
                        <div className="flex justify-start">
                          <div className="card w-full max-w-3xl p-4">
                            <Spinner label="Agent is writing…" />
                          </div>
                        </div>
                      </>
                    ) : pendingApproval ? (
                      <div className="flex justify-start">
                        <ApprovalCard
                          approval={pendingApproval}
                          busy={approve.isPending}
                          onDecision={(decision) => approve.mutate(decision)}
                        />
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
              <Composer
                value={draft}
                onChange={setDraft}
                onSubmit={submit}
                busy={
                  send.isPending ||
                  approve.isPending ||
                  regenerate.isPending ||
                  Boolean(pendingApproval)
                }
                placeholder={
                  pendingApproval
                    ? "Approve or reject the pending tool call to continue…"
                    : "Ask a question about the graph…"
                }
              />
            </>
          ) : (
            <div className="flex flex-1 flex-col">
              <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-6 py-10">
                <h2 className="text-lg font-medium text-slate-800">Ask the trade graph</h2>
                <p className="mt-1 mb-6 max-w-sm text-center text-sm text-slate-500">
                  Start a new chat, or pick a recommendation to fill the composer.
                </p>
                <Recommendations onPick={setDraft} />
              </div>
              <Composer
                value={draft}
                onChange={setDraft}
                onSubmit={startWithDraft}
                busy={newChat.isPending || send.isPending}
                placeholder="Ask about countries, categories, or trade flows…"
              />
            </div>
          )}
        </section>
      </div>
      {pendingDelete ? (
        <ConfirmDelete
          title={pendingDelete.title || "New chat"}
          busy={removeThread.isPending}
          onCancel={() => {
            if (!removeThread.isPending) setPendingDelete(null);
          }}
          onConfirm={() => removeThread.mutate(pendingDelete)}
        />
      ) : null}
    </div>
  );
}

function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  placeholder = "Ask a question about the graph…",
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  placeholder?: string;
}) {
  const canSend = value.trim().length > 0 && !busy;
  return (
    <div className="border-t border-stone-200 bg-white px-4 py-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          rows={2}
          value={value}
          placeholder={placeholder}
          aria-label="Message the agent"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (canSend) onSubmit();
            }
          }}
          className="input min-h-[48px] resize-none"
        />
        <button type="button" className="btn-primary shrink-0" disabled={!canSend} onClick={onSubmit}>
          Send
        </button>
      </div>
      <p className="mx-auto mt-1.5 max-w-3xl text-[11px] text-slate-400">
        Enter to send · Shift + Enter for a new line. The agent only runs read-only Cypher.
      </p>
    </div>
  );
}
