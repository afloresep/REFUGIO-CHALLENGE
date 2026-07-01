import { ReviewForm } from "@/components/review-form";
import { getTemplates } from "@/lib/templates";

export default async function ReviewPage() {
  const templates = await getTemplates();

  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Safety review</p>
        <h1>Deterministic checker with LLM-style review text.</h1>
        <p>
          The public checker is server-side, so this clone makes the visible behavior
          explicit: deterministic safety tags are authoritative, then a review-style
          explanation is generated from those tags.
        </p>
      </section>
      <ReviewForm templates={templates} />
    </div>
  );
}
