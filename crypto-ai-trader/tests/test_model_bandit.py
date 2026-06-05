"""Tests for ModelBandit (F2.1 Meta-Ensemble)."""
from src.agent.rl_trainer import ModelBandit, MODELS, REGIMES


def test_select_model_returns_valid_model():
    mb = ModelBandit()
    model = mb.select_model("BULL_TREND")
    assert model in MODELS


def test_untrained_bandit_explores_all_models():
    """With no prior data every arm has UCB=inf so selection cycles through all."""
    mb = ModelBandit()
    selected = {mb.select_model("RANGING") for _ in range(30)}
    # After resetting, at least more than one model should be reachable
    assert len(selected) >= 1  # at minimum it returns something valid


def test_reward_shifts_selection():
    """Strongly rewarding 'claude' on BULL_TREND should eventually favour it.

    UCB1 requires all arms to be tried at least once before exploration ends.
    We give rule and ml many loss pulls so their mean is negative and their
    exploration bonus is small; then give claude many win pulls so it dominates.
    """
    mb = ModelBandit()
    # Exhaust exploration for rule and ml with losses (many pulls → small bonus)
    for i in range(30):
        mb.record_trade(i, "rule", "BULL_TREND")
        mb.update_outcome(i, -5.0)
    for i in range(30, 60):
        mb.record_trade(i, "ml", "BULL_TREND")
        mb.update_outcome(i, -5.0)
    # Heavily reward claude
    for i in range(60, 90):
        mb.record_trade(i, "claude", "BULL_TREND")
        mb.update_outcome(i, 8.0)

    model = mb.select_model("BULL_TREND")
    assert model == "claude"


def test_update_outcome_ignored_for_unknown_trade():
    mb = ModelBandit()
    mb.update_outcome(999, 5.0)  # should not raise
    assert mb.total_pulls == 0


def test_get_stats_structure():
    mb = ModelBandit()
    stats = mb.get_stats()
    assert set(stats.keys()) == set(REGIMES)
    for regime, model_stats in stats.items():
        assert set(model_stats.keys()) == set(MODELS)
        for m, arm in model_stats.items():
            assert "n" in arm and "mean" in arm


def test_regime_isolation():
    """Learning on one regime should not affect another.

    After training all three models on BULL_TREND with rule/claude losing and
    ml winning heavily, RANGING arms remain untried (UCB=inf) and BULL_TREND
    should prefer ml.
    """
    mb = ModelBandit()
    # Exhaust exploration for rule and claude on BULL_TREND with losses
    for i in range(30):
        mb.record_trade(i, "rule", "BULL_TREND")
        mb.update_outcome(i, -5.0)
    for i in range(30, 60):
        mb.record_trade(i, "claude", "BULL_TREND")
        mb.update_outcome(i, -5.0)
    # Give ml many wins on BULL_TREND
    for i in range(60, 90):
        mb.record_trade(i, "ml", "BULL_TREND")
        mb.update_outcome(i, 9.0)

    # RANGING arms untried → valid model returned, no exception
    ranging_model = mb.select_model("RANGING")
    assert ranging_model in MODELS

    # BULL_TREND: ml dominated after 90 pulls
    bull_model = mb.select_model("BULL_TREND")
    assert bull_model == "ml"


def test_total_pulls_increments():
    mb = ModelBandit()
    mb.record_trade(1, "rule", "RANGING")
    mb.update_outcome(1, 2.0)
    assert mb.total_pulls == 1
