from engine.autoresearch import EvidenceAutoresearchController


def test_failed_gap_rotates_strategy():
    controller = EvidenceAutoresearchController()
    gap = {"gap_id": "G", "gap_type": "missing_transfer", "priority": "high"}
    priority = controller.select_gap([gap])
    first = controller.build_strategy(priority, gap, [])
    history = [
        {
            "gap_id": "G",
            "strategy": {"experiment_type": first.experiment_type.value},
        }
    ]
    second = controller.build_strategy(priority, gap, history)
    assert first.experiment_type != second.experiment_type
