import { cleanLabel, pointAnchorId } from '@/lib/chat-summary';
import Link from 'next/link';
import {
  type DetailedHTMLProps,
  type HTMLAttributes,
  type JSX,
  createElement,
  memo,
} from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ChatMessageReference from './chat/chat-message-reference';

const REFERENCE = /^\[\d+(?:\s*,\s*\d+)*]$/;
const TRAILING_PUNCTUATION = /^[.,;:!?)\]»“"']+/;

type HastNode = {
  type: string;
  tagName?: string;
  value?: string;
  children?: HastNode[];
};

/** The text of a block's leading bold span, as in `**Grüne** stimmten …`. */
function leadingBold(node: unknown): string | undefined {
  const first = (node as HastNode | undefined)?.children?.find(
    (child) => child.type !== 'text' || child.value?.trim(),
  );
  if (first?.tagName !== 'strong') return undefined;
  return cleanLabel(
    first.children?.map((child) => child.value ?? '').join('') ?? '',
  );
}

type Props = {
  children: string;
  onReferenceClick: (number: number) => void;
  getReferenceName?: (number: number) => string | null;
  getReferenceTooltip?: (number: number) => string | null;
  getReferenceIsVideo?: (number: number) => boolean;
  /** With `anchorLabels`: a block that opens with one of these bold labels
   * gets an id from `anchorPrefix`, for the "Kurz gesagt" points to jump to. */
  anchorPrefix?: string;
  anchorLabels?: ReadonlySet<string>;
};

const NonMemoizedMarkdown = ({
  children,
  onReferenceClick,
  getReferenceTooltip,
  getReferenceName,
  getReferenceIsVideo,
  anchorPrefix,
  anchorLabels,
}: Props) => {
  // Pure per block: React may render a block twice. A repeated label
  // repeats the id, and a jump lands on its first block.
  const anchorId = (node: unknown): string | undefined => {
    if (!anchorPrefix || !anchorLabels) return undefined;
    const label = leadingBold(node);
    return label && anchorLabels.has(label)
      ? pointAnchorId(anchorPrefix, label)
      : undefined;
  };

  // react-markdown v9 passes a 'node' prop to components which is not a valid DOM attribute
  // and causes TypeScript errors when spreading props to elements like Link or pre.
  const cleanProps = (props: Record<string, unknown>) => {
    const rest = { ...props };
    rest.node = undefined;
    return rest;
  };

  function checkAndBuildReference(
    tag: keyof JSX.IntrinsicElements,
    {
      children,
      ...props
    }: DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>,
  ) {
    const buildReference = (children: string) => {
      const parts = children.split(/(\[\d+(?:\s*,\s*\d+)*])/g);

      if (parts.length > 1) {
        return parts.map((part, index) => {
          const match = part.match(/^\[(\d+(?:\s*,\s*\d+)*)]$/);
          if (match) {
            const numbers = match[1].split(',');
            const pill = (
              <ChatMessageReference
                key={`${index}-${numbers}`}
                numbers={numbers}
                index={index}
                onReferenceClick={onReferenceClick}
                getReferenceTooltip={getReferenceTooltip}
                getReferenceName={getReferenceName}
                getReferenceIsVideo={getReferenceIsVideo}
              />
            );
            // Punctuation right after a pill wraps with it, never alone.
            const trailing = TRAILING_PUNCTUATION.exec(parts[index + 1] ?? '');
            return trailing ? (
              <span key={`${index}-${numbers}`} className="whitespace-nowrap">
                {pill}
                {trailing[0]}
              </span>
            ) : (
              pill
            );
          }
          const previous = parts[index - 1];
          return previous && REFERENCE.test(previous)
            ? part.replace(TRAILING_PUNCTUATION, '')
            : part;
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
    code: (props) => {
      const { className, children, ...rest } = props;
      const { inline, ...restWithoutInline } = rest as Record<string, unknown>;
      const match = /language-(\w+)/.exec(className || '');
      const cleaned = cleanProps(restWithoutInline);

      return !inline && match ? (
        <pre
          className={`${className} mt-2 w-[80dvw] overflow-x-scroll rounded-lg bg-zinc-100 p-3 text-sm dark:bg-zinc-800 md:max-w-[500px]`}
          {...cleaned}
        >
          <code className={match[1]}>{children}</code>
        </pre>
      ) : (
        <code
          className={`${className} rounded-md bg-zinc-100 px-1 py-0.5 text-sm dark:bg-zinc-800`}
          {...cleaned}
        >
          {children}
        </code>
      );
    },
    ol: ({ children, ...props }) => {
      return (
        <ol className="ml-4 list-outside list-decimal" {...cleanProps(props)}>
          {children}
        </ol>
      );
    },
    li: ({ children, node, ...props }) => {
      const id = anchorId(node);
      return checkAndBuildReference('li', {
        children,
        className: id ? 'scroll-mt-4 py-1 outline-none' : 'py-1',
        id,
        tabIndex: id ? -1 : undefined,
        ...cleanProps(props),
      });
    },
    ul: ({ children, ...props }) => {
      return (
        <ul className="ml-4 list-outside list-decimal" {...cleanProps(props)}>
          {children}
        </ul>
      );
    },
    strong: ({ children, ...props }) => {
      return (
        <span className="font-semibold" {...cleanProps(props)}>
          {children}
        </span>
      );
    },
    em: ({ children, ...props }) => {
      return checkAndBuildReference('em', { children, ...cleanProps(props) });
    },
    p: ({ children, node, ...props }) => {
      const id = anchorId(node);
      return checkAndBuildReference('p', {
        children,
        id,
        tabIndex: id ? -1 : undefined,
        className: id ? 'scroll-mt-4 outline-none' : undefined,
        ...cleanProps(props),
      });
    },
    a: ({ children, href, ...props }) => {
      if (!href) {
        return (
          <span
            className="text-blue-500 hover:underline"
            {...cleanProps(props)}
          >
            {children}
          </span>
        );
      }
      return (
        <Link
          href={href}
          className="text-blue-500 hover:underline"
          target="_blank"
          rel="noreferrer"
          {...cleanProps(props)}
        >
          {children}
        </Link>
      );
    },
    h1: ({ children, ...props }) => {
      return (
        <h1 className="my-0 text-xl font-semibold" {...cleanProps(props)}>
          {children}
        </h1>
      );
    },
    h2: ({ children, ...props }) => {
      return (
        <h2 className="my-0 text-xl font-semibold" {...cleanProps(props)}>
          {children}
        </h2>
      );
    },
    h3: ({ children, ...props }) => {
      return (
        <h3 className="my-0 text-xl font-semibold" {...cleanProps(props)}>
          {children}
        </h3>
      );
    },
    h4: ({ children, ...props }) => {
      return (
        <h4 className="my-0 text-lg font-semibold" {...cleanProps(props)}>
          {children}
        </h4>
      );
    },
    h5: ({ children, ...props }) => {
      return (
        <h5 className="my-0 text-base font-semibold" {...cleanProps(props)}>
          {children}
        </h5>
      );
    },
    h6: ({ children, ...props }) => {
      return (
        <h6 className="my-0 text-sm font-semibold" {...cleanProps(props)}>
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
