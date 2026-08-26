from roulette_fibonacci.labouchere import Labouchere


def test_single_win_reaches_target():
    s = Labouchere(target=1, unit=1.0)
    assert s.current_bet() == 1.0
    s.register_result(won=True)
    assert s.complete


def test_loss_appends_stake_to_line():
    s = Labouchere(target=1, unit=1.0)
    s.register_result(won=False)
    assert s.line == [1.0, 1.0]
    assert s.current_bet() == 2.0


def test_loss_then_win_nets_the_target():
    """The defining property: a win after a loss still delivers exactly +1."""
    s = Labouchere(target=1, unit=1.0)
    profit = 0.0

    bet = s.current_bet()
    profit -= bet
    s.register_result(won=False)

    bet = s.current_bet()
    profit += bet
    s.register_result(won=True)

    assert s.complete
    assert profit == 1.0


def test_win_removes_both_ends():
    s = Labouchere(target=1, unit=1.0, line=[1.0, 2.0, 3.0])
    assert s.current_bet() == 4.0
    s.register_result(won=True)
    assert s.line == [2.0]


def test_line_grows_only_on_losses():
    s = Labouchere(target=1, unit=1.0)
    for _ in range(5):
        s.register_result(won=False)
    assert len(s.line) == 6
    assert s.current_bet() > 1.0


def test_outstanding_tracks_promised_profit():
    s = Labouchere(target=3, unit=1.0)
    assert s.outstanding == 3.0
