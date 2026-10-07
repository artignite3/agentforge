import type { ReactNode } from "react";
import { Workflow } from "lucide-react";
export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status.toLowerCase()}`}>
      <span className="status-dot" />
      {status.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}
export function Empty({
  title,
  children,
  icon = <Workflow size={27} />,
}: {
  title: string;
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function Stat({
  label,
  value,
  note,
  icon,
}: {
  label: string;
  value: string;
  note: string;
  icon: ReactNode;
}) {
  return (
    <section className="stat">
      <div className="stat-top">
        <span>{label}</span>
        {icon}
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-note">{note}</div>
    </section>
  );
}
export function Summary({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div>
      <span>
        {icon}
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  );
}
export function Health({
  icon,
  name,
  value,
  detail,
  good,
}: {
  icon: ReactNode;
  name: string;
  value: string;
  detail: string;
  good: boolean;
}) {
  return (
    <section className="panel health-card">
      <div>
        {icon}
        <span className={`connection-dot ${good ? "online" : ""}`} />
      </div>
      <h3>{name}</h3>
      <strong>{value}</strong>
      <p>{detail}</p>
    </section>
  );
}
