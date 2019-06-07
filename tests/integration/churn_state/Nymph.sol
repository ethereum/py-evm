pragma solidity ^0.5.7;

// Nymph exists purely to be deleted later

contract Nymph {
    function poof() public {
        selfdestruct(msg.sender);
    }
}
