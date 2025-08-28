def sum_two_numbers(first_digit, second_digit):
    return first_digit + second_digit

if __name__ == "__main__":
    a, b = map(int, input().split())
    print(sum_two_numbers(a, b))

