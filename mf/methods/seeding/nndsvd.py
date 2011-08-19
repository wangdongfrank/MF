
from mf.utils.utils import *
from mf.utils.linalg import *

class Nndsvd(object):
    """
    Nonnegative Double Singular Value Decomposition (NNDSVD) [1] is a new method designed to enhance the initialization
    stage of the nonnegative matrix factorization. The basic algorithm contains no randomization and is based on 
    two SVD processes, one approximating the data matrix, the other approximating positive sections of the 
    resulting partial SVD factors utilizing an algebraic property of unit rank matrices. 
    
    NNDSVD is well suited to initialize NMF algorithms with sparse factors. Numerical examples suggest that NNDSVD leads 
    to rapid reduction of the approximation error of many NMF algorithms. By setting algorithm options :param:`flag` dense factors can be
    generated. 
    
    [1] Boutsidis, C., Gallopoulos, E., (2007). SVD-based initialization: A head start for nonnegative matrix factorization, Pattern Recognition, 2007,
    doi:10.1016/j.patcog.2007.09.010.
    """

    def __init__(self):
        self.name = "nndsvd"
        
    def initialize(self, V, rank, options):
        """
        Return initialized basis and mixture matrix. 
        
        Initialized matrices are sparse :class:`scipy.sparse.csr_matrix` if NNDSVD variant is specified by the :param:`flag` option,
        else matrices are :class:`numpy.matrix`.
        
        :param V: Target matrix, the matrix for MF method to estimate. Data instances to be clustered. 
        :type V: :class:`scipy.sparse` of format csr, csc, coo, bsr, dok, lil, dia or :class:`numpy.matrix`
        :param rank: Factorization rank. 
        :type rank: `int`
        :param options: Specify algorithm or model specific options (e.g. initialization of extra matrix factor, seeding parameters).
                        :param flag: Indicate the variant of the NNDSVD algorithm. Possible values are:
                                     #. 0 -- NNDSVD,
                                     #. 1 -- NNDSVDa (fill in the zero elements with the average),
                                     #. 2 -- NNDSVDar (fill in the zero elements with random values in the space [0:average/100]).
                                    Default is NNDSVD.
                                    Because of the nature of NNDSVDa and NNDSVDar, when the target matrix is sparse, only NNDSVD is possible
                                    and :param:`flag` is ignored (NNDSVDa and NNDSVDar eliminate zero elements). 
                        :type flag: `int`
        """
        self.rank = rank
        self.flag = options.get('flag', 0)
        if negative(V):
            raise MFError("The input matrix contains negative elements.")
        U, S, E = svd(V)
        if sp.isspmatrix(U):
            return self._init_sparse(V, U, S, E)
        self.W = np.mat(np.zeros((V.shape[0], self.rank)))
        self.H = np.mat(np.zeros((self.rank, V.shape[1])))
        # choose the first singular triplet to be nonnegative
        self.W[:, 0] = sqrt(S[0]) * abs(U[:, 0])
        self.H[0, :] = sqrt(S[0]) * abs(E[:, 0].T)
        # second svd for the other factors
        for i in xrange(1, self.rank):
            uu = U[:, i]
            vv = E[:, i]
            uup = self._pos(uu)
            uun = self._neg(uu)
            vvp = self._pos(vv)
            vvn = self._neg(vv)
            n_uup = norm(uup, 2)
            n_vvp = norm(vvp, 2)
            n_uun = norm(uun, 2)
            n_vvn = norm(vvn, 2)
            termp = n_uup * n_vvp; termn = n_uun * n_vvn
            if (termp >= termn):
                self.W[:, i] = sqrt(S[i] * termp) / n_uup * uup 
                self.H[i, :] = sqrt(S[i] * termp) / n_vvp * vvp.T 
            else:
                self.W[:, i] = sqrt(S[i] * termn) / n_uun * uun
                self.H[i, :] = sqrt(S[i] * termn) / n_vvn * vvn.T
        self.W[self.W < 1e-11] = 0
        self.H[self.H < 1e-11] = 0
        # NNDSVD 
        if self.flag == 0:
            return sp.csr_matrix(self.W), sp.csr_matrix(self.H)
        # NNDSVDa
        if self.flag == 1:
            avg = V.mean()
            self.W[self.W == 0] = avg
            self.H[self.H == 0] = avg
        # NNDSVDar
        if self.flag == 2:
            avg = V.mean()
            n1 = len(self.W[self.W == 0])
            n2 = len(self.H[self.H == 0])
            self.W[self.W == 0] = avg * np.random.uniform(n1, 1) / 100
            self.H[self.H == 0] = avg * np.random.uniform(n2, 1) / 100
        return self.W, self.H
    
    def _init_sparse(self, V, U, S, E):
        """
        Continue the NNDSVD initialization of sparse target matrix.
        
        :param V: Target matrix
        :type V: :class:`scipy.sparse` of format csr, csc, coo, bsr, dok, lil, dia
        :param U: Left singular vectors.
        :type U: :class:`scipy.sparse` of format csr, csc, coo, bsr, dok, lil, dia
        :param E: Right singular vectors.
        :type E: :class:`scipy.sparse` of format csr, csc, coo, bsr, dok, lil, dia
        :param S: Singular values.
        :type S: :class:`scipy.sparse` of format csr, csc, coo, bsr, dok, lil, dia
        """
        # LIL sparse format is convenient for construction
        self.W = sp.lil_matrix((V.shape[0], self.rank))
        self.H = sp.lil_matrix((self.rank, V.shape[1]))
        # scipy.sparse.linalg ARPACK does not allow computation of rank(V) eigenvectors
        # fill the missing columns/rows with random values
        prng = np.random.RandomState()
        S = [S[i, i] for i in xrange(np.min([S.shape[0], S.shape[1]]))] 
        S += [prng.rand() for _ in xrange(self.rank - len(S))]
        U = U.tolil()
        E = E.tolil()
        temp_U = sp.lil_matrix((V.shape[0], V.shape[0]))
        temp_E = sp.lil_matrix((V.shape[1], V.shape[1]))
        if temp_U.shape != U.shape:
            temp_U[:, :U.shape[1]] = U
            temp_U[:, U.shape[1]:] = sp.rand(U.shape[0], temp_U.shape[1] - U.shape[1], density = 0.8, format = 'lil')
        U = temp_U
        if temp_E.shape != E.shape:
            temp_E[:E.shape[0], :] = E
            temp_E[E.shape[0]:, :] = sp.rand(temp_E.shape[0] - E.shape[0], E.shape[1], density = 0.8, format = 'lil')
        E = temp_E
        # choose the first singular triplet to be nonnegative
        self.W[:, 0] = sqrt(S[0]) * abs(U[:, 0])
        self.H[0, :] = sqrt(S[0]) * abs(E[:, 0].T)
        # second svd for the other factors
        for i in xrange(1, self.rank):
            uu = U[:, i]
            vv = E[:, i]
            uup = self._pos(uu)
            uun = self._neg(uu)
            vvp = self._pos(vv)
            vvn = self._neg(vv)
            n_uup = norm(uup, 2)
            n_vvp = norm(vvp, 2)
            n_uun = norm(uun, 2)
            n_vvn = norm(vvn, 2)
            termp = n_uup * n_vvp; termn = n_uun * n_vvn
            if (termp >= termn):
                self.W[:, i] = sqrt(S[i] * termp) / n_uup * uup 
                self.H[i, :] = sqrt(S[i] * termp) / n_vvp * vvp.T 
            else:
                self.W[:, i] = sqrt(S[i] * termn) / n_uun * uun
                self.H[i, :] = sqrt(S[i] * termn) / n_vvn * vvn.T
        # CSR sparse format is convenient for fast arithmetic and matrix vector operations
        self.W = self.W.tocsr()
        self.H = self.H.tocsr()
        return self.W, self.H
            
    def _pos(self, X):
        """Return positive section of matrix or vector."""
        if sp.isspmatrix(X):
            return multiply(sop(X, 0, ge), X)
        else:
            return multiply(X >= 0, X)
    
    def _neg(self, X):
        """Return negative section of matrix or vector."""
        if sp.isspmatrix(X):
            return multiply(sop(X, 0, le), - X)
        else:
            return multiply(X < 0, -X)
    
    def __repr__(self):
        return "nndsvd.Nndsvd()"
    
    def __str__(self):
        return self.name
            
            
            
        