type Props = {
  data: unknown;
};

/**
 * Renders a schema.org node as an inline JSON-LD script.
 *
 * Belongs on the page that the node describes, not in a shared layout — nodes
 * carry a url and an @id, so emitting one from a layout would make every route
 * beneath it claim the same identity.
 */
function JsonLd({ data }: Props) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

export default JsonLd;
