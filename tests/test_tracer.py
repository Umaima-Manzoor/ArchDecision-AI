from datetime import datetime
from app.agent.tracer import Tracer

class TestTracer:

    def test_starts_empty(self):
        tracer = Tracer()
        assert tracer.get_steps() == []       # no steps recorded yet

    def test_log_adds_step(self):
        tracer = Tracer()
        tracer.log("planning", "Decomposing query into 5 axes")
        steps = tracer.get_steps()
        assert len(steps) == 1
        assert steps[0].step == "planning"
        assert steps[0].detail == "Decomposing query into 5 axes"

    def test_timestamp_is_iso_format(self):
        tracer = Tracer()
        tracer.log("searching", "Running Tavily queries")
        timestamp = tracer.get_steps()[0].timestamp
        # isoformat() produces strings like "2026-11-15T10:30:45.123456+00:00"
        parsed = datetime.fromisoformat(timestamp)       # will raise ValueError if not valid ISO
        assert parsed.year >= 2026       # sanity check that the timestamp is recent

    def test_multiple_steps_accumulate_in_order(self):
        tracer = Tracer()
        tracer.log("planning", "Step 1")
        tracer.log("searching", "Step 2")
        tracer.log("cleaning", "Step 3")
        tracer.log("synthesizing", "Step 4")
        tracer.log("done", "Step 5")
        steps = tracer.get_steps()
        assert len(steps) == 5
        assert steps[0].step == "planning"
        assert steps[1].step == "searching"
        assert steps[2].step == "cleaning"
        assert steps[3].step == "synthesizing"
        assert steps[4].step == "done"

    def test_each_tracer_is_independent(self):       # two tracers should not share state
        tracer_a = Tracer()
        tracer_b = Tracer()
        tracer_a.log("planning", "Only in A")
        assert len(tracer_a.get_steps()) == 1
        assert len(tracer_b.get_steps()) == 0       # B is unaffected

    def test_usage_starts_at_zero(self):        # token counters should be zero before any LLM calls
        tracer = Tracer()
        assert tracer.total_prompt_tokens == 0
        assert tracer.total_completion_tokens == 0

    def test_add_usage_accumulates(self):       # simulate planner + synthesizer each adding their token counts
        tracer = Tracer()
        tracer.add_usage(800, 120)      # planner: 800 input tokens, 120 output tokens
        tracer.add_usage(3200, 950)     # synthesizer: 3200 input tokens (sources in prompt), 950 output tokens (matrix)
        assert tracer.total_prompt_tokens == 4000       # 800 + 3200
        assert tracer.total_completion_tokens == 1070   # 120 + 950