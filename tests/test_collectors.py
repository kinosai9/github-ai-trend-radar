from github_ai_trend_radar.collectors.ossinsight import ossinsight_period


def test_ossinsight_period_mapping():
    assert ossinsight_period("daily") == "past_24_hours"
    assert ossinsight_period("weekly") == "past_week"
    assert ossinsight_period("monthly") == "past_month"
