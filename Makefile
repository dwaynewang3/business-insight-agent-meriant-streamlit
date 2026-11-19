.PHONY: data test-data stress-data cases test lint ask eval demo

data: ## Build the dev warehouse (data/dev.duckdb), its manifest, and the policy knowledge base
	uv run python -m data.generator --scenario data/scenarios/dev.yaml
	uv run python -m mcp_servers.policies.build

test-data: ## Build the held-out test data (data/test.duckdb), scored once at the end
	uv run python -m data.generator --scenario data/scenarios/test.yaml

stress-data: ## Build the stress data (data/stress.duckdb): two causes, no cause in the data, a recode
	uv run python -m data.generator --scenario data/scenarios/stress.yaml

cases: ## Print every eval question
	uv run python -m evals.cases

test: ## Run the test suite
	uv run pytest -q

lint: ## Check code style
	uv run ruff check .

ask: ## Ask the agent a question, then follow-ups: make ask Q="..." ROLE=head_of_claims
	uv run python -m agent --role $(or $(ROLE),head_of_claims) "$(Q)"

eval: ## Run and grade eval cases (costs API credits): make eval SUBSET=smoke|all KIND=why REPEATS=3
	uv run python -m evals.run_evals --kind $(or $(KIND),what) $(if $(REPEATS),--repeats $(REPEATS)) \
		$(if $(filter all,$(SUBSET)),,--subset $(or $(SUBSET),smoke))

demo: ## Open the UI. The guided demo needs no API key; the data is built first if it's missing.
	@test -f data/dev_restricted.duckdb || $(MAKE) data
	uv run streamlit run app/main.py --server.address localhost
