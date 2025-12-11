import Link from 'next/link';
import {
  createElement,
  type DetailedHTMLProps,
  type HTMLAttributes,
  type JSX,
  memo,
} from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ChatMessageReference from './chat/chat-message-reference';

type Props = {
  children: string;
  onReferenceClick: (number: number) => void;
  getReferenceName?: (number: number) => string | null;
  getReferenceTooltip?: (number: number) => string | null;
};

const NonMemoizedMarkdown = ({
  children,
  onReferenceClick,
  getReferenceTooltip,
  getReferenceName,
}: Props) => {
  function checkAndBuildReference(
    tag: keyof JSX.IntrinsicElements,
    {
      children,
      ...props
    }: DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>,
  ) {
    const buildReference = (children: string) => {
      const parts = children.split(/(\[\d+(?:\s*,\s*\d+)*\])/g);

      if (parts.length > 1) {
        return parts.map((part, index) => {
          const match = part.match(/^\[(\d+(?:\s*,\s*\d+)*)\]$/);
          if (match) {
            const numbers = match[1].split(',');
            return (
              <ChatMessageReference
                key={`${index}-${numbers}`}
                numbers={numbers}
                index={index}
                onReferenceClick={onReferenceClick}
                getReferenceTooltip={getReferenceTooltip}
                getReferenceName={getReferenceName}
              />
            );
          }
          return part;
        });
      }

      return children;
    };

    if (typeof children === 'string') {
      return <span {...props}>{buildReference(children)}</span>;
    }

    if (Array.isArray(children)) {
      return createElement(
        tag,
        props,
        children.map((child) => {
          if (typeof child === 'string') {
            return buildReference(child);
          }
          return child;
        }),
      );
    }

    return createElement(tag, props, children);
  }

  const components: Partial<Components> = {
    code: ({ inline, className, children, ...props }) => {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <pre
          {...props}
          className={`${className} mt-2 w-[80dvw] overflow-x-scroll rounded-lg bg-zinc-100 p-3 text-sm dark:bg-zinc-800 md:max-w-[500px]`}
        >
          <code className={match[1]}>{children}</code>
        </pre>
      ) : (
        <code
          className={`${className} rounded-md bg-zinc-100 px-1 py-0.5 text-sm dark:bg-zinc-800`}
          {...props}
        >
          {children}
        </code>
      );
    },
    ol: ({ children, ...props }) => {
      return (
        <ol className="ml-4 list-outside list-decimal" {...props}>
          {children}
        </ol>
      );
    },
    li: ({ children, ...props }) => {
      return checkAndBuildReference('li', {
        children,
        className: 'py-1',
        ...props,
      });
    },
    ul: ({ children, ...props }) => {
      return (
        <ul className="ml-4 list-outside list-decimal" {...props}>
          {children}
        </ul>
      );
    },
    strong: ({ children, ...props }) => {
      return (
        <span className="font-semibold" {...props}>
          {children}
        </span>
      );
    },
    em: ({ children, ...props }) => {
      return checkAndBuildReference('em', { children, ...props });
    },
    p: ({ children, ...props }) => {
      return checkAndBuildReference('p', { children, ...props });
    },
    a: ({ children, ...props }) => {
      return (
        <Link
          className="text-blue-500 hover:underline"
          target="_blank"
          rel="noreferrer"
          {...props}
        >
          {children}
        </Link>
      );
    },
    h1: ({ children, ...props }) => {
      return (
        <h1 className="mb-2 mt-6 text-xl font-semibold" {...props}>
          {children}
        </h1>
      );
    },
    h2: ({ children, ...props }) => {
      return (
        <h2 className="mb-2 mt-6 text-xl font-semibold" {...props}>
          {children}
        </h2>
      );
    },
    h3: ({ children, ...props }) => {
      return (
        <h3 className="mb-2 mt-6 text-xl font-semibold" {...props}>
          {children}
        </h3>
      );
    },
    h4: ({ children, ...props }) => {
      return (
        <h4 className="mb-2 mt-6 text-lg font-semibold" {...props}>
          {children}
        </h4>
      );
    },
    h5: ({ children, ...props }) => {
      return (
        <h5 className="mb-2 mt-6 text-base font-semibold" {...props}>
          {children}
        </h5>
      );
    },
    h6: ({ children, ...props }) => {
      return (
        <h6 className="mb-2 mt-6 text-sm font-semibold" {...props}>
          {children}
        </h6>
      );
    },
  };

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  );
};

export const Markdown = memo(
  NonMemoizedMarkdown,
  (prevProps, nextProps) => prevProps.children === nextProps.children,
);
