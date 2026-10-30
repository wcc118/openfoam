"""Linear diagonal modal dynamics; no aerodynamic or coupling model.

Right-hand generalized coordinates satisfy M*a + C*v + K*q = force.
Newmark average acceleration uses beta=1/4, gamma=1/2. Forces are endpoint
values. Caller owns coupling iteration, time quadrature, and convergence.
"""
from dataclasses import dataclass
import numpy as np


def _vector(value, name, size=None):
    a = np.asarray(value, dtype=float)
    if a.ndim != 1 or not a.size or not np.isfinite(a).all():
        raise ValueError(f'{name} must be a nonempty finite 1D vector')
    if size is not None and a.size != size:
        raise ValueError(f'{name} length must be {size}')
    return tuple(float(x) for x in a)


@dataclass(frozen=True)
class State:
    """Owned immutable checkpoint, including force at this endpoint."""
    q: tuple
    v: tuple
    a: tuple
    force: tuple
    time: float = 0.0

    def __post_init__(self):
        q = _vector(self.q, 'q')
        object.__setattr__(self, 'q', q)
        for name in ('v', 'a', 'force'):
            object.__setattr__(self, name, _vector(getattr(self, name), name, len(q)))
        t = float(self.time)
        if not np.isfinite(t):
            raise ValueError('time must be finite')
        object.__setattr__(self, 'time', t)


@dataclass(frozen=True)
class ModalSystem:
    """Diagonal coefficients; zero stiffness explicitly supports rigid modes."""
    mass: tuple
    damping: tuple
    stiffness: tuple

    def __post_init__(self):
        mass = _vector(self.mass, 'mass')
        object.__setattr__(self, 'mass', mass)
        for name in ('damping', 'stiffness'):
            object.__setattr__(self, name, _vector(getattr(self, name), name, len(mass)))
        if min(mass) <= 0 or min(self.damping) < 0 or min(self.stiffness) < 0:
            raise ValueError('require mass>0, damping>=0, stiffness>=0')

    def initial_state(self, q, v, force, time=0.0):
        n = len(self.mass)
        q, v, force = [np.array(_vector(x, name, n))
                       for x, name in ((q, 'q'), (v, 'v'), (force, 'force'))]
        a = (force - np.array(self.damping)*v - np.array(self.stiffness)*q)/self.mass
        return State(q, v, a, force, time)

    def _check(self, state):
        if not isinstance(state, State) or len(state.q) != len(self.mass):
            raise ValueError('state must match modal system')
        lhs = (np.array(self.mass)*state.a + np.array(self.damping)*state.v
               + np.array(self.stiffness)*state.q)
        scale = np.maximum(1.0, np.abs(np.array(self.mass)*state.a)
                           + np.abs(np.array(self.damping)*state.v)
                           + np.abs(np.array(self.stiffness)*state.q)
                           + np.abs(state.force))
        if not np.all(np.abs(lhs-state.force) <= 1e-12*scale):
            raise ValueError('state acceleration must satisfy endpoint equilibrium')

    def checkpoint(self, state):
        self._check(state)
        return State(state.q, state.v, state.a, state.force, state.time)

    def restore(self, checkpoint):
        """Return the complete accepted endpoint; rejected steps have no side effects."""
        return self.checkpoint(checkpoint)

    def step(self, state, next_force, dt):
        self._check(state)
        if np.ndim(dt) != 0 or not np.isfinite(dt) or dt <= 0:
            raise ValueError('dt must be a positive finite scalar')
        dt = float(dt)
        f = np.array(_vector(next_force, 'next_force', len(self.mass)))
        m, c, k = map(np.array, (self.mass, self.damping, self.stiffness))
        q, v, a = map(np.array, (state.q, state.v, state.a))
        qp, vp = q + dt*v + .25*dt*dt*a, v + .5*dt*a
        an = (f-c*vp-k*qp)/(m+.5*dt*c+.25*dt*dt*k)
        return State(qp+.25*dt*dt*an, vp+.5*dt*an, an, f, state.time+dt)
