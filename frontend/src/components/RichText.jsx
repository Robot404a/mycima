function renderInline(text, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${keyPrefix}-b-${index}`}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={`${keyPrefix}-i-${index}`}>{part.slice(1, -1)}</em>;
    }
    return <span key={`${keyPrefix}-t-${index}`}>{part}</span>;
  });
}

export function RichText({ text = "", className = "" }) {
  const lines = String(text).split(/\n+/);
  return (
    <div className={`rich-text ${className}`}>
      {lines.map((line, index) => (
        <p key={`line-${index}`}>{renderInline(line, `l-${index}`)}</p>
      ))}
    </div>
  );
}
