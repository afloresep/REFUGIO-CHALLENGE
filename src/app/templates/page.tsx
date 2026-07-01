import { getTemplates } from "@/lib/templates";

export default async function TemplatesPage() {
  const templates = await getTemplates();

  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Templates</p>
        <h1>Public REFUGIO Python templates.</h1>
        <p>
          The deployed instructions expose these examples inline. This repo also
          stores them as files under <code>templates/</code>.
        </p>
      </section>
      <section className="template-grid">
        {templates.map((template) => (
          <article className="card" key={template.filename}>
            <div className="section-head">
              <div>
                <h2>{template.label}</h2>
                <p className="instruction-copy">{template.description}</p>
              </div>
              <span className="mono">{template.filename}</span>
            </div>
            <pre><code>{template.source}</code></pre>
          </article>
        ))}
      </section>
    </div>
  );
}
