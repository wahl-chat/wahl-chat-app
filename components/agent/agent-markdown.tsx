'use client';

import Link from 'next/link';
import { memo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
    content: string;
}

const components: Partial<Components> = {
    // Handle code blocks (inside <pre>)
    pre: ({ children, ...props }) => (
        <pre
            {...props}
            className="mt-2 w-full overflow-x-auto rounded-lg bg-zinc-100 p-3 text-sm dark:bg-zinc-800"
        >
            {children}
        </pre>
    ),
    // Handle inline code
    code: ({ className, children, ...props }) => {
        // If there's a language class, it's a code block (handled by pre)
        const isCodeBlock = /language-(\w+)/.test(className || '');

        if (isCodeBlock) {
            // Code block - just return the code element, pre handles the wrapper
            return <code className={className}>{children}</code>;
        }

        // Inline code
        return (
            <code
                className="rounded-md bg-zinc-100 px-1 py-0.5 text-sm dark:bg-zinc-800"
                {...props}
            >
                {children}
            </code>
        );
    },
    ol: ({ children, ...props }) => (
        <ol className="ml-4 list-outside list-decimal" {...props}>
            {children}
        </ol>
    ),
    li: ({ children, ...props }) => (
        <li className="py-1" {...props}>
            {children}
        </li>
    ),
    ul: ({ children, ...props }) => (
        <ul className="ml-4 list-outside list-disc" {...props}>
            {children}
        </ul>
    ),
    strong: ({ children, ...props }) => (
        <span className="font-semibold" {...props}>
            {children}
        </span>
    ),
    p: ({ children, ...props }) => (
        <p className="mb-2 last:mb-0" {...props}>
            {children}
        </p>
    ),
    a: ({ children, href, ...props }) => (
        <Link
            href={href || '#'}
            className="text-blue-500 hover:underline"
            target="_blank"
            rel="noreferrer"
            {...props}
        >
            {children}
        </Link>
    ),
    h1: ({ children, ...props }) => (
        <h1 className="mb-2 mt-4 text-lg font-semibold" {...props}>
            {children}
        </h1>
    ),
    h2: ({ children, ...props }) => (
        <h2 className="mb-2 mt-4 text-base font-semibold" {...props}>
            {children}
        </h2>
    ),
    h3: ({ children, ...props }) => (
        <h3 className="mb-2 mt-3 text-sm font-semibold" {...props}>
            {children}
        </h3>
    ),
    blockquote: ({ children, ...props }) => (
        <blockquote
            className="border-l-4 border-muted-foreground/30 pl-4 italic text-muted-foreground"
            {...props}
        >
            {children}
        </blockquote>
    ),
};

function AgentMarkdownComponent({ content }: Props) {
    return (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {content}
        </ReactMarkdown>
    );
}

export const AgentMarkdown = memo(
    AgentMarkdownComponent,
    (prevProps, nextProps) => prevProps.content === nextProps.content
);

export default AgentMarkdown;


