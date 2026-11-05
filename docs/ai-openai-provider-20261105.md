# OpenAI provider follow-up — November5,2026

Core0.10.0 remains a candidate. A new key was created only after the user
confirmed its local `.env.local` destination. Git's local exclusion protects
that untracked file; no credential is added to source, packages or WSL config.
The private repository-signing key remains local and unchanged.

## Provider gap repaired

The native app previously offered NIM, Gemini and OpenVINO; the Python client
did not route OpenAI credentials. A shell fallback even counted an OpenAI key
as a NIM credential. OpenAI is now an independent CLI/native-GUI choice with
its own key, URL, model and aliases. Other providers keep their credentials.
Existing provider selection is preserved; this does not silently select OpenAI.

OpenAI requests use Chat Completions with `max_completion_tokens`. Default
`gpt-6-luna` uses `reasoning_effort:none`; temperature is omitted to avoid
incompatible reasoning-model options. Explicit model overrides remain available.
See the [official model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [request reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

Quota exhaustion and transient request-rate limits produce different messages.
Authentication/model-access, network, malformed and empty responses fail clearly.
Configuration output fully redacts all provider keys, including their prefixes.
No retry loop spends additional requests after exhausted balance.

## Evidence and remaining live gate

Six offline provider tests exercise credential/endpoint separation, auto
selection, environment/model aliases, payload limits, streaming/nonstreaming,
quota/rate classification, malformed/empty responses and redaction. The CLI/
fallback regression and native GTK streaming/cancel/read-failure checks pass.
Graphite/Paper native renders show the added OpenAI choice and model without
changing control dimensions or theme layout. Impeccable4.8.0 guidance was used.

The new key authenticates against the models endpoint. The first GPT-4.1-nano
probe returned `model_not_found`; this is retained as an unsuccessful probe.
A documented current starter model, GPT-6 Luna, reaches the API but returns
HTTP429, `insufficient_quota` / `credit_balance_exhausted`. No successful live
generation, long cloud transcript, live cancellation or recovery is claimed.
Item11's live gate remains pending available API balance; no more paid requests
are made by this pass. OpenVINO and physical/held VM checks remain deferred.

Private probes/captures stay under
`C:\Users\7ryan\AppData\Local\Temp\ooonana-ai-provider-20261105\`.
Signed publication/installed receipt follows offline package validation.
