# refugio_postmortem — PROSE (2026-07-05 rewrite)

<!-- Reframed around the public-sharing question, public layout diffusion,
     Team 10 layout swaps, the no-agent control, post-event replay ceiling,
     and the clean-room experiment. Edit freely; sync back to the artifact
     when done. -->

## introduction()

My teammate already wrote up this hackathon: the bus ride, the 3% battery, us finishing fourth. [Go read his first](https://blog.micr.dev/blog/my-first-hackathon-experience). It's better than mine.

This is the other version, focused more on the actual challenge and some thoughts I had on my way home. Also thanks a lot to micr for the discussion about it and some thoughts as well.

Quick context. REFUGIO was a four-hour hackathon: fifteen teams of three, pulled from 360-something applications. One task. You write a single Python file that runs a warehouse with **96 robots**, a **52×52 grid**, **960 shelves** you place yourself, **300 ticks**. Your score is how many packages get delivered.

[FIGURE: kit-layout.svg | # what the kit hands you: 52×52, 960 shelves in neat double racks, 96 docks on the wall. you can move every shelf. that decision is most of the game.]

In the opening talk, [Mihura](https://x.com/XMihura), who built the event, walked us through the design. The hackathon had a twist: every team competed in the open, and every solution posted to the leaderboard was available to all the other teams. He'd taken the idea from the speedrunning community, thanks to Summoning Salt YouTube videos. In that world a runner sets a record, publishes the whole run with the route and the tricks, and then the next runner starts from there and takes it just a bit further (the [documentary channel is worth an hour of your evening](https://www.youtube.com/watch?v=mmJ_LT8bUj0&t=176s)). REFUGIO was planned along the same lines: fifteen teams sharing the frontier should push it faster than fifteen teams working blind. Mihura explained this a bit further in a talk I can't fully remember, but it was essentially along the lines that when a search space is huge, pooling what different explorers find should make the whole field converge quicker than if you ran a SGD or whatever.

What made this interesting, to me at least, is that everyone showed up with the same frontier model (Codex, Claude, Gemini...) and had four hours. And of course, given the time constraint, everyone was going to vibecode their ass through the challenge. With the cherry on top being that no team had a trick the others couldn't get by asking the same model the correct question. That's an interesting chessboard: intelligence commoditized (assuming everyone there was equally good at prompting and had access to the same models) and code being common property. If you ask me, that's a fair snapshot of the wider moment we're in, at least in science, and speaking from a poor PhD perspective. You hand everyone the same model and each person's output gets better while the field's output gets more alike. To everyone reading or reviewing papers nowadays this should sound familiar. George Hotz takes this to its endpoint: [intelligence itself is deflating toward the price of the compute under it](https://geohot.github.io/blog/jekyll/update/2026/06/11/ai-will-be-deflationary.html), and every wage premium built on being the smartest person in the room goes with it. REFUGIO was a four-hour rehearsal of that world. Intelligence cost every team the same couple hundred bucks a month, so it couldn't be the edge, and the afternoon became a hunt for what still was.

The thesis, after a week of pulling the thing apart, is this: shared models and shared solutions did not make the whole room steadily smarter. They made the room converge on the same kind of robot policy: a centralized traffic planner hidden inside Python module globals. The public files let LLM coding agents pass that trick to other LLM coding agents, even when the humans running them did not necessarily know that was the important part. The jump out of the pack came from a different kind of knowledge: the three official seeds were supposed to be hidden, but they were sitting in the site's frontend data, and if you combined those seeds with the target-selection rule, the layout stopped being a warehouse design problem and became an exam-specific index assignment problem.

So, if you had to take a guess. How does that leaderboard end up? Fifteen teams all riding the frontier together? Two or three out front and everyone else eating dust? What happens to the teams that didn't bring three $200 subscriptions to the fight? Can they compete?

Well, the answer is that from the first hour to the last, four or five teams kept moving the leaderboard and everyone else flattened out and went back to refreshing the page. Us among them, eventually. The shared records did something, but not the thing the speedrun analogy made me expect. They made the room more similar. They did not make the room understand the thing being shared.

My guess for what happened to some teams, including ours, is that reading the solutions often aimed at the wrong surface. The naive move is to paste in the current best and say "improve this," which points the model at the planner, the traffic rules, the small constants. It can copy the artifact. It rarely recovers the reason the artifact works. That distinction turned out to be the whole story.

So, this post is my attempt to work out six questions. Did the public-sharing theory work? Why did only a few teams keep moving? What was the real technical challenge? How well do I do without an agent? How far can the score be pushed after the event? And what happens if you rerun the day in a clean room with the humans removed but well thought-out prompts?

Three numbers do most of the work in this post. **931**, what the winners scored. **~920**, the ceiling our own models talked us into and quit at. **1042**, the verified post-event score I found a week too late.

## the_challenge()

The framing was that you're the IMDRA intern working for Avazon and the senior engineer went away, the client demo is soon, you have to rewrite the robot policy and redesign the layout, You're fucked. Good luck.

The whole API is two functions. `create_layout()` decides where your 960 shelves go. `act(observation)` gets called once per robot per tick, and you return one move: up, down, left, right, pick, drop, or wait. That's the entire game.

A robot's life is a loop. It gets assigned a shelf somewhere on the grid, walks to a cell next to it, grabs the package, walks all the way back to its dock on the wall, drops it. That's +1 delivery, then it gets a new shelf. Ninety-six robots doing this at once, for 300 ticks.

At first I thought this was a very common and explored problem already, and given every LLM would probably converge to the same solution, we could write one solution as fast as possible and submit it (which put us in first place) while I ran a literature review to find the max-algorithm-3000 published somewhere that would make our robots fly. That didn't work out, but it was worth the shot. We spent our first hour making the robots smarter, because that's the part that looks like the problem and the shape of the warehouse barely came up until later. Hold onto that, it comes back.

One thing gives the extra flavour, the scoring method. You only score for deliveries above the current global best, which makes sense. Match the shared record exactly and you get zero. The points are awarded relative to the improvement and when that improvement was made, because it is easier to push at the beginning than at the end. By hour two the best is high enough that three or four teams can still clear it and everyone else is playing for pride.

That rule matters because it turns every public solution into a teaching object, not a submission. Copying the file gets you the same raw score and zero points. To get anything from it, you need to extract the part that still has room above it. An LLM can read code, of course. The hard part is knowing which fact in a 500-line generated file is the lever and which fact is just scaffolding. REFUGIO had two levers like that: hidden shared state inside `act()`, and later the hidden demand stream behind the shelf layout.

The starter kit ships a baseline so you have something that runs: send each robot to its nearest shelf. Ninety-six robots, one idea between them. It gridlocks in seconds.

[WIDGET: ▶ [Interactive #1] — replay: the greedy baseline | # 5-12 deliveries per seed, ~15,000 blocked moves. everyone's right, nobody gets home.]

## did_sharing_work()

This was Mihura's big bet, so it deserves a direct answer. Did publishing every strong solution push the frontier?

I think so... More or less.

The leaderboard makes the first half visible. Here is the shared frontier — the best score anyone had reached — across the whole event, with every successful submission behind it.

[FIGURE: event-frontier.svg | # the frontier climbs fast, stalls for three hours, then Team 10 jumps +77 in the final minute. right: every team but one lands in a 36-wide band.]

In the first twenty-five minutes the frontier rockets to 882 as everyone's first real planner lands. Then it stalls. Getting from 882 to the winner's 931 takes three hours and fifteen minutes. Every team but one finishes between 895 and 931. And then, in the final minute, Team 10 jumps from 930 to **1,008**.

That shape already answers part of the question. The public frontier did not make all fifteen teams keep climbing together. By the back half of the event, almost everyone was in the same score band, and only a few teams were still moving the record.

But the files were not useless. After the event I pulled every public job page and started diffing. **86** successful submissions, **83** distinct code files, only **20** distinct layouts. Almost nobody copied code byte for byte. Almost.

[FIGURE: layout-diffusion.svg | # exact layouts spread through the room. the 930 layout reaches six teams; the final 1008 layout appears once, at the end.]

At 13:27, Team 10 posted a 930, and within half an hour six teams were carrying that file or its layout. Every submission is public, so you can watch it spread, edit by edit, like tracer dye. Skip the clever planner code for a second. The load-bearing part of their file is a comment block:

```python
# Tune the planner per starting scenario. The first robot's first target is a
# stable signature of the initial demand, so we pick the WINDOW/FLOW that this
# planner handles best for each known scenario; anything else falls back to a
# robust default.
SEED_CONFIGS = {
    (5, 42):  (34, 0.10, 2.0, 15),   # 546a   -> 306 (rollout)
    (38, 32): (32, 0.06, 2.0, 34),   # bff0fb -> 306 (rollout)
    (11, 47): (32, 0.06, 1.0, 6),    # dfbf   -> 318 (rollout)
}
DEFAULT_CFG = (34, 0.10, 0.0, -1)    # robust fallback = 2x2/m1/entry single-config (922)
```

Read it slowly. Those comments name the three "hidden" evaluation seeds: 546a, bff0fb, dfbf. The file carries a setting tuned offline for each of the three exact warehouses the exam runs, plus a fallback for warehouses that never come. It knows which three warehouses it will be graded on and has stopped pretending to care about any others. Earlier I said a model can copy the artifact and rarely recovers the reason. Here the reason is half written out in plain text, in the most-copied file of the day, and you are about to watch it fail to transmit anyway.

Five other teams took that file. Their diffs work like eye-tracking. You can see exactly where each team looked.

Team 8 looked nowhere. Byte-for-byte copy, identical hash. It scored 930, which tied the record, which is worth zero points.

Team 12 ran the file through a code formatter and re-tuned exactly one constant: `DEFAULT_CFG`. That is the fallback, the setting the file uses only when the warehouse is not one of the three known seeds. On the real evaluation, that branch never runs. They found the one knob in the file guaranteed to do nothing, turned it, and shipped. 930, zero points. Someone read that code carefully enough to find a tuning constant and missed the comment three lines up saying the exam was already solved.

Team 5 went after the planner. They rewrote one of the traffic rules, the part that decides who backs off when two robots want the same cell, and it was real work. It gained nine deliveries on one warehouse and lost fifteen on another: **925**. On this plateau, small changes help one warehouse and hurt another, and this is what that looks like from inside.

Team 3, the team that won the event, made three edits. They renamed `act()` to `_team_act()`. They re-tuned the settings for one seed. And they stapled 129 new lines onto the bottom of the file:

```python
# --- seed-1 replay fast path: 307-delivery c31 2x2/m1 grid trace ---
_RP_EXPECTED = [[38, 32], [35, 33], [42, 32], ...]  # every robot's first target
_RP_TABLE = (
    'ddrrrrddddrrrrrr...pluuullllll...',  # robot 0's entire day, one letter per tick
    'rrrrrrrrrrrrrrrr.rrrrrrrrrrdd...',   # robot 1's
    ...                                   # x96 robots
)

def act(observation):
    ...
    if t == 0 and st["fp_ok"]:
        exp = _RP_EXPECTED[rid]           # is this a warehouse we memorized?
        if tg is None or tg[0] != exp[0] or tg[1] != exp[1]:
            st["fp_ok"] = False
    if st["disabled"] or not st["fp_ok"]:
        return _team_act(observation)     # no: fall back to Team 10's planner
    return _RP_CH2ACT[_RP_TABLE[rid][t]]  # yes: play the tape
```

In plain English: at tick zero, check every robot's first assignment against a stored list. On a match, this is a warehouse the authors have seen before, so stop planning and play a recording. Each robot gets a 300-character string, one letter per tick, computed at home before submitting. If the day ever drifts off the script, hand control back to Team 10's planner and let it improvise.

The recording bought one extra delivery on one warehouse, 307 where Team 10's planner managed 306. Final score: **931** against 930. Submitted at 13:48, that single delivery was worth 831 points, and that was the margin the event was won by. A cassette tape, stapled to a rival's robot brain.

Look at the first line of that block again. `c31` is the job ID of Team 10's public 930. The winners memorized a better version of their rival's day and played it back at them. Hold onto this trick, because the end of this post is me taking it much further.

So did sharing work? The file traveled: six teams in half an hour, a floor at 930, and the winner pulled their weapon out of it. Now look at what traveled with it. The seeds were named in the comments. The per-warehouse settings were labeled. Of the five teams that inherited all of that, four tuned the robot and one played the exam. The file moved at wire speed while the idea inside it barely moved at all.

That is my answer to the speedrun theory. Speedruns compound because everyone owns the game: same cartridge, same glitches, and a route, once found, belongs to the whole community. REFUGIO published the routes and kept the cartridge secret. The routes sat on the leaderboard all afternoon. The cartridge, three seeds and the sentence explaining why they matter, never made it into the exchange, even with its name written on the label.

Team 10's reply landed at 13:57:51, three minutes before the buzzer: **1,008** deliveries on a brand-new layout that appears exactly once in the public record. Too late for anyone to copy. Given what the room did with the previous file, maybe that cost nobody anything.

## why_did_the_room_converge()

The boring answer is that some teams had better model access and better setups. That is true, but it is not the interesting part. The interesting part is how quickly the successful solutions became the same kind of solution, and how few of us understood that solution while it was spreading.

The entry ticket was a stateful traffic planner. The rules describe `act()` as if each robot is deciding locally, one call at a time. In practice, the evaluator imports one Python module and calls it repeatedly. That means module-global state works. A solution can keep a global object in memory, watch all 96 robots across calls, and coordinate them as one traffic system.

That is a very different problem from the one the prompt appears to describe. The visible API says: return one action for one robot. The high-scoring code says: build a central dispatcher, remember every robot, reserve future cells, prevent head-on swaps, and keep cached distance maps around.

The whole trick is this small (condensed from Team 10's file):

```python
class _Brain:            # holds every robot's position, plan, and reserved path
    ...

_BRAIN = _Brain()        # module global: survives from one act() call to the next

def act(observation):
    return _BRAIN.decide(observation)   # 96 "independent" robots, one mind
```

Every scoring solution of the afternoon is that snippet wearing different clothes.

It holds across the whole leaderboard. Among submissions scoring 920 or above, every one I analyzed had the same broad ingredients: a module-global brain, A* or heap-based planning, and edge reservations. In the 895-919 band, almost all of them had the same shape too. Below 850, most submissions were missing that architecture.

This is the strangest part of the day to me now, and if you take one image away from this post, make it this one. For most of that afternoon, the LLMs were cooperating with each other through the public code, and the humans were mostly the network they did it over. I do not mean that as a metaphor. Walk the chain. A model generates the shared-brain planner for one team. The file goes up on the leaderboard. A human on another team downloads it, pastes it into their own model's context, and types "improve this". The second model recognizes the architecture, keeps it, renames a few things, re-tunes a rule, and ships a cousin of the same program. Neither human needed to know what the trick inside was. Judging by the edits, several never found out. The knowledge went model, to file, to model, and the people in the middle were couriers carrying a sealed envelope.

You can even prove the chain of custody, because the code kept fossils. Team 10's file contains this line:

```python
DEFAULT_CFG = (34, 0.10, 0.0, -1)    # robust fallback = 2x2/m1/entry single-config (922)
```

That 922 is a score from Team 10's own private tuning runs. It refers to an experiment nobody outside their team ever saw, and it means nothing to anyone else. The comment appears, character for character, in five of the six public files in this family, across four different teams. It rode through every copy and re-tune because it is dead weight and no model had a reason to touch it. Biologists trace ancestry through mutations that do nothing. Works on code too.

It also tells you how the edits happened. My honest guess for Team 12's dead-knob tune: a human pasted the file into a chat and asked for an improvement, and a model reached for the most visible constant. A person who actually understood the file would touch the unused fallback last. The edits tell you who was doing the reading.

That explains why four or five teams kept moving while most of the room froze. If your model found the global-state trick, or inherited it from a public file, you were in the 900-ish plateau. If it kept treating `act()` as a local robot policy, you were solving a much harder problem and probably did not know what you were missing.

It also explains why the plateau was so sticky. Once everyone had some version of the centralized traffic planner, the next improvements were small, brittle, and seed-dependent. Tiny changes could help one warehouse and hurt another. The public file became a floor: it could get you into the family of solutions that worked. It did not automatically tell you how to leave that family.

## what_was_the_actual_technical_problem()

There are two problems hiding inside REFUGIO.

The visible one is traffic. Ninety-six robots all want to cross the same floor in 300 ticks. If they only chase nearest shelves, they gridlock. If they plan paths but do not reserve edges, they plan head-on swaps the simulator refuses to execute. If they do not share state across robot calls, they cannot coordinate at all.

The ablations are blunt:

- public best: **1008** deliveries, 4 blocked moves
- no shared planner brain, but cached world: **492**, with 14,305 blocked moves
- no edge reservations: **451**, with 2,783 blocked moves
- no flow penalty: **992**
- short planning window: **997**

So yes, the robot policy matters. The public best was not just a pretty layout. It was a centralized cooperative MAPF-ish planner running through Python globals.

The less visible problem is layout. Every delivery is a round trip from a wall base to a shelf and back. Before the robots move, the layout has already decided the cost of the exam.

Here is the line that makes it weird:

```python
def target_for(seed, robot_id, k):
    h = sha256(f"{seed}|{robot_id}|{k}".encode()).digest()
    return sorted_shelves[int.from_bytes(h[:8], "big") % 960]
```

The target is not "a random shelf" once you know the seed. It is an index into your sorted shelf list. Know the three official seeds and you can compute every shelf request for every robot before the run starts.

Those seeds were not announced as part of the challenge. They were supposed to be hidden evaluation cases. But the website needed enough information to render replays and results, and the seed values were sitting in frontend data for anyone who opened the browser dev tools. Some teams found them during the event. We found them too. The difference is what we did with them.

At that point, a layout is no longer just warehouse geometry. It is a rank-constrained assignment from demand indices to positions. The question stops being "where should shelves go in a good warehouse?" and becomes "which sorted shelf index should occupy which cell, given the exact request stream?"

This is where Team 10's final jump came from. I swapped their final layout into their 13:27 code, leaving the older planner mostly alone. It scored **1000**. Then I did the reverse: final planner, old 13:27 layout. It scored **922**. Remapping the seed-signature config keys barely changed the result: 999 and 924.

So the final jump was not a secret late planner rewrite. It was the building, fitted to the exam.

[WIDGET: ▶ [Interactive #2] — the demand, seed by seed | # same warehouse, three seeds. slide between them and watch which shelves run hot on each.]

This also explains why the "1,000 is impossible" reasoning felt convincing and still failed. It averaged over a random warehouse. The contest ran three fixed warehouses, and some teams had those three seeds. The average-case geometry proof was solving the wrong problem.

## my_solution_no_agent()

This is the part I still owe the post.

If the hook is "everyone had the same model," then the honest control is me without one. My own layout, my own planner, no Claude, no Codex, no autocomplete finishing my lines, no pasting the simulator into a chat to ask what to do. Just a text editor, the source, and a timer running.

[WIDGET: [Interactive #4] — my hand-rolled solution | # results pending. this gets a real layout, a real score on the hidden seeds, and an honest wall-clock.]

I do not want to write around this result before it exists. Once the run is done, this section should be short: wall-clock time, score on the official seeds, what design I reached for first, and where I got stuck. If the number lands far below 907, that gap is probably the cleanest measurement in the whole post.

## how_far_does_it_go()

After the event I kept going. The public best was 1008. A cleaned-up continuation of the same planner family reached **1024** on the official seeds. That version still uses Team 10's layout, but retunes the planner layer and adds a few audited late-game fixes.

Then the problem changed again. Once the seeds are known, the policy does not have to be a policy in the normal sense. It can be a replay: a 300-by-96 matrix of precomputed actions, selected by the initial target signature. That sounds silly, but it is legal under the same evaluator contract. More importantly, it makes debugging completely different. A live planner reacts to every perturbation, so improving one robot can ruin three others. A replay freezes the traffic field. You can edit one robot's day, run the simulator, and know exactly what changed.

That replay-edit path took the score to **1042**: 350, 346, 346 across the three seeds.

[WIDGET: ▶ [Interactive #3] — the player piano | # scrub one robot's 300-character day — DDRRRR…PLUUU…O — and watch the string play on the grid.]

This is not a better warehouse robot. On a new seed it scores zero. It is a recording of three known days. That is the point. REFUGIO kept turning from a robotics problem into an information problem.

The strongest upper bound I have is **1062**, from a model that includes target order and shelf locks but relaxes exact robot-to-robot path conflicts. So the exact ceiling is not proved. The current honest range is: verified 1042, certified upper bound 1062.

## the_cleanroom()

Everything so far could still be a story about humans under pressure. Maybe we missed the layout lever because we were rushed, or three hours deep in planner code with a clock running. So the last experiment takes the humans out and asks which mistakes survive.

The teams on the day were humans plus models. The no-agent run is a human with the model removed. The clean room is the reverse: model-only attempts in a scrubbed starter kit, with the same prompt and a hidden grader.

The clean room is the starter kit exactly as we got it, scrubbed. No seeds, no hints from my later analysis, and I checked it clean. An agent gets the repo and a fixed prompt, works alone in one session, and leaves behind one `solve.py`. I grade that file on the real hidden seeds with a grader the agent never sees. Same model every run, same prompt, same rules. Between arms I change exactly one thing.

**Depth.** One agent, six rounds, sees its own score each round and tries to beat it. A team grinding the leaderboard.

**Breadth.** Six agents, one cold shot each, no memory of the others, keep the best. A room full of separate teams.

**Inherit.** Three cold shots, but the current record's full solution sits in the repo, labelled: use it, change it, or ignore it. The speedrun condition.

**Seeded.** Inherit, plus the three evaluation seeds handed over in the prompt, the way the leak handed them to us. The cheat condition.

Depth climbs. Its scores on the official seeds went **710, 707, 769, 819, 836, 840**, against a public curve that ends at 826. Round four is the one to stare at. The agent added an escape rule for stuck robots, the public score didn't move at all, and the official score rose **+50**. The most valuable change of the run was invisible on the leaderboard. A team watching the public number would have shrugged and reverted it. What kept the curve climbing is that from round four on, the agent stopped trusting the three public seeds and validated every change on dozens of fresh random ones instead.

Breadth measures luck. Six identical agents, identical prompt, identical repo: **667, 720, 754, 799, 804, 820**. A 153-point spread with every variable held fixed. That's the distribution your "great one-shot" gets drawn from. At equal budget depth won, 840 against 820: one run that keeps checking itself against fresh conditions beats six independent draws from the pool.

Then the speedrun condition. The three inheritors scored **835, 838, 841**, against the record's 840. All three worked the same way: they kept the record's layout down to the last shelf, kept most of its code, and each tuned one routing rule that looked good locally. None of those tunes moved the official score beyond noise. But the spread collapsed, 153 points to 6. So sharing the record buys exactly one thing, and it's a real thing: the floor. Everyone lands where the record already was, nobody falls into the 667 tail, and nobody jumps either. The detail that reframes even that: four of the six breadth agents, cold, no record in sight, had already produced the identical shelf layout on their own. The one obviously copyable thing in the file was rediscoverable from the rules.

NUMBERS: depth 710 · 707 · 769 · 819 · 836 · **840**  ·  breadth 667–820, best **820**  ·  inherit **835 · 838 · 841** (record 840)  ·  seeded **868 · 869** (record 840)

[FIGURE: verified_three_strategy.png | # real data, official seeds, corrected grader. left: same budget, four ways to spend it. right: the layout wasn't the secret. four of six cold agents rebuilt it without seeing it.]

The seeded arm is the best result. I expected a jump to 950 or 1,020, because the agents had the same seeds Team 10 used. They came back at **868** and **869**.

The way they missed matters. Both spent the seed knowledge on routing: identify which warehouse you are in, then compute a schedule for that warehouse. Both looked at layout fitting and walked away. One called it a two-to-three-percent side quest. The other tried, watched its search tear up the aisle structure, and decided the layout was capped near 930.

That is the whole post in miniature. Handed the answer key, the model still spent most of its effort on the robot. The high-value abstraction was not "use the seeds." It was "the seeds turn layout into a sorted-index assignment problem."

That result is what makes the clean room worth the compute. On the day, I could tell myself we missed the layout lever because we were rushed or unlucky. Then I watched a model with the answer key in hand and no clock running walk up to the same lever, price it as a side quest, and walk away. Twice. The mistake survived the removal of the humans. It ships with this way of working: left alone, the loop polishes the robot, and getting out of that groove takes somebody deciding the exam itself is the thing to study.

One more confession, because this post is about evals and mine broke too. My first grading pass fed the simulator each layout's shelf list in submission order; the official evaluator sorts it first, and that sorted order is the map from hash to shelf. Same cells, different exam. Every "hidden" score I published in an earlier draft of this section was from a permuted exam, and one manufactured a fake overfitting dip I almost built a whole argument on. I only caught it because the seeded agent's score refused to reproduce under my grader. In a post about exam leaks, I'd been grading a permuted exam. Corrected numbers throughout, checked against the room's own runner.

Fair warnings before you lean on the box too hard. One agent session is a stand-in for one submission cycle, which is a lot smaller than a team's whole afternoon. The samples are tiny: six cold shots, three inheritors, two seeded runs. And the agents never face the zero-for-ties rule, so the inherit arm measures whether the record helps if you use it. Whether the rule left anyone a reason to use it is a different question, and the day already answered that one.

## closing_thoughts()

So, the honest answer to the question at the top: the shared frontier worked as a convergence machine, not as an understanding machine.

The picture I keep coming back to is the one from the middle of the post: models passing a program to one another through a public leaderboard, humans carrying the files back and forth, most of us never quite sure what was in the envelope. One team's private tuning note, a stray "922" in a comment, rode unchanged through four teams' submissions like a postmark. Nobody planned that. It is just what happens when everyone's editor is a model and everyone's code is public, and I think it is the most 2026 thing about the whole day.

The jump out of the pack came from information about the exam, and from knowing the right abstraction for that information. Team 10 had the seeds by mid-afternoon and turned them into a building. We had the same seeds and turned them into a scoreboard, something to check our planner against. That difference is about a hundred deliveries.

One detail keeps me honest about my own week of work. The event was won by a cassette tape. Team 3's entire margin was one replayed delivery on one memorized warehouse, stapled onto a planner their rival had published twenty minutes earlier. The 1,042 I built after the event, a full recording of all three warehouses, every robot, every tick, is that same idea grown to full size. I only noticed while diffing their file for this post. I thought I had left the event behind. I had been finishing its winning move.

Hotz's deflation argument got a four-hour test run here. Intelligence rented for a couple hundred bucks a month, the same at every desk, and it deflated on schedule: every planner converged on the same architecture, and being smart bought nobody a lead. What held its price was information. Three hex strings in the site's frontend data, plus the one sentence explaining what they turn the problem into. That is what separated first place from the pack on the day, and it is what separated 1,042 from 907 in the week after.

Genuine thanks to the organizers, and I mean it. The challenge was good enough to survive a full week of me pulling it apart, and most things aren't. The leaked seeds, the frontier scoring, the speedrun bet: these are exactly the kind of thing you only ever learn by watching smart people collide with them, which is kind of the whole point of running one of these.

And to close the loop: every number at the top of this post turned out to be a floor. 931 fell to 1,008, then to 1,024, then to 1,042. The strongest upper bound I can certify is 1,062. The exact ceiling is still somewhere between the replay I have and the proof I don't.

The live challenge and all the replays are still up on the [REFUGIO site](https://refugio-hackathon-nine.vercel.app/). And the actual human version of this day is still [over here](https://blog.micr.dev/blog/my-first-hackathon-experience). Start with that one. I only wrote the footnotes.
