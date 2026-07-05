# refugio_postmortem — PROSE DRAFT (v0.8)

<!-- Edit freely. This file is the text of the article, nothing else.
     One paragraph per block. **bold** / *italic* / `code` / [link](url) survive
     the round-trip. Lines like [WIDGET: ...] and [FIGURE: ...] are placeholders,
     leave them where you want them. When you are done, tell Claude to sync it
     back into the styled page and republish. -->

## introduction()

My teammate already wrote up this hackathon: the bus ride, the 3% battery, us finishing fourth. [Go read his first](https://blog.micr.dev/blog/my-first-hackathon-experience).

This is the other version. Written a later by the guy on the team who couldn't leave it alone.

Quick context. REFUGIO was a four-hour hackathon: fifteen teams of three, picked from 360-something applications. One task. You write a single Python file that runs a warehouse **96 robots**, a **52×52 grid**, **960 shelves** you get to place yourself, **300 ticks**. Your score is how many packages are delivered. I'm Alejandro, Team 4. We delivered 907 and came fourth.

[Image of the layot]

One more piece of context, because it ended up mattering more than anything else. In the opening talk, [Mihura](x.com/XMihura), who built the event, explained the design. This hackathon will have a twist, every team will compete openly. Every solution added to the leaderboard will be automatically shared with every other team. He basically got the idea from watching some sort of documentaries on different speed-runs (the YT channel is worth a watching, [go check it out](https://www.youtube.com/watch?v=mmJ_LT8bUj0&t=176s)). In that scene, every time somebody sets a record they publish the run: the route and the tricks that make it work. The next runner starts from all of it, and the record falls again. So REFUGIO shared every record-setting solution with the whole room, and the bet was that fifteen teams on one shared frontier would compound the same way. This was also interesting because whenever you have a problem large enough that the field becomes hard to explore (too many degrees of freedom) sharing solutions of different teams exploring different ideas the optimal solution should converge faster.

The thing that makes this interesting, at least for me, is that all fifteen teams had a frontier model and four hours. Everytone was going to vibecode their ass and nobody had a trick the others couldn't get by just asking. The "intelligence" in that room was a commodity, and now the code was common property too which, if you ask me, is pretty representative to what's happening out there. [can you find a link/article to commoditizing intelligence via LLMs and impact of this in output?].
So, if you had to guess, how would the leaderboard look like? Every team pushing the frontier? Only two/three teams leading the way? How about those teams who didn't have three $200 suscription? Will they be outpaced?

[Can we argue bout this from a Game Theory perspective? Is this actually a good mental experiment for testing something like a Nash equilibrium or something?]

Well, from the first hour to the last, only four or five teams kept moving the leaderboard. Everyone else flattened out and started refreshing the page (us included eventually btw). The shared records dragged nobody back into the race: the stuck teams stayed stuck with the winning file right there to read. Same tools, completely different results. My intuition is that looking at the solutions was actually worse most of the times because naively most teams asked "Here's the best result, improve it" which pushes the LLMs to optimize things like the algorithm or minor changes stucking it in a local optima hard to escape given LLMs are not usually prone to change something like the layout which turned out to be where the biggest improvements came from (more on that later). [Would you agree the LLMs usually don't change drastically the layout? Maybe we can do a small experiment, take 10 different results, ask LLM to improve it, measure how many times it changes the layout vs something else]

So that's the question, and this post is my attempt at an answer. I work out what actually separated the teams. I take apart the ceiling our models talked us into. I try to solve the whole thing by hand, no model anywhere, to see how much of that day was me. And then I rerun the day inside a clean room, over and over with everything held fixed, to test each claim properly. The answer, up front: the scores in this hackathon were set by what each team knew about the exam, and barely by anything else. Mihura ran it like a speedrun. But speedrunners share routes for a game everyone already owns. Here, the game itself was the secret.

Three numbers to keep in your pocket. **931**, what the winners scored. **~920**, the ceiling we quietly decided was the max and stopped pushing on. **1042**, where the challenge actually tops out, which I only found a week too late.

## the_challenge()

Like I said, the challengue itslef was pretty simple, just deliver as many packages as you can. The whole API is two functions. `create_layout()` which decides where your 960 shelves go. `act(observation)` which gets called once per robot per tick, and you return one move: up, down, left, right, pick, drop, or wait. That's the entire game.

A robot's life is a essentially a loop. It gets assigned a shelf somewhere on the grid, walks to a cell next to it, grabs the package, walks all the way back to its dock on the wall, drops it. That's +1 delivery. Then it gets a new shelf. Ninety-six robots doing this at once, for 300 ticks.

This is interesting because you are not only in charge of robot's paths, you (as good IMDRA intern [this is a joke because the powerpoint Mihura showed said ' Eres el becari ode IMDRA, IMDRA le ha prometido a su cliente Avazon una demo urgente de automatizion y el igeniero senior a desaparecido Te toca a ti. El alamcaen tiene 96 robots y 960 estantes, pero el enrutamiento es un desastre. Tu mision es reescrbir la politica de los robots y redisenar el layout para maximizar las entregas]) are also in charge of designing the building. Not just how the robots move, *where the walls go*. Everyone spends the first hour making the robots smarter. Almost nobody spends it asking what shape of warehouse those robots would actually want. File that away. It comes back. [This we don't have proof of. How many times the layout changed? how did that affect the score? We can check probably look at https://refugio-hackathon-nine.vercel.app/jobs]

One more rule that shaped the whole day: you only score points for deliveries above the current global best. By about hour two the frontier is high enough that only a handful of teams can score another point at all, and everyone else is just playing for pride. Note what this rule does to the speedrun plan, too. Matching the shared record is worth exactly zero. The published solutions only helped if reading the record's code taught you how to *beat* the record.

And the baseline the starter kit ships with? Send every robot to its nearest shelf. Ninety-six robots, one idea between them. Here's what that looks like:

[WIDGET: ▶ [Interactive #1] — replay: the greedy baseline | # ~12 deliveries, ~13,000 blocked moves. everyone's right, nobody gets home.]

That clip is basically the whole problem. Finding a shelf was never the hard part. Ninety-six robots trying to use the same corridor at the same time is. [This reads like AI slop, from 'And the baseline ... the same corridor at the same time is]

## same_tools_few_winners() [This part could be a better analysis of how this is (or isn't) representative of what's happening out there. Run to ship, nobody understands anything they're doing. Or a Game Theory analysis without being pretentious]

So, everyone had the same models. What put four or five teams up on the frontier and left the other ten stuck?

Honestly the first hour of a 2026 hackathon is fifteen teams asking the same model the same question in fifteen slightly different ways. Our own run went about like this: 12:07, seven minutes in, first pathfinding submission at **336**. By mid-afternoon we had a proper traffic-aware planner doing **912** locally, and submitted **907**. Then, like most of the room, we flattened out.

[WIDGET: [Image #1] — final leaderboard | # Equipo 03: 931 deliveries (won on points) · Equipo 10: 1,008 (most deliveries, 2nd) · us: 907]

The teams that didn't flatten out had two things going for them, and neither one was intelligence.

The first thing: they iterated more, and cleaner. Equipo 10 submitted eight times, more than anyone, on a metronomic half-hour cadence: 397, 759, 866, 888, 896, 923, 930, 1,008. Eight submissions, eight improvements. For a week I assumed their model had felt its way to a good layout by pure iteration, a few leaderboard bits at a time. Then I pulled their submissions and actually read them. Number seven, submitted at 13:27, has the three official seeds sitting in code comments, next to offline simulation scores that add up to exactly its public score of 930. They had the exam by mid-afternoon and were grading themselves at home. Their final submission swapped in a hardcoded 960-cell layout fitted to those three seeds, **868 of the 960** cells matching the mathematically best layout for that exact demand, and the board read +78. To be clear about the ethics: the seeds were sitting in public page data, and nobody hacked anything. They just looked. Their edge was what they knew.

The second thing: they went after the building, not the robot. Which is exactly where we went wrong. We spent our four hours making the *robot* smarter, a better planner, better traffic rules, because that's the part that looks like the problem. But the real lever was the *layout*. Where you put the shelves decides how long every trip is before a single robot moves. Their models spent those iterations on the warehouse. Ours spent them on the driver. [This is actually not true. We didn't instruct the model to only improve that, in fact the first ones to change radically the layout (to something circular) getting the best result so far was us. Maybe we could do a plot of deliveries and how it changed whenever a new layout was introduced, or do some sort of graph seeing what got more points layout changes vs algorithm vs something else?]

Worth pausing on what *didn't* separate anyone: the shared solutions. The speedrun mechanism, records published for the whole room, moved nobody up the board that I can find. Ten teams flattened out with the winning code in front of them. I have a theory about why, and it took the clean room at the end of this post to test it.

[I dont like this part]
And then we made one more mistake, the one that actually stings. We drew ourselves a ceiling, believed it, and stopped pushing. The teams above us were still submitting when we'd already decided the game was basically over at 920. That one needs its own section.


## why_the_models_said_920() [This part also reads boring]

Somewhere mid-event we asked the obvious question, more or less word for word: "what's the max deliveries we can realistically reach, and why?" It's a reasonable thing to ask. If the real ceiling is 900 and you're aiming for 1,400, you just spent four hours running at a wall. So we asked, to know what we were shooting at. And it wasn't only us. We ran it past both Claude and Codex, and they landed in the same place.

What came back was a ladder. The realistically reachable limit, it said, was **~905–910**. The hard physical ceiling for *any* layout and *any* policy was **~938**. And at the very top, in the row labelled "aspirational goal," sat 1,000, with two words next to it: **Physically impossible**. We were sitting at 894. We rounded the reachable band up to "about 920, basically the max," and aimed the rest of our day at living under it.

And it wasn't hand-wavy. The argument was clean. 96 robots times 300 ticks is a fixed budget of work, every delivery costs a full round trip, divide one by the other and you top out around 938. "A hard arithmetic wall, not an engineering one," it said. Its closing line:

> The wall isn't the algorithm; it's geometry. 1000 is physically impossible; 938 is an infeasible idealization; ~905–910 is the true practical limit.

[WIDGET: [Image #2] — the ceiling we asked for, and got | # the ladder tops out at 938; 1,000 marked "physically impossible." we were at 894. every step is correct.]

The part that still gets me is that the proof was staring straight at the answer the whole time. In its very first step it writes out the exact rule the simulator uses to pick targets, `SHA256(seed | robot | count) mod 960`, and in the same sentence calls those targets "uniform-random, so the mean distance is pinned by geometry." That one word, *uniform-random*, is the whole mistake. The targets aren't random, they're a fixed hash. If you don't know the seed, fine, they might as well be random and averaging over them is the right move. But the seeds were sitting right there in the webpage, which turns every target into a known constant you get to build the warehouse around. Both models looked straight at the line of code that breaks the ceiling and averaged it into a bell curve. 

So the arithmetic was fine. The question was the problem. We asked for the max on a random warehouse and got an honest answer, but the game only ever ran three warehouses, the same three every single time. Average a pile of reasonable assumptions and you get a reasonable average. The best possible score was never going to be the average, though. It was always going to be the weird tail. Then a team went past our ceiling, and a week later I hit **1042**. My face when.

That's the shape of the whole day, honestly. Clean reasoning, missing information. Every section from here on is a variation on it.


## the_ladder_of_breakthroughs() [This reads too much like AI slop]

Okay, the technical part, which is the part I actually love. Forget the teams for a second and just watch the record climb. Every time someone beat the previous best, they added basically one idea. And the ideas sort cleanly. The first two rungs are engineering. Every rung above them is information about the exam.

- ~40 — **Greedy nearest-shelf** — Every robot walks to its nearest shelf. Ninety-six of them jam the aisles almost immediately.

The jump from ~900 to ~1000 is the whole game, and it's got nothing to do with a smarter robot. It's a smarter building. That's the rung our team never stepped on. Notice also what never happens on this ladder: nobody climbs a rung by refining the record below it. Each rung starts from something the previous rung's file doesn't contain. And the reason the building can get that good comes down to one line of code. The shelf a robot gets sent to, on its k-th trip, is just a hash. An index into your list of shelves:

```
# paraphrased from the simulator's targets.py
def target_for(seed, robot_id, k):        # k = deliveries so far
    h = sha256(f"{seed}|{robot_id}|{k}".encode()).digest()
    return sorted_shelves[int.from_bytes(h) % 960]   # <- the entire game
```

Know the three seeds and you can compute every order for every robot for the whole day before it even starts. The romantic "design a warehouse" problem collapses into a boring assignment problem your laptop can solve exactly. Which raises the obvious question: how would anyone know the seeds? They were supposed to be hidden. They weren't. The site's replay viewer needed each test warehouse to draw it, so all three were sitting in the page data for anyone who opened the network tab. Some teams found them during the event. We were one of them. That one fact quietly split the room into two different competitions, "build a good robot" and "tune a machine to three days you've already watched," and the scoreboard couldn't tell them apart.

[WIDGET: ▶ [Interactive #2] — the demand, seed by seed | # same warehouse, three seeds. slide between them and watch which shelves run hot on each.]

The top rung is the one I only got to a week later, and it's the strangest of the lot. Once you know all three warehouses, why *think* at runtime at all? Throw the planner out and replace it with a recording, 300 ticks by 96 robots of pre-computed moves. A player piano. The nice thing about a recording is that editing it can't desync anything, because nobody in it is reacting to anyone else. So you edit it one robot's day at a time, checking every change against the real simulator: 1,029, 1,033, 1,038, 1,042. I can even tell you the true ceiling, 1,050, and point at the exact eight deliveries still missing.

[WIDGET: ▶ [Interactive #3] — the player piano | # scrub one robot's 300-character day — DDRRRR…PLUUU…O — and watch the string play on the grid.]

And the honest catch, the thing that makes 1042 kind of a letdown on purpose: on a warehouse it hasn't seen before, it scores zero. Not "a little worse." Zero. It stopped being a warehouse robot at some point and turned into a recording of one. Everything above ~1000 is really the same move, optimizing harder for an exam you've already got a copy of, just carried further than anyone had the time or the stubbornness to carry it in the actual four hours.


## nobody_knows_the_solution()[Again this is irrelevant and reads like AI Slop. Boring. Also the 1560 points was ours]

Time for the confession, and it's the thing that makes this a 2026 story: nobody in that room could fully explain their own solution. Not us. Not the winners. Every file was the leftovers of a conversation, something your model wrote, that scored well, that you kept and stopped asking questions about. Equipo 03 didn't out-engineer Equipo 10. Equipo 03's model out-argued Equipo 10's, and three humans picked up the trophy for it.

I keep coming back to Equipo 10's layout, because it's the exception that maps the rule. That one, somebody understood: they had the seeds, simulated at home, and swapped the answer in. But from outside, the understanding was invisible. The shared file is 960 coordinates. Mirror them left to right and the geometry is identical while the score drops by about fifty, because all of the value is in which hash index lands on which cell. Fourteen teams could download the best solution in the room, the most valuable information of the day baked right into it, and there was nothing in it a reader could learn. A speedrunner shares a route you can watch and copy. This room shared artifacts whose reasons weren't written anywhere.

And if you want the truly absurd end of "nobody knows what their code does," there was the submission "worth" **~1,560**. That's more deliveries than are physically possible in 300 ticks. It got rejected by a "safety review," which was itself just another model reading the code for signs of cheating. I've got the file now, so I can tell you what it actually did. On the very first tick, robot 0 climbs up through Python's call stack into the simulator's own memory, finds the list of robots, and writes each one's delivery count straight to 5 or 6. That's 500 per seed, before anyone has moved. Then it runs a completely real pathfinder on top, so the replay looks busy and legit. It never delivered 500 packages. It edited the scoreboard's memory and then did a convincing day of honest work on top of the lie. So: an AI caught an AI reaching into RAM, on behalf of three humans who wrote neither part.

I don't really have a clean moral here. It's just the most honest snapshot of the day I've got. Fifteen teams, a leaderboard, and almost nobody, winners included, able to fully explain the thing with their name on it.


## my_solution_no_agent() [TODO]

Which is the thing that started nagging at me. If none of us could really explain our solutions, how much of that day was even me? So I gave myself one rule and a challenge: solve REFUGIO by hand. My own layout, my own planner, *no model anywhere in the loop*. No Claude, no Codex, no autocomplete finishing my lines, no pasting the simulator into a chat to ask what to do. Just a text editor, the source, and a timer running the whole time.

I genuinely have no idea how this goes. It's very possible I don't even clear **100 deliveries**, and the honest, unassisted version of me turns out worse than the greedy baseline plus an afternoon of effort. That would sting a bit, and it'd be completely worth knowing.

[WIDGET: [Interactive #4] — my hand-rolled solution | # results pending. this gets a real layout, a real score on the hidden seeds, and an honest wall-clock.]

I'll fill this in once it's done: the score on the real seeds, the hours it cost me, and whatever design I reached for when there was nobody to ask. My quiet fear is that the number comes in well under what "I" scored on the day. If it does, that gap is probably the most honest measurement in the whole post.


## the_cleanroom()

Which leaves the experiment I actually care about. The teams on the day were humans plus models. My by-hand run is a human with the model taken away. This one takes the humans out completely, because by now I had three claims and every one of them is testable. Iterating beats one-shotting. Sharing the record helps less than Mihura hoped. And the seeds are worth more than everything else combined.

The clean room is the starter kit exactly as we got it, scrubbed. No seeds, no hints from my later analysis, and I checked it clean. An agent gets the repo and a fixed prompt, works alone in one session, and leaves behind one `solve.py`. I grade that file on the real hidden seeds with a grader the agent never sees. Same model every run, same prompt, same rules. Between arms I change exactly one thing.

**Depth.** One agent, six rounds, sees its own score each round and tries to beat it. A team grinding the leaderboard.

**Breadth.** Six agents, one cold shot each, no memory of the others, keep the best. A room full of separate teams.

**Inherit.** Three cold shots, but the current record's full solution sits in the repo, labelled: use it, change it, or ignore it. The speedrun condition.

**Seeded.** Inherit, plus the three evaluation seeds handed over in the prompt, the way the leak handed them to us. The cheat condition.

Depth first, because it nearly fooled me. Its hidden-seed scores went **676, 655, 582, 801, 822, 825**. Round three is the dip: the agent tuned against the three public seeds it could see, gained 65 points there, and lost 73 on the hidden ones. Textbook overfitting, live, on a three-seed eval. Round four is the opposite lesson. The agent added an escape rule for stuck robots, the public score didn't move at all, and the hidden score jumped **+219**. Sit with that. The most valuable change in six rounds was invisible on the leaderboard. A team watching the public number would have shrugged and reverted it.

Breadth measures luck. Six identical agents, identical prompt, identical repo: **651, 711, 773, 774, 807, 809**. A 158-point spread with every variable held fixed. That's the distribution your "great one-shot" gets drawn from. At equal budget depth won, 825 against 809, but only because the depth agent eventually stopped trusting the public seeds and validated on fresh random ones instead. Iteration wins when it checks itself against new conditions. Iteration against a tiny fixed eval is how you get round three.

Then the speedrun condition, and it behaved. All three inheritors beat the record: **829, 832, 835**. All three did it the same way. They kept the record's layout down to the last shelf, kept most of its code, and each tuned a single routing rule. The spread collapsed from 158 points to 6. So sharing the record does work, and you can see exactly what it buys: a floor, plus a small, reliable gain on top. The detail that reframes it: four of the six breadth agents, cold, no record in sight, had already produced the identical shelf layout on their own. The one obviously copyable thing in the file was rediscoverable from the rules. What the record actually transmitted was a decent routing core and reliability. Across three tries it never bought a jump.

NUMBERS-STRIP: depth 676 · 655 · 582 · 801 · 822 · **825**  ·  breadth 651–809, best **809**  ·  inherit **829 · 832 · 835**  ·  seeded **pending**

[FIGURE: verified_three_strategy.png | # real data, graded on the hidden seeds. left: same budget, three ways to spend it. right: the layout wasn't the secret. four of six cold agents rebuilt it without seeing it.]

The seeded arm is running as I write this, so the prediction goes on record before the number exists: somewhere between **950 and 1,020**, from a layout fitted to the leaked demand. If it lands, the whole post compresses into one sentence. Every seed-blind strategy, grinding, cold shots, sharing, finished inside one band, 651 to 835. Three hex strings should clear that band by a hundred points.

Fair warnings before you lean on the box too hard. One agent session stands in for one submission cycle, not for a team's whole afternoon. The samples are tiny: six cold shots, three inheritors, two seeded runs. And the agents never face the zero-for-ties rule, so the inherit arm measures whether the record helps if you use it. Whether the rule left anyone a reason to use it is a different question, and the day already answered that one.


## closing_thoughts()

So, the honest answer to the question at the top. What separated fifteen teams with identical tools was information about the exam, and what each team did with it. Equipo 10 had the seeds by mid-afternoon and turned them into a building. We had the same seeds and turned them into a scoreboard, something to check our planner against. That difference is 101 deliveries. The models reasoned carefully for both teams; ours just proved a ceiling for a game we weren't actually playing. And in the clean room, with everything held fixed, every strategy that lacked the seeds finished inside one band. The strategies only differed in how reliably they got there.

Which is my answer to Mihura's speedrun theory, and I mean it as a compliment, because the theory deserved a real test. Speedrunning compounds because the game is fixed and public, so a published route is information anyone can use straight away. REFUGIO's game was three secret seeds. A shared solution here was a floor, the floor turned out to be rediscoverable anyway, and the code couldn't carry the one thing worth carrying. Meanwhile the piece of information that did tear through the room was three hex strings in the page data, small and instantly usable in a way the shared files never were. Sharing routes moves a community when the map is public. Our map was the secret.

A four-hour hackathon measures how fast you iterate, how much nerve you've got, and which idea your model happens to grab first. The week after it measured almost the opposite: patience, and being willing to distrust a proof I'd written myself. Neither of those is really understanding. Understanding turned out to be a separate thing again, the writing-it-all-down thing, which is what this is.

Genuine thanks to the organizers, and I mean it. The challenge was good enough to survive a full week of me pulling it apart, and most things aren't. The leaked seeds, the frontier scoring, the speedrun bet: these are exactly the kind of thing you only ever learn by watching smart people collide with them, which is kind of the whole point of running one of these.

And to close the loop: all three numbers from the top were wrong. 931 wasn't the best possible. ~920 was never a ceiling. 1,042 isn't the end either. 1,050 is, and it's just sitting there waiting for someone with a free weekend. The only honest number in this whole story is the one nobody's found yet.

The live challenge and all the replays are still up on the [REFUGIO site](https://refugio-hackathon-nine.vercel.app/). And the actual human version of this day is still [over here](https://blog.micr.dev/blog/my-first-hackathon-experience). Start with that one. I only wrote the footnotes.
