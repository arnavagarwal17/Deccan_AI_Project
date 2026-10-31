"""Reward package initialization."""


def score(*args, **kwargs):
    from reward.score import score as _score
    return _score(*args, **kwargs)


__all__ = ["score"]
