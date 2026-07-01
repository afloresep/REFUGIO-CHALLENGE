import Link from "next/link";
import { notFound } from "next/navigation";
import { ReplayViewer } from "@/components/replay-viewer";
import { getLocalReplay, isLocalReplayId } from "@/lib/replay-store";

export default async function ReplayPage({
  params,
}: Readonly<{
  params: Promise<{ jobId: string }>;
}>) {
  const { jobId } = await params;

  if (!isLocalReplayId(jobId)) {
    notFound();
  }

  const replay = await getLocalReplay(jobId);

  return (
    <div className="page-stack replay-page">
      <section className="section-head replay-toolbar">
        <div>
          <p className="eyebrow">Replay</p>
          <h1 className="mono">{jobId}</h1>
        </div>
        <Link className="button secondary" href={`/api/refugio-replay?jobId=${jobId}&download=1`}>
          Download JSON
        </Link>
      </section>
      <ReplayViewer replay={replay} />
    </div>
  );
}
