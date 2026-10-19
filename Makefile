.PHONY: dev down test lint seed verify sample evaluate openapi types e2e run-alerts outbox chat-eval chat-eval-live
dev:
	docker compose up --build --wait
down:
	docker compose down
test:
	docker compose run --rm --no-deps api pytest -q
	docker compose run --rm --no-deps api python scripts/evaluate_detector.py
	docker compose run --rm --no-deps api python scripts/export_openapi.py --check
	docker compose run --rm --no-deps web npm test -- --run
	docker compose run --rm --no-deps web npm run types:check
lint:
	docker compose run --rm --no-deps api ruff check .
	docker compose run --rm --no-deps web npm run lint
	docker compose run --rm --no-deps web npm run typecheck
seed:
	docker compose exec api python scripts/seed_demo.py
verify:
	python scripts/verify_stack.py
sample:
	docker compose run --rm --no-deps api python scripts/gen_sample_data.py
evaluate:
	docker compose run --rm --no-deps api python scripts/evaluate_detector.py
openapi:
	docker compose run --rm --no-deps api python scripts/export_openapi.py
types:
	docker compose run --rm --no-deps web npm run types
e2e:
	python scripts/run_e2e.py

chat-eval:
	docker compose run --rm --no-deps api pytest -q -s tests/test_chat_evals.py

chat-eval-live:
	docker compose run --rm --no-deps -e SUBTRACK_LIVE_EVAL=1 api pytest -q -s tests/test_chat_evals.py
run-alerts:
	docker compose exec -T api python -m app.jobs run $(if $(AS_OF),--as-of $(AS_OF),)
outbox:
	python -c "from pathlib import Path; Path('var/outbox').mkdir(parents=True, exist_ok=True)"
	docker compose cp api:/var/subtrack/outbox/. var/outbox

