from github_ai_trend_radar.processors.dedupe import dedupe_candidates


def test_dedupe_merges_source_hits_for_same_repo():
    merged = dedupe_candidates(
        [
            {"repo_full_name": "Owner/Repo", "source_hits": ["ossinsight"], "metrics": {}, "metadata": {}},
            {"repo_full_name": "owner/repo", "source_hits": ["github_search"], "metrics": {}, "metadata": {}},
        ]
    )

    assert len(merged) == 1
    assert merged[0]["source_hits"] == ["ossinsight", "github_search"]


def test_dedupe_preserves_non_empty_readme_excerpt():
    merged = dedupe_candidates(
        [
            {"repo_full_name": "owner/repo", "source_hits": ["ossinsight"], "metrics": {}, "metadata": {}, "readme_excerpt": ""},
            {
                "repo_full_name": "owner/repo",
                "source_hits": ["github_search"],
                "metrics": {},
                "metadata": {},
                "readme_excerpt": "hello",
            },
        ]
    )

    assert merged[0]["readme_excerpt"] == "hello"
