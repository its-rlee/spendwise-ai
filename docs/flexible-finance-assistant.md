# SpendWise: flexible financial question answering

This feature replaces the fixed Gemini intent list with a **bounded structured
query grammar**. Users can combine sources, dates, merchants, product names,
categories, grouping, sorting, and aggregations in many ways without
adding a new intent for every question.

## How it works

1. FastAPI authenticates the user via Supabase.
2. Gemini receives the current question, UTC date, and up to six recent chat
   turns, and returns up to three **query specifications** (JSON, never SQL).
3. Pydantic rejects unsupported fields, operations, sources, oversized results,
   invalid date ranges, and incompatible product filters.
4. SQLAlchemy compiles a fixed set of read-only operations. Every query is
   scoped by `Transaction.user_id == authenticated_user.id`.
5. FastAPI builds a deterministic response from **approved** transactions and
   individual receipt items, with machine-readable query results in `facts`.
   Gemini is **not** used to invent, compute, or rephrase monetary values.
6. Flutter displays the conversation and sends the last six messages for
   follow-up questions. The chat exists only in in-memory Flutter state;
   it is not saved by this feature.

## Configure

In `backend/.env` (never commit secrets):

```dotenv
FINANCE_AI_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=your-key-held-privately
```

The model ID must be available for your project; no paid plan is required by
the implementation, but quota, service availability, eligibility and privacy
terms depend on Google's API. Never ship the key to Flutter.

From the repo root:

```powershell
docker compose up -d --build --force-recreate api
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
cd mobile
flutter analyze
flutter test
```

## Example questions

- "How much was my most recently recorded receipt?"
- "What products did I buy at Costco?"
- "When did I last buy chicken?"
- "What categories did my reviewed receipt items fall under?"
- "Compare my monthly spending between January and October 2026."
- "How much did I spend on weekends this year?"
- "Which merchants account for most of my spending?"
- "And only at Costco?" (follow-up referencing an earlier query)

## Limits and safety

- Financial records are sensitive: even though Gemini doesn't receive raw
  database tables by default, the user's question and last six conversation
  turns (including previous answers) are sent to Google's API for planning.
  Explain this clearly to real users, and verify provider data usage terms.
- The system is **not an arbitrary SQL engine**, doesn't support writes, and
  doesn't answer every imaginable question. Unsupported or unanswerable
  requests receive a clear response, not fabricated numbers.
- Currency is filtered per query; values from distinct currencies are never
  silently summed together.
- Item amounts are **receipt line amounts**, not verified unit prices.
  Apparent price increases may reflect quantity, promotions or extraction
  mistakes, and item totals may differ from receipt totals.
- Each query returns at most 25 rows; a question may execute up to 3
  queries. Group aggregates use the matching approved records, with at
  most 25 groups returned.
- This implementation does not persist chat history server-side, perform
  model-generated SQL, or expose privileged Supabase keys.
- For a public production deployment, add per-user rate limits, request
  budgets, explicit financial-AI consent, observability without sensitive
  logging, and additional benchmarks for answer correctness.
