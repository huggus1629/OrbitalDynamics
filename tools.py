def digits_after_decimal(x):
	return len(str(float(x)).split('.')[1])


# flips sign of vector
def vec_neg(vec: tuple[float, ...]):
	return tuple(- comp for comp in vec)


# sums up a list of vectors
def vec_sum(l_vec: list[tuple[float, ...]]):
	dim = len(l_vec[0])  # determine the dimension of the vector by counting its components
	fres = [0.0 for _ in range(dim)]  # initialize Fres vector with zeroes
	for vec in l_vec:
		if len(vec) != dim:  # if the vectors don't have matching dimensions, return None
			return None
		for i in range(dim):
			# for every component, add it to the corresponding component in Fres
			fres[i] += vec[i]

	return tuple(fres)


# multiplies vector by scalar
def vec_mul(vec: tuple[float, ...], s):
	return tuple(s * comp for comp in vec)
