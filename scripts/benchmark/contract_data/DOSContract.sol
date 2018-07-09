pragma solidity ^0.4.23;

contract DOSContract{
    address[] deployedContracts;
    uint64[] liste;
   
    function createEmptyContract() public{
        address newContract = new EmptyContract();
        deployedContracts.push(newContract);
    }

    function storageEntropy() public{
        liste.push(1);
    }

    function storageEntropyRevert() public{
        liste.push(1);
        revert("Error");
    }

    function createEmptyContractRevert() public{
        address newContract = new EmptyContract();
        deployedContracts.push(newContract);
        revert();
    }
}

contract EmptyContract{

}