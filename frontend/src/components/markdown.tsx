import { useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

function childrenToText(children: ReactNode): string {
  if (children === null || children === undefined || children === false) return "";
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(childrenToText).join("");
  if (typeof children === "object" && children !== null && "props" in children) {
    return childrenToText((children as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

function CodeFence({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="not-prose overflow-hidden rounded-lg border border-stone-200 bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-1.5">
        <span className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
          {lang || "code"}
        </span>
        <button
          type="button"
          onClick={() => void copy()}
          className="text-[11px] font-medium text-teal-300 hover:text-white"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[13px] leading-relaxed break-words whitespace-pre-wrap text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function splitCypherBlocks(content: string, stored: string[] = []) {
  const fromBody: string[] = [];
  const stripped = content
    .replace(/```(?:cypher)\s*\n([\s\S]*?)```/gi, (_match, code: string) => {
      const query = code.trim();
      if (query) fromBody.push(query);
      return "";
    })
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const queries: string[] = [];
  for (const query of [...stored, ...fromBody]) {
    const text = query.trim();
    if (text && !queries.includes(text)) queries.push(text);
  }
  return { content: stripped, queries };
}

export function QueryGuardrail({ queries }: { queries: string[] }) {
  if (queries.length === 0) return null;
  const label = queries.length === 1 ? "Generated query" : `Generated queries (${queries.length})`;
  return (
    <details className="rounded-lg border border-stone-200 bg-stone-50">
      <summary className="cursor-pointer px-3 py-2 text-[11px] font-medium tracking-wide text-slate-500 uppercase select-none marker:text-slate-400">
        {label}
      </summary>
      <div className="space-y-2 border-t border-stone-200 p-2">
        {queries.map((query) => (
          <CodeFence key={query} lang="cypher" code={query} />
        ))}
      </div>
    </details>
  );
}

export function Markdown({ content }: { content: string }) {
  const components: Components = {
    h1: ({ children }) => (
      <h3 className="text-base font-semibold text-slate-900">{children}</h3>
    ),
    h2: ({ children }) => (
      <h4 className="text-sm font-semibold text-slate-900">{children}</h4>
    ),
    h3: ({ children }) => (
      <h5 className="text-sm font-semibold text-slate-800">{children}</h5>
    ),
    h4: ({ children }) => (
      <h6 className="text-[13px] font-medium text-slate-800">{children}</h6>
    ),
    p: ({ children }) => <p>{children}</p>,
    a: ({ href, children }) => (
      <a
        href={href}
        className="break-words font-medium text-teal-800 underline decoration-teal-700/30 underline-offset-2 hover:decoration-teal-800"
        target="_blank"
        rel="noreferrer"
      >
        {children}
      </a>
    ),
    ul: ({ children }) => <ul className="ml-4 list-disc space-y-1.5">{children}</ul>,
    ol: ({ children }) => <ol className="ml-4 list-decimal space-y-1.5">{children}</ol>,
    li: ({ children }) => <li className="pl-0.5 marker:text-slate-400">{children}</li>,
    strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-stone-300 pl-3 text-slate-600">{children}</blockquote>
    ),
    hr: () => <hr className="border-stone-200" />,
    table: ({ children }) => (
      <div className="overflow-x-auto rounded-lg border border-stone-200">
        <table className="w-full min-w-[28rem] border-collapse text-[13px]">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-stone-50">{children}</thead>,
    tbody: ({ children }) => <tbody className="bg-white">{children}</tbody>,
    tr: ({ children }) => <tr className="border-b border-stone-200 last:border-b-0">{children}</tr>,
    th: ({ children, style }) => (
      <th
        className="px-3 py-2 align-bottom font-semibold whitespace-nowrap text-slate-700"
        style={style}
      >
        {children}
      </th>
    ),
    td: ({ children, style }) => (
      <td
        className="px-3 py-2 align-top whitespace-nowrap text-slate-800 tabular-nums"
        style={style}
      >
        {children}
      </td>
    ),
    pre: ({ children }) => <>{children}</>,
    code: ({ className, children }) => {
      const text = childrenToText(children).replace(/\n$/, "");
      const match = /language-([\w+-]+)/.exec(className ?? "");
      const isBlock = match !== null || text.includes("\n");
      if (isBlock) {
        return <CodeFence lang={match?.[1] ?? ""} code={text} />;
      }
      return (
        <code className="rounded-md border border-stone-200 bg-stone-50 px-1 py-px font-mono text-[12px] leading-5 text-slate-800 align-middle">
          {children}
        </code>
      );
    },
  };

  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed text-slate-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
