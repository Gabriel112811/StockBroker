primes = [2]

def is_prime_with_primes(n:int) -> bool:
    for i in primes:
        
        if n % i == 0:
            return False

def is_prime(n:int) -> bool:
    if n % 2 == 0:
        return False


