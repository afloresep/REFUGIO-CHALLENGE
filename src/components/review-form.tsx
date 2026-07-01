"use client";

import { useState, useTransition } from "react";
import type { SafetyReview } from "@/lib/safety-review";
import type { Template } from "@/lib/templates";

export function ReviewForm({ templates }: Readonly<{ templates: Template[] }>) {
  const [source, setSource] = useState(templates[0]?.source ?? "");
  const [review, setReview] = useState<SafetyReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <section className="card review-form">
      <div className="section-head">
        <h2>Policy source</h2>
        <select
          aria-label="Load template"
          value=""
          onChange={(event) => {
            const template = templates.find((candidate) => candidate.filename === event.target.value);

            if (template) {
              setSource(template.source);
              setReview(null);
              setError(null);
            }
          }}
        >
          <option value="">Load template...</option>
          {templates.map((template) => (
            <option key={template.filename} value={template.filename}>
              {template.label}
            </option>
          ))}
        </select>
      </div>
      <textarea
        aria-label="Python policy source"
        spellCheck={false}
        value={source}
        onChange={(event) => setSource(event.target.value)}
      />
      <div className="inline-actions">
        <button
          type="button"
          disabled={isPending}
          onClick={() => {
            startTransition(async () => {
              setError(null);
              const response = await fetch("/api/review", {
                body: JSON.stringify({ source }),
                headers: { "content-type": "application/json" },
                method: "POST",
              });

              const payload = await response.json() as SafetyReview | { error?: string };

              if (!response.ok) {
                setReview(null);
                setError("error" in payload && payload.error ? payload.error : "Review failed.");
                return;
              }

              setReview(payload as SafetyReview);
            });
          }}
        >
          {isPending ? "Reviewing..." : "Run review"}
        </button>
      </div>
      {error ? <div className="notice rejected">{error}</div> : null}
      {review ? (
        <div className={review.status === "approved" ? "notice approved" : "notice rejected"}>
          <h3>{review.status === "approved" ? "approved" : "rejected"}</h3>
          <p>{review.message}</p>
          {review.findings.length > 0 ? (
            <ul>
              {review.findings.map((finding) => (
                <li key={`${finding.tag}:${finding.evidence}`}>
                  <strong>{finding.tag}</strong>: {finding.evidence}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
