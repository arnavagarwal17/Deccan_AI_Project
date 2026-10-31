.PHONY: setup pipeline quality score rollouts report-data zip clean

PYTHON ?= python
COUNT ?= 30
SEED ?= 42
PROBE_N ?= 2

setup:
	$(PYTHON) -m pip install -r requirements.txt
	playwright install chromium

pipeline:
	$(PYTHON) -m pipeline.generate --count $(COUNT) --seed $(SEED)

quality:
	$(PYTHON) -m quality.run_all --probe-n $(PROBE_N)

score:
	$(PYTHON) -m reward.score --submission tasks/calm-wave-fintech/solution --config tasks/calm-wave-fintech/tests/grader_config.json --capture out/capture

rollouts:
	$(PYTHON) -m rollouts.run --probe-n $(PROBE_N)

report-data:
	$(PYTHON) -m rollouts.summary

zip:
	$(PYTHON) -c "import zipfile, os; \
	z = zipfile.ZipFile('submission.zip', 'w', zipfile.ZIP_DEFLATED); \
	skip_dirs = {'.venv', '__pycache__', '.git', '.gemini', 'out'}; \
	[z.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), '.')) \
	 for root, dirs, files in os.walk('.') if not any(s in root for s in skip_dirs) \
	 for f in files if not f.endswith(('.pyc', '.zip')) and os.path.getsize(os.path.join(root, f)) < 20*1024*1024]; \
	z.close(); \
	print(f'Created submission.zip ({os.path.getsize(\"submission.zip\")/1024/1024:.2f} MB)')"

clean:
	rm -rf out /tmp/cap rollouts/*.png quality/rejected

