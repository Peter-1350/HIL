import random
import time


# Initialize once from the current time; calls then consume the same random stream.
random.seed(time.time_ns())


def RandomUniform(min_value=0.0, max_value=100.0):
    """Generate a uniform random value in the [min_value, max_value] range."""
    return random.uniform(min_value, max_value)
