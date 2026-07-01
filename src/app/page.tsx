import Link from "next/link";

const topJobs = [
  { jobId: "c15da13c3eaa", team: "Equipo 10", deliveries: 1008, points: 66990 },
  { jobId: "3905ff4f9ead", team: "Equipo 03", deliveries: 931, points: 831 },
  { jobId: "7a4738c9956c", team: "Equipo 04", deliveries: 907, points: 7227 },
  { jobId: "1b294895f546", team: "Equipo 02", deliveries: 882, points: 88683 },
  { jobId: "bf4184ae5b49", team: "Equipo 16", deliveries: 896, points: 0 },
];

export default function Home() {
  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Warehouse challenge workbench</p>
        <h1>REFUGIO replay viewer, policy templates, and safety review clone.</h1>
        <p>
          This repo mirrors the public hackathon surfaces with bundled replay data,
          extracted templates, and a local deterministic plus LLM-style safety gate.
        </p>
        <div className="actions">
          <Link className="button" href="/replays/bf4184ae5b49">
            Open replay
          </Link>
          <Link className="button secondary" href="/review">
            Review policy
          </Link>
        </div>
      </section>

      <section className="metrics-row" aria-label="Bundled challenge data">
        <div>
          <strong>5</strong>
          <span>bundled replays</span>
        </div>
        <div>
          <strong>96</strong>
          <span>robots per run</span>
        </div>
        <div>
          <strong>300</strong>
          <span>ticks per replay</span>
        </div>
        <div>
          <strong>0</strong>
          <span>runtime external replay fetches</span>
        </div>
      </section>

      <section className="card">
        <div className="section-head">
          <h2>Known public jobs</h2>
          <Link href="/templates">Submission templates</Link>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Team</th>
                <th>Deliveries</th>
                <th>Points</th>
                <th>Replay</th>
              </tr>
            </thead>
            <tbody>
              {topJobs.map((job) => (
                <tr key={job.jobId}>
                  <td className="mono">{job.jobId}</td>
                  <td>{job.team}</td>
                  <td>{job.deliveries}</td>
                  <td>{job.points.toLocaleString("en-US")}</td>
                  <td>
                    <Link href={`/replays/${job.jobId}`}>View</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
