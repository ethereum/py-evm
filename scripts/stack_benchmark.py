#!/usr/bin/env python

import time

from eth.vm.stack import (
    Stack,
    Stack_Old,
)


def push_benchmark():
    stack = Stack()
    uint_max = 2**32 - 1

    start_time = time.perf_counter()
    for _ in range(500):
        stack.push(uint_max)
        stack.push(b'\x00' * 32)
    time_taken_refactored = time.perf_counter() - start_time

    stack_old = Stack_Old()
    start_time = time.perf_counter()
    for _ in range(500):
        stack_old.push(uint_max)
        stack_old.push(b'\x00' * 32)
    time_taken_old = time.perf_counter() - start_time

    return time_taken_refactored, time_taken_old


def pop_benchmark1():
    # This is a case which favours the new built Stack
    stack = Stack()
    stack_old = Stack_Old()

    for stack_obj in (stack, stack_old):
        for _ in range(1000):
            stack_obj.push(b'\x00' * 32)

    start_time = time.perf_counter()
    stack.pop_n(1000)
    time_taken_refactored = time.perf_counter() - start_time

    start_time = time.perf_counter()
    stack_old.pop(1000, "uint256")
    time_taken_old = time.perf_counter() - start_time

    return time_taken_refactored, time_taken_old


def pop_benchmark2():
    # This is a case which favours the old Stack
    stack = Stack()
    stack_old = Stack_Old()

    for stack_obj in (stack, stack_old):
        for _ in range(1000):
            stack_obj.push(b'\x00' * 32)

    start_time = time.perf_counter()
    stack.pop_n(1000)
    time_taken_refactored = time.perf_counter() - start_time

    start_time = time.perf_counter()
    stack_old.pop(1000, "bytes")
    time_taken_old = time.perf_counter() - start_time

    return time_taken_refactored, time_taken_old


#push_benchmark()
#pop_benchmark1()
#pop_benchmark2()

def main():
    print("Stack Push of 500 bytestrings and 500 integers")
    print("----------------------------------------------")
    refactored_time, old_time = push_benchmark()
    print("Old Code\t\t|\t{}".format(old_time))
    print("Refactored Code\t\t|\t{}".format(refactored_time))
    print("\n\n")
    
    print("Stack Pop 1000 times (Pushed 1000 bytestrings)(For old one, expected popped output in int)")
    print("----------------------------------------------")
    refactored_time, old_time = pop_benchmark1()
    print("Old Code\t\t|\t{}".format(old_time))
    print("Refactored Code\t\t|\t{}".format(refactored_time))
    print("\n\n")

    print("Stack Pop 1000 times (Pushed 1000 bytestrings)(For old one, expected popped output in bytes)")
    print("----------------------------------------------")
    refactored_time, old_time = pop_benchmark2()
    print("Old Code\t\t|\t{}".format(old_time))
    print("Refactored Code\t\t|\t{}".format(refactored_time))


main()
