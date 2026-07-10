export default function Logo({ size = 34 }) {
  return (
    <div
      className="flex items-center justify-center rounded-lg bg-accent font-bold text-white shrink-0"
      style={{ width: size, height: size, fontSize: size * 0.53 }}
    >
      R
    </div>
  );
}
