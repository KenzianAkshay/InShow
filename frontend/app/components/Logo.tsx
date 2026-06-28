/** ShowSphere brand mark — a stylised sphere (globe with a meridian and two
 *  latitude lines). Uses currentColor so it inherits the container's text
 *  colour (white on the coral brand tile). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
      <ellipse
        cx="12"
        cy="12"
        rx="4"
        ry="9"
        stroke="currentColor"
        strokeWidth="1.6"
        opacity="0.9"
      />
      <path
        d="M3.2 9.5h17.6M3.2 14.5h17.6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}
