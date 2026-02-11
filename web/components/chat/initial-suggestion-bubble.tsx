type Props = {
  children: React.ReactNode;
  onClick?: () => void;
};

function InitialSuggestionBubble({ children, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="cursor-pointer rounded-full border border-input px-3 py-2 text-xs text-muted-foreground ring-offset-background transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2  "
    >
      {children}
    </button>
  );
}

export default InitialSuggestionBubble;
