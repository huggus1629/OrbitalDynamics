def digits_after_decimal(x):
	return len(str(float(x)).split('.')[1])


def vec_neg(vec: tuple):
	return tuple(- comp for comp in vec)
