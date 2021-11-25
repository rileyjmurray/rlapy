import scipy.linalg as la
import scipy.sparse.linalg as sparla
import parla.utils.linalg_wrappers as law
import numpy as np


def a_lift(A, scale):
    if scale == 0:
        return A
    else:
        A = np.row_stack((A, scale*np.eye(A.shape[1], dtype=A.dtype)))
        # Explicitly augmenting A seems like overkill.
        # However, it's faster than the LinearOperator approach I tried.
        return A

#TODO: consolidate the r and M cases below.
#   use a flag for upper-triangular.

#TODO: rename functions here ("times" and "inv_r" and "m" is a mess).


def a_times_inv_r(A, delta, R, k=1):
    """Return a linear operator that represents [A; sqrt(delta)*I] @ inv(R)
    """
    if k != 1:
        raise NotImplementedError()

    sqrt_delta = np.sqrt(delta)
    A_lift = a_lift(A, sqrt_delta)
    m = A.shape[0]

    def forward(arg, work):
        np.copyto(work, arg)
        work = la.solve_triangular(R, work, lower=False, check_finite=False,
                                   overwrite_b=True)
        out = A_lift @ work
        return out

    Radj = R.T.conj() if law.is_complex(R) else R.T

    def adjoint(arg, work):
        np.dot(A.T, arg[:m], out=work)
        if delta > 0:
            work += sqrt_delta * arg[m:]
        out = la.solve_triangular(Radj, work, lower=True, check_finite=False)
        return out

    vec_work = np.zeros(A.shape[1], dtype=R.dtype)
    mv = lambda vec: forward(vec, vec_work)
    rmv = lambda vec: adjoint(vec, vec_work)
    # if k != 1 then we'd need to allocate workspace differently.
    # (And maybe use workspace differently.)

    A_precond = sparla.LinearOperator(shape=A_lift.shape,
                                      matvec=mv, rmatvec=rmv,
                                      dtype=R.dtype)

    M_fwd = lambda z: la.solve_triangular(R, z, lower=False)
    M_adj = lambda w: la.solve_triangular(Radj, w, lower=True)

    return A_precond, M_fwd, M_adj


def a_times_m(A, delta, M, k=1):
    if k != 1:
        raise NotImplementedError()

    sqrt_delta = np.sqrt(delta)
    A = A.astype(M.dtype)
    A_lift = a_lift(A, sqrt_delta)
    m = A.shape[0]

    def forward(arg, work):
        np.dot(M, arg, out=work)
        out = A_lift @ work
        return out

    is_complex = law.is_complex(M)
    M_adjmat = M.T.conj() if is_complex else M.T
    A_adj = A.T.conj() if is_complex else A.T

    def adjoint(arg, work):
        np.dot(A_adj, arg[:m], out=work)
        if delta > 0:
            work += sqrt_delta * arg[m:]
        return M_adjmat @ work

    vec_work = np.zeros(A.shape[1], dtype=M.dtype)
    mv = lambda x: forward(x, vec_work)
    rmv = lambda y: adjoint(y, vec_work)
    # if k != 1 then we'd need to allocate workspace differently.
    # (And maybe use workspace differently.)

    A_precond = sparla.LinearOperator(shape=(A_lift.shape[0], M.shape[1]),
                                      matvec=mv, rmatvec=rmv,
                                      dtype=M.dtype)

    M_fwd = lambda z: M @ z
    M_adj = lambda w: M_adjmat @ w

    return A_precond, M_fwd, M_adj


def svd_right_precond(A_ske):
    U, sigma, Vh = la.svd(A_ske, overwrite_a=True, check_finite=False,
                          full_matrices=False)
    eps = np.finfo(float).eps
    rank = np.count_nonzero(sigma > sigma[0] * A_ske.shape[1] * eps)
    Vh = Vh[:rank, :]
    U = U[:, :rank]
    sigma = sigma[:rank]
    V = Vh.T.conj() if law.is_complex(A_ske) else Vh.T
    M = V / sigma
    return M, U, sigma, Vh
