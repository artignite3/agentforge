import type { ReactNode } from "react";
import { Workflow } from "lucide-react";
import { statusLabel } from "../format";

export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status.toLowerCase()}`}>
      <span className="status-dot" />
      {statusLabel(status)}
    </span>
  );
}

export function Empty({
  title,
  children,
  icon = <Workflow size={24} />,
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
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <section className="stat">
      <div className="stat-top">
        <span>{label}</span>
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

/** One dependency per row: status dot, name, current value, and what it means. */
export function Health({
  name,
  value,
  detail,
  good,
}: {
  name: string;
  value: string;
  detail: string;
  good: boolean;
}) {
  return (
    <div className="health-row">
      <span className={`connection-dot ${good ? "online" : "offline"}`} />
      <strong>{name}</strong>
      <span className="health-value">{value}</span>
      <p>{detail}</p>
    </div>
  );
}
