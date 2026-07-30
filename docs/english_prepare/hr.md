# english prepare

## 1. self-introduction
### 1.1 key points
- 8 years total, last 3 years AI/Backend
- Shopee e-commerce background → directly relevant to Zalando
- End-to-end ownership: architecture → production → monitoring

### 1.2 details
Hello, my name is Wu Hong Lei. I'm a senior engineer with 8 years of development experience, and the last 3 years have been focused on AI and backend systems.

At Shopee — one of the largest e-commerce platforms in Southeast Asia — I built their internal AI assistant platform from scratch. I owned the full lifecycle: architecture design, core Agent engine, tool integration, RAG retrieval, all the way to production deployment and monitoring. It's now used daily by multiple teams.

I think this background is a strong fit for Zalando. Both are large-scale e-commerce companies dealing with high traffic, complex data pipelines, and the challenge of applying AI to real business scenarios. My experience building AI systems in an e-commerce context — understanding how teams actually use these tools day to day — is something I can bring directly to this role.

So yeah, that's a quick overview of my background. Happy to dive into any details.

## 2. greatest strengths and biggest weaknesses
### 2.1 key points
**Greatest strengths:**
- End-to-end Ownership: Ability to take ideas from architecture to production.
- Complex Problem Solving: Skilled in debugging complex ReAct loops and optimizing LLM latency.
- Continuous Learning: Always seeking new challenges and technologies to stay ahead.

**Biggest weaknesses:**
- Public Speaking: Occasionally feel nervous presenting to large groups. -> Action: Leading weekly tech shares to build confidence.
- Technical Depth vs. Speed: Tend to over-research details early on. -> Action: Adopting time-boxing to balance depth with MVP delivery.

### 2.2 details
**Greatest strengths:**
My greatest strength is end-to-end ownership. I don't just write code; I take full responsibility for the system's journey, from architectural design to production-grade deployment.

I also excel at complex problem solving. For instance, I'm skilled at debugging intricate ReAct loops and optimizing LLM latency to ensure a smooth user experience.

Lastly, I’m driven by continuous learning. I proactively master emerging AI technologies to drive innovation and stay ahead in this fast-evolving field.

**Weaknesses**
Regarding areas for improvement, one challenge I’ve faced is public speaking. I occasionally feel nervous when presenting to large groups. To overcome this, I’ve started leading weekly tech shares within my team, which has significantly built my confidence.

Another area is balancing technical depth with speed. In the past, I tended to over-research details early on. Now, I adopt time-boxing for my research phases. This helps me strike a better balance between deep technical exploration and timely MVP delivery.


## 3. daily work/weekly work/job responsibilities
### 3.1 key points
- Architecture & Design: Designing ReAct loops, defining tool interfaces, and planning system scalability.
- Core Development: Implementing Agent logic, integrating LLM APIs, and building RAG pipelines.
- Optimization & Observability: Tuning prompt performance, reducing latency, and setting up logging/tracing for production stability.
- Cross-functional Collaboration: Aligning with Product/Ops teams on requirements and explaining technical constraints.

### 3.2 details
In my current role at Shopee, my work revolves around four key areas.

First, I focus on architectural design, where I define how our Agents interact with various tools and manage context windows.

Second, I handle the core implementation, specifically building RAG pipelines and optimizing prompt engineering to ensure high-quality responses.

Third, I place a heavy emphasis on production stability. I’ve set up observability dashboards to track Agent latency and error rates, which allows us to iterate quickly.

Finally, a significant part of my week is spent on cross-functional collaboration. I work closely with product managers to translate their requirements into feasible technical solutions, ensuring our Agents truly solve user problems.

## 4. Challenges & Solutions
### 4.1 key points
- Technical Problems: Encountered unpredictable Agent behaviors (e.g., infinite loops or tool misuse) in production.
- Technical Trade-offs: Needed to choose between multiple solutions (A, B, C) for a new feature, each with different advantages and disadvantages (e.g., speed vs. accuracy vs. cost).

### 4.2 details
One significant challenge was dealing with unstable Agent behaviors in our production environment, such as infinite loops. To solve this, I didn't just patch the code; I dived into SOTA frameworks to see how they handle state transitions. By adopting their checkpointing logic, we significantly improved the system's reliability.

Another challenge is making technical trade-offs. For instance, when designing a RAG pipeline, we had three options varying in latency and accuracy. Instead of picking the most 'advanced' one, I evaluated them based on our business goal of fast user feedback. We chose a lighter model that boosted response speed by 30%, which ultimately drove higher user engagement.
