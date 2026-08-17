export default function VerifiedBadge({ size = 18 }) {
  return (
    <span
      title="Verified"
      className="inline-flex items-center justify-center rounded-full"
      style={{
        width: size,
        height: size,
        background: "#ff4fb7", // pink
        boxShadow: "0 6px 18px rgba(255,79,183,0.35)",
      }}
    >
      <svg
        width={Math.max(10, Math.floor(size * 0.62))}
        height={Math.max(10, Math.floor(size * 0.62))}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M20 7L10.5 16.5L4 10"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
