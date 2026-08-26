from roulette_fibonacci.strategy import FibonacciStrategy, build_sequence


def test_build_sequence_default_six_steps():
    assert build_sequence(6) == [1, 1, 2, 3, 5, 8]


def test_bet_progression_on_losses_matches_fibonacci():
    s = FibonacciStrategy(unit=1.0, max_steps=6)
    bets = [s.current_bet()]
    for _ in range(6):
        s.register_result(won=False)
        bets.append(s.current_bet())
    assert bets == [1, 1, 2, 3, 5, 8, 8]


def test_bet_stays_capped_after_max_steps_losses():
    s = FibonacciStrategy(unit=1.0, max_steps=6)
    for _ in range(10):
        s.register_result(won=False)
    assert s.current_bet() == 8
    assert s.capped


def test_win_retreats_two_steps():
    s = FibonacciStrategy(unit=1.0, max_steps=6)
    for _ in range(4):
        s.register_result(won=False)
    assert s.current_bet() == 5
    s.register_result(won=True)
    assert s.current_bet() == 2


def test_win_at_start_stays_at_start():
    s = FibonacciStrategy(unit=1.0, max_steps=6)
    s.register_result(won=True)
    assert s.at_start
    assert s.current_bet() == 1


def test_unit_scales_the_whole_sequence():
    s = FibonacciStrategy(unit=2.5, max_steps=6)
    for _ in range(4):
        s.register_result(won=False)
    assert s.current_bet() == 12.5
