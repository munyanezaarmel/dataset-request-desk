import { Status } from "@/lib/api";

export default function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge ${status}`}>{status.replace("_", " ")}</span>;
}
