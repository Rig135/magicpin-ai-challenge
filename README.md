# Vera - magicpin AI Challenge

Vera is an intelligent, highly contextual Merchant AI Assistant designed to process adaptive context events (such as merchant milestones, changing statistics, and active customer signals) and generate ultra-specific, personalized, and actionable messages via the WhatsApp platform.

## Problem Statement
The goal is to build an autonomous agent that acts as a business copilot for magicpin merchants. The copilot must understand 5 distinct category voices (e.g. dentists, gyms, salons, restaurants, pharmacies), constantly adapt to real-time asynchronous context payload injections, and drive merchant engagement without hallucinating data or relying on outdated context. In addition, it must manage multi-turn conversations safely while distinguishing positive intent, negative hostility, and conversational noise (auto-replies).

## Architecture
Vera's architecture is structured as a clean FastAPI web service separating core logic from API endpoints:
- **`app/api`**: FastAPI routers encapsulating `POST /v1/context`, `POST /v1/tick`, `POST /v1/reply`.
- **`app/models`**: Pydantic schemas enforcing structural integrity for both request schemas and canonical domain entities.
- **`app/store`**: In-memory idempotency and context stores (`ContextStore`, `ConversationStore`) designed specifically to intercept and discard stale updates while storing the most recent accepted payload version.
- **`app/services`**: The core execution strategies, specifically `Composer`, `LLMClient`, and `TriggerRouter`.

## Context Model
We accept context via `POST /v1/context`. The system immediately deserializes payloads into generic validated schemas:
1. `CategoryContext`
2. `MerchantContext`
3. `CustomerContext`
4. `TriggerContext`

Each object is tracked with a `(scope, context_id)` composite key tied to an explicit integer `version`. Stale versions (`req.version <= current.version`) are outright rejected to prevent regressions.

## Routing Approach
During a tick execution (`POST /v1/tick`), Vera evaluates every available trigger.
The `TriggerRouter` maps the `trigger.kind` to one of several core semantic strategies:
- `digest`: Research and category data insights.
- `recall`: Customer follow-ups based on history.
- `performance`: Operational spike/dip reporting.
- `milestone`: Celebratory progress markers.
- `event`: Calendar or geographic external signals.
- `lapse`: Win-back workflows.
- `appointment`: Scheduling workflows.

## LLM Strategy
Vera connects to the Gemini (or fallback OpenAI) engine and issues highly constrained zero-shot composition prompts based on the selected `TriggerRouter` strategy.
Instead of relying on LLM creativity, Vera enforces a strict standard:
- Provide all available and updated context directly to the LLM formatted as JSON.
- Command the model to NEVER invent data or names.
- Ensure the model adopts the voice tone explicit in the `CategoryContext`.
- Return structured output (`body`, `cta`, `rationale`).

## Validation Strategy
Once the LLM returns a structured composed message, it undergoes a deterministic and LLM-assisted **Grounding Check**:
1. Checks for empty body, forbidden phrases, and CTA format issues.
2. Checks for hallucinations by prompting an internal grounding validator to identify if any numbers, dates, or claims were invented outside of the supplied Context map.
If the validation step flags errors, the Composer dynamically issues a retry prompt with instructions specifically targeted at correcting the raised error.

## Multi-turn Strategy
Multi-turn conversations (`POST /v1/reply`) leverage deterministic pre-processing to save LLM tokens and latency.
- **Auto-reply Detection**: Tracks consecutive duplicated auto-responses.
- **Negative Intent**: Regex/keyword checks for standard hostility (immediately outputs `action: end`).
- **Positive Intent**: Matches explicit positive affirmation (immediately outputs `action: send` with actionable next steps).
- **Nuanced Follow-ups**: If no deterministic boundary is crossed, the query alongside the full conversation history is sent to the LLM to classify the explicit intent (`wait`, `end`, `send`).

## Limitations
1. Memory is entirely volatile; restarting the server completely resets the conversation and context state.
2. Strict structural reliance on Pydantic might reject slightly non-conforming, yet valid context payloads if properties are entirely misplaced.
3. Complex multi-turn intents outside standard operational bounds might still struggle in zero-shot without fine-tuning.

## How to Run Locally
1. Clone the repository.
2. Install requirements: `pip install -r requirements.txt`
3. Ensure you have an active `.env` file containing `GEMINI_API_KEY`.
4. Run the server: `uvicorn app.main:app --port 8080 --reload`
5. Visit `http://localhost:8080/v1/healthz` to verify uptime.

## How to Run Judge Simulator
With the bot running locally on `port 8080`:
1. Ensure dependencies are installed and the dataset folder `dataset/` is available in the root.
2. Run `python judge_simulator.py`.
The judge will perform a warmup cycle and subsequently test multi-turn conversations and message composition against adaptive payload updates.

## Deployment Instructions (Checklist)
Before deploying to production, follow these steps:
- [ ] Environment variables configured for the production LLM Key (`GEMINI_API_KEY` / `OPENAI_API_KEY`).
- [ ] In-memory state classes (`ContextStore`, `ConversationStore`) mapped to a persistent remote datastore (e.g., Redis / Postgres) for horizontal scaling.
- [ ] Gunicorn configured to run multiple workers: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker`
- [ ] Rate limits monitored to ensure LLM interactions don't trigger platform blocks.
- [ ] Log streaming (e.g. Datadog or ELK) securely established on production instances for immediate hallucination tracking.
