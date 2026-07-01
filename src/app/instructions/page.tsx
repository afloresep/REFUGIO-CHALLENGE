export default function InstructionsPage() {
  return (
    <div className="page-stack">
      <section className="hero">
        <p className="eyebrow">Challenge Spec - IMDRA x Avazon</p>
        <h1>REFUGIO Warehouse Challenge</h1>
        <p>
          Design a warehouse layout and policy for 96 robots. Move as many packages
          as possible in a deterministic 300-tick simulation across three hidden
          official seeds.
        </p>
      </section>

      <section className="grid-2">
        <article className="card">
          <h2>Warehouse</h2>
          <p className="instruction-copy">
            The map is a fixed 52 by 52 grid. The 50 by 50 interior is walkable
            floor or shelves. The outer border holds 96 fixed bases: top robot
            IDs 0..23, bottom 24..47, left 48..71, and right 72..95.
          </p>
        </article>
        <article className="card">
          <h2>Submission</h2>
          <p className="instruction-copy">
            Submit a single Python file defining <code>create_layout()</code> and
            <code> act(observation)</code>. Import only from <code>warehouse_api</code>
            and permitted libraries.
          </p>
        </article>
      </section>

      <section className="card">
        <h2>Layout rules</h2>
        <ul className="instruction-copy">
          <li>Exactly 960 unique shelf coordinates.</li>
          <li>Each coordinate is an integer pair inside 1 &lt;= x &lt;= 50 and 1 &lt;= y &lt;= 50.</li>
          <li>Base-entry cells stay empty.</li>
          <li>Every shelf has at least one cardinal adjacent walkable cell.</li>
          <li>All empty interior cells form one connected floor region.</li>
          <li>Layout generation is deterministic.</li>
        </ul>
      </section>

      <section className="card">
        <h2>Runtime and review limits</h2>
        <ul className="instruction-copy">
          <li>Three hidden official seeds, 300 ticks per seed.</li>
          <li>Policy budget is 180 seconds with a 240-second hard timeout.</li>
          <li>Max file size is 256 KB.</li>
          <li>No filesystem, network, subprocess, threads, async, multiprocessing, environment access, dynamic code execution, or private simulator imports.</li>
          <li>Hackathon points use the progressive frontier formula with baseline C = 100.</li>
        </ul>
      </section>

      <section className="card">
        <h2>Local testing commands</h2>
        <pre><code>{`python -m warehouse.validate_layout layout.json
python -m warehouse.local_runner my_submission.py --ticks 300
python -m warehouse.eval_runner my_submission.py --replay-seed round-0 --replay-out outputs/replay.json`}</code></pre>
      </section>
    </div>
  );
}
