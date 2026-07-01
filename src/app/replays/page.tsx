import Link from "next/link";
import { localReplayIds } from "@/lib/replay-store";

export default function ReplaysPage() {
  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Replays</p>
        <h1>Open a public REFUGIO replay.</h1>
      </section>
      <section className="card">
        <div className="template-grid">
          {localReplayIds.map((jobId) => (
            <Link className="button secondary mono" href={`/replays/${jobId}`} key={jobId}>
              {jobId}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
