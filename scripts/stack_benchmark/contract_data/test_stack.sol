pragma solidity >=0.4.23;

contract TestStack {
	function doLotsOfPops() public{
		uint v = 0;
		for (uint i=0; i<100; i++) {
			v += 100;
		}
	}
}
