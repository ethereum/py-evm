pragma solidity ^0.5.7;

// FillStorage churns storage on each shuffle() call

contract FillStorage {
    mapping(uint => uint) public balances;

    constructor () public {
        balances[0] = 1;
    }

    function shuffle(uint shuffle_width) public {
        for(uint i = 0; i<shuffle_width; i++) {
            if (balances[i+1] == balances[i] - 1) {
                balances[i+1] = balances[i];
                return;
            }
        }
        balances[0] += 1;
    }

    function delete_index(uint index) public {
        delete balances[index];
    }
}
"""
