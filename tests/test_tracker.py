import pytest

from apuestas.tracker import Bet, BetLog, analyse


def make_bet(bet_id="b00001", odds=2.0, stake=10.0, status="open", closing=0.0):
    return Bet(
        bet_id=bet_id,
        date="2026-01-01",
        event="Test",
        selection="A",
        book="soft",
        odds_taken=odds,
        p_estimate=0.55,
        stake=stake,
        ev_pct=0.10,
        status=status,
        closing_odds=closing,
    )


def test_profit_on_win_excludes_the_stake():
    assert make_bet(odds=2.5, stake=10, status="won").profit == pytest.approx(15.0)


def test_profit_on_loss_is_the_stake():
    assert make_bet(stake=10, status="lost").profit == -10.0


def test_open_and_void_bets_have_no_profit():
    assert make_bet(status="open").profit == 0.0
    assert make_bet(status="void").profit == 0.0
    assert not make_bet(status="void").settled


def test_clv_positive_when_you_beat_the_close():
    assert make_bet(odds=2.10, closing=2.00).clv == pytest.approx(0.05)


def test_clv_negative_when_the_line_moves_against_you():
    assert make_bet(odds=1.90, closing=2.00).clv == pytest.approx(-0.05)


def test_clv_is_zero_without_a_closing_price():
    assert make_bet(odds=2.10, closing=0.0).clv == 0.0


def test_log_roundtrips_through_csv(tmp_path):
    path = str(tmp_path / "bets.csv")
    log = BetLog(path)
    log.add(make_bet("b00001", odds=2.5, closing=2.3))
    log.settle("b00001", "won")

    reloaded = BetLog(path)
    assert len(reloaded.bets) == 1
    bet = reloaded.bets[0]
    assert bet.status == "won"
    assert bet.odds_taken == 2.5
    assert bet.closing_odds == 2.3
    assert bet.profit == pytest.approx(15.0)


def test_duplicate_bet_id_rejected(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    log.add(make_bet("b00001"))
    with pytest.raises(ValueError):
        log.add(make_bet("b00001"))


def test_settle_unknown_id_raises(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    with pytest.raises(KeyError):
        log.settle("nope", "won")


def test_invalid_status_rejected(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    with pytest.raises(ValueError):
        log.add(make_bet(status="maybe"))


def test_next_id_increments(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    assert log.next_id() == "b00001"
    log.add(make_bet("b00001"))
    assert log.next_id() == "b00002"


def test_analyse_computes_roi_and_hit_rate(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    log.add(make_bet("b00001", odds=2.0, stake=10, status="won"))
    log.add(make_bet("b00002", odds=2.0, stake=10, status="lost"))

    stats = analyse(log)
    assert stats["settled"] == 2
    assert stats["staked"] == 20
    assert stats["profit"] == 0.0
    assert stats["roi"] == 0.0
    assert stats["hit_rate"] == 0.5


def test_analyse_excludes_open_bets_from_roi(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    log.add(make_bet("b00001", stake=10, status="won"))
    log.add(make_bet("b00002", stake=999, status="open"))

    stats = analyse(log)
    assert stats["settled"] == 1
    assert stats["open"] == 1
    assert stats["staked"] == 10


def test_analyse_reports_clv_only_for_bets_with_closing_odds(tmp_path):
    log = BetLog(str(tmp_path / "bets.csv"))
    log.add(make_bet("b00001", odds=2.10, status="won", closing=2.00))
    log.add(make_bet("b00002", odds=2.20, status="lost", closing=2.00))
    log.add(make_bet("b00003", odds=2.00, status="won", closing=0.0))

    stats = analyse(log)
    assert stats["with_closing_line"] == 2
    assert stats["beat_close_rate"] == 1.0
    assert stats["avg_clv"] == pytest.approx(0.075)


def test_analyse_handles_empty_log(tmp_path):
    stats = analyse(BetLog(str(tmp_path / "bets.csv")))
    assert stats["total_bets"] == 0
    assert "roi" not in stats
