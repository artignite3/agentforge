from evals.compare import p95, summarize


def test_summary_separates_client_errors_and_uses_nearest_rank_p95():
    finished = {
        "verified": True,
        "model_calls": 5,
        "estimated_cost_usd": 0.001,
    }
    group = [{**finished, "execution_ms": ms} for ms in (100, 200, 300, 400)] + [
        {"client_error": "TimeoutError"}
    ]
    stats = summarize(group)
    assert stats["runs"] == 5
    assert stats["verified"] == 4 and stats["verified_rate"] == 0.8
    assert stats["client_errors"] == 1
    assert stats["execution_ms_median"] == 250
    assert stats["execution_ms_p95"] == 400
    assert p95([7]) == 7
