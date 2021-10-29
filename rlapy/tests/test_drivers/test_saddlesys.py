import unittest
import numpy as np
import scipy.linalg as la
import rlapy.drivers.saddlesys as rsad
import rlapy.comps.itersaddle as itersad
import rlapy.utils.sketching as usk


def make_simple_prob(m, n, spectrum, delta, rng):
    rng = np.random.default_rng(rng)

    # Construct the data matrix
    rank = spectrum.size
    U = usk.orthonormal_operator(m, rank, rng)
    Vt = usk.orthonormal_operator(rank, n, rng)
    A = (U * spectrum) @ Vt

    # Construct the right-hand-side
    prop_range = 0.7
    b0 = rng.standard_normal(m)
    b_range = U @ (U.T @ b0)
    b_orthog = b0 - b_range
    b_range *= (np.mean(spectrum) / la.norm(b_range))
    b_orthog *= (np.mean(spectrum) / la.norm(b_orthog))
    b = prop_range * b_range + (1 - prop_range) * b_orthog

    # Make c
    c = rng.standard_normal(n)

    # solve for x_opt, y_opt
    gram = A.T @ A + delta * np.eye(n)
    rhs = A.T @ b - c
    x_opt = la.solve(gram, rhs, sym_pos=True)
    y_opt = b - A @ x_opt

    # Return
    ath = AlgTestHelper(A, b, c, delta, x_opt, y_opt)
    return ath


class AlgTestHelper:

    def __init__(self, A, b, c, delta, x_opt, y_opt):
        """
        (x_opt, y_opt) solve ...

             [  I   |     A   ] [y_opt] = [b]
             [  A'  | -delta*I] [x_opt]   [c]

        the following characterization holds for x_opt ...

            (A' A + delta * I) x_opt = A'b - c.

        """
        self.A = A
        self.b = b
        self.c = c
        self.delta = delta
        self.x_opt = x_opt
        self.y_opt = y_opt
        self.x_approx = None
        self.y_approx = None
        self.tester = unittest.TestCase()

    def test_delta_xy(self, tol):
        """
        ||x - x_opt|| <= tol   and   ||y - y_opt|| <= tol
        """
        delta_x = self.x_opt - self.x_approx
        nrm = la.norm(delta_x, ord=2) / (1 + min(la.norm(self.x_opt),
                                                 la.norm(self.x_approx)))
        self.tester.assertLessEqual(nrm, tol)

        delta_y = self.y_opt - self.y_approx
        nrm = la.norm(delta_y, ord=2) / (1 + min(la.norm(self.y_opt),
                                                 la.norm(self.y_approx)))
        self.tester.assertLessEqual(nrm, tol)

    def test_normal_eq_residual(self, tol):
        """
        || (A' A + delta*I) x - (A' b - c)|| <= tol
        """
        rhs = self.A.T @ self.b - self.c
        lhs = self.A.T @ (self.A @ self.x_approx)
        lhs += self.delta * self.x_approx
        gap = rhs - lhs
        nrm = la.norm(gap, ord=2)
        self.tester.assertLessEqual(nrm, tol)

    def test_block_residual(self, tol):
        """
          ||   [  I   |     A   ] [y] - [b]   ||   <=   tol
          ||   [ A.T  | -delta*I] [x]   [c]   ||
        """
        block1 = self.y_approx + self.A @ self.x_approx - self.b
        block2 = self.A.T @ self.y_approx - self.delta * self.x_approx - self.c
        gap = np.concatenate([block1, block2])
        nrm = la.norm(gap, ord=2)
        self.tester.assertLessEqual(nrm, tol)


class TestSPS2(unittest.TestCase):
    #TODO: make a base class and have this superclass it

    def test_simple(self):
        alg = rsad.SPS2(
            sketch_op_gen=usk.sjlt_operator,
            sampling_factor=3,
            iterative_solver=itersad.PcSS2()
        )
        rng = np.random.default_rng(0)
        m, n = 1000, 100
        kappa = 1e5
        spectrum = np.linspace(kappa ** 0.5, kappa ** -0.5, num=n)

        delta = 0.0
        ath = make_simple_prob(m, n, spectrum, delta, rng)
        xy = alg(ath.A, ath.b, ath.c, ath.delta,
                 tol=1e-12, iter_lim=50,
                 rng=rng, logging=False)
        ath.x_approx = xy[0]
        ath.y_approx = xy[1]
        ath.test_normal_eq_residual(tol=1e-6)
        ath.test_block_residual(tol=1e-6)
        ath.test_delta_xy(tol=1e-6)

        delta = 1.0
        ath = make_simple_prob(m, n, spectrum, delta, rng)
        xy = alg(ath.A, ath.b, ath.c, ath.delta,
                 tol=1e-12, iter_lim=50,
                 rng=rng, logging=False)
        ath.x_approx = xy[0]
        ath.y_approx = xy[1]
        ath.test_normal_eq_residual(tol=1e-6)
        ath.test_block_residual(tol=1e-6)
        ath.test_delta_xy(tol=1e-6)