def digits_after_decimal(x):
	return len(str(float(x)).split('.')[1])


# flips sign of vector
def vec_neg(vec: tuple):
	return tuple(- comp for comp in vec)


# sums up a list of vectors
def vec_sum(l_vec: list[tuple]):
	dim = len(l_vec[0])
	fres = [0 for _ in range(dim)]
	for vec in l_vec:
		if len(vec) != dim:
			return
		for i in range(dim):
			fres[i] += vec[i]

	return tuple(fres)
