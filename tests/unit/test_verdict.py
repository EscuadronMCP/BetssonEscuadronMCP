from betsson_validator.domain.verdict import (
    Outcome,
    Status,
    Testimony,
    WitnessKind,
    evaluate,
)


def screen(outcome: Outcome) -> Testimony:
    return Testimony(witness="pantalla", kind=WitnessKind.VISUAL, outcome=outcome, detail="d")


def corroborating(name: str, outcome: Outcome) -> Testimony:
    return Testimony(witness=name, kind=WitnessKind.CORROBORATING, outcome=outcome, detail="d")


def test_pass_when_all_witnesses_confirm() -> None:
    result = evaluate("saldo", (screen(Outcome.CONFIRMS), corroborating("red", Outcome.CONFIRMS)))
    assert result.status is Status.PASS


def test_screen_is_mandatory_even_if_others_confirm() -> None:
    result = evaluate(
        "saldo", (screen(Outcome.UNAVAILABLE), corroborating("historial", Outcome.CONFIRMS))
    )
    assert result.status is Status.FAIL


def test_no_witnesses_is_fail() -> None:
    assert evaluate("saldo", ()).status is Status.FAIL


def test_corroborating_contradiction_is_discrepancy() -> None:
    result = evaluate(
        "premio", (screen(Outcome.CONFIRMS), corroborating("historial", Outcome.CONTRADICTS))
    )
    assert result.status is Status.FAIL
    assert "Discrepancia" in result.reason
    assert "historial" in result.reason


def test_unavailable_witness_does_not_block_pass_but_is_reported() -> None:
    result = evaluate(
        "saldo", (screen(Outcome.CONFIRMS), corroborating("red", Outcome.UNAVAILABLE))
    )
    assert result.status is Status.PASS
    assert result.unavailable_witnesses == ("red",)


def test_contradicting_screen_readings_fail() -> None:
    result = evaluate("apuesta", (screen(Outcome.CONFIRMS), screen(Outcome.CONTRADICTS)))
    assert result.status is Status.FAIL


def test_withdrawn_evidence_turns_a_confirmation_into_unavailable() -> None:
    from betsson_validator.domain.verdict import withdraw_evidence  # noqa: PLC0415

    seen = Testimony(
        witness="pantalla",
        kind=WitnessKind.VISUAL,
        outcome=Outcome.CONFIRMS,
        detail="d",
        evidence=("captura.jpg",),
    )
    result = withdraw_evidence(evaluate("saldo", (seen,)), {"captura.jpg"})
    assert result.status is Status.FAIL
    assert result.testimonies[0].outcome is Outcome.UNAVAILABLE


def test_withdrawn_evidence_never_hides_a_contradiction() -> None:
    from betsson_validator.domain.verdict import withdraw_evidence  # noqa: PLC0415

    against = Testimony(
        witness="red",
        kind=WitnessKind.CORROBORATING,
        outcome=Outcome.CONTRADICTS,
        detail="d",
        evidence=("trafico.json",),
    )
    result = withdraw_evidence(
        evaluate("saldo", (screen(Outcome.CONFIRMS), against)), {"trafico.json"}
    )
    assert result.status is Status.FAIL
    assert result.testimonies[1].outcome is Outcome.CONTRADICTS


def test_a_visual_contradiction_is_reported_as_such() -> None:
    against = Testimony(
        witness="cabecera",
        kind=WitnessKind.VISUAL,
        outcome=Outcome.CONTRADICTS,
        detail="saldo 0.00 EUR → 0.01 EUR",
    )
    result = evaluate("saldo", (against,))
    assert result.status is Status.FAIL
    assert "contradice" in result.reason
    assert "0.01 EUR" in result.reason
