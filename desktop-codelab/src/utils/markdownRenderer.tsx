import React from 'react';

// ─── Inline renderer ──────────────────────────────────────────────────────────
// Parses **bold**, *italic*, `code`, and plain text within a single line.

function renderInline(text: string, keyPrefix: string): React.ReactNode {
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  const parts = text.split(pattern);
  return parts.map((part, i) => {
    const k = `${keyPrefix}-i${i}`;
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={k} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={k} className="italic text-gray-300">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={k} className="bg-gray-700 text-amber-300 font-mono text-[11px] px-1 py-0.5 rounded">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={k}>{part}</React.Fragment>;
  });
}

// ─── Block-level list flusher ─────────────────────────────────────────────────

type ListMode = 'ul' | 'ol' | null;

interface ListBuffer {
  mode: ListMode;
  items: { content: string; indent: number }[];
}

function flushList(buf: ListBuffer, key: string): React.ReactNode | null {
  if (buf.items.length === 0) return null;
  const Tag = buf.mode === 'ol' ? 'ol' : 'ul';
  const listClass = buf.mode === 'ol'
    ? 'list-decimal list-inside space-y-0.5 my-1 ml-2 text-gray-300'
    : 'list-disc list-inside space-y-0.5 my-1 ml-2 text-gray-300';
  return (
    <Tag key={key} className={listClass}>
      {buf.items.map((item, i) => (
        <li key={i} style={{ paddingLeft: `${item.indent * 12}px` }}>
          {renderInline(item.content, `${key}-li${i}`)}
        </li>
      ))}
    </Tag>
  );
}

// ─── Main markdown renderer ───────────────────────────────────────────────────
// Converts a plain-text markdown string to an array of React nodes.
// Handles: headings, horizontal rules, unordered/ordered lists, blockquotes, blank lines, paragraphs.
// Does NOT handle nested fenced code blocks — those are stripped upstream by renderMessageContent.

export function renderMarkdown(content: string): React.ReactNode[] {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  const listBuf: ListBuffer = { mode: null, items: [] };

  const pushList = () => {
    const el = flushList(listBuf, `list-${elements.length}`);
    if (el) elements.push(el);
    listBuf.mode = null;
    listBuf.items = [];
  };

  lines.forEach((rawLine, i) => {
    const line = rawLine;
    const key = `md-${i}`;

    // Heading 1
    const h1 = line.match(/^# (.+)$/);
    if (h1) {
      pushList();
      elements.push(
        <h1 key={key} className="text-base font-bold text-white mt-3 mb-1 border-b border-gray-700 pb-0.5">
          {renderInline(h1[1], key)}
        </h1>
      );
      return;
    }

    // Heading 2
    const h2 = line.match(/^## (.+)$/);
    if (h2) {
      pushList();
      elements.push(
        <h2 key={key} className="text-sm font-bold text-blue-300 mt-2.5 mb-1">
          {renderInline(h2[1], key)}
        </h2>
      );
      return;
    }

    // Heading 3
    const h3 = line.match(/^### (.+)$/);
    if (h3) {
      pushList();
      elements.push(
        <h3 key={key} className="text-sm font-semibold text-gray-200 mt-2 mb-0.5">
          {renderInline(h3[1], key)}
        </h3>
      );
      return;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      pushList();
      elements.push(<hr key={key} className="border-gray-600 my-2" />);
      return;
    }

    // Unordered list item: - item or * item (with optional leading spaces)
    const ulMatch = line.match(/^(\s*)[-*] (.+)$/);
    if (ulMatch) {
      if (listBuf.mode === 'ol') pushList();
      listBuf.mode = 'ul';
      listBuf.items.push({ content: ulMatch[2], indent: Math.floor(ulMatch[1].length / 2) });
      return;
    }

    // Ordered list item: 1. item
    const olMatch = line.match(/^(\s*)\d+\. (.+)$/);
    if (olMatch) {
      if (listBuf.mode === 'ul') pushList();
      listBuf.mode = 'ol';
      listBuf.items.push({ content: olMatch[2], indent: Math.floor(olMatch[1].length / 2) });
      return;
    }

    // Blockquote
    const bqMatch = line.match(/^> (.+)$/);
    if (bqMatch) {
      pushList();
      elements.push(
        <blockquote key={key} className="border-l-2 border-blue-500 pl-3 my-1 text-gray-400 italic text-[12px]">
          {renderInline(bqMatch[1], key)}
        </blockquote>
      );
      return;
    }

    // Blank line
    if (line.trim() === '') {
      pushList();
      // Only add spacing div if there's already content
      if (elements.length > 0) {
        elements.push(<div key={key} className="h-1.5" />);
      }
      return;
    }

    // Plain paragraph
    pushList();
    elements.push(
      <p key={key} className="text-gray-300 leading-relaxed my-0.5">
        {renderInline(line, key)}
      </p>
    );
  });

  pushList();
  return elements;
}
