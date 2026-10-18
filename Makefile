.PHONY: dev down test lint seed verify sample evaluate openapi
dev:
	docker compose up --build --wait
down:
	docker compose down
test:
	docker compose run --rm --no-deps api pytest -q
	docker compose run --rm --no-deps api python scripts/evaluate_detector.py
	docker compose run --rm --no-deps api python scripts/export_openapi.py --check
	docker compose run --rm --no-deps web npm test -- --run
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

