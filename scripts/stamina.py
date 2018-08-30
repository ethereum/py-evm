import pathlib
import logging
import json
import web3

from pprint import pprint
from web3 import Web3
from solc import compile_source
from web3.contract import ConciseContract

from scripts.benchmark.utils.chain_plumbing import (
    get_chain,
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY
)

from eth.constants import (
    CREATE_CONTRACT_ADDRESS
)

from eth.vm.forks.byzantium import (
    ByzantiumVM,
)

from eth.vm.forks.frontier import (
    FrontierVM,
)

from eth.chains.base import (
    MiningChain,
)

from scripts.benchmark.utils.tx import (
    new_transaction,
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

from scripts.benchmark.utils.compile import (
    get_compiled_contract
)

FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000
TRANSFER_AMOUNT = 1000
TRANSER_FROM_AMOUNT = 1

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:30303"))

contract_source_code = '''
pragma solidity ^0.4.23;


contract Stamina {
  struct Withdrawal {
    uint128 amount;
    uint128 requestBlockNumber;
    address delegatee;
    bool processed;
  }

  /**
   * Internal States
   */
  // delegatee of `delegator` account
  // `delegator` => `delegatee`
  mapping (address => address) _delegatee;

  // stamina of delegatee
  // `delegatee` => `stamina`
  mapping (address => uint) _stamina;

  // total deposit of delegatee
  // `delegatee` => `total deposit`
  mapping (address => uint) _total_deposit;

  // deposit of delegatee
  // `depositor` => `delegatee` => `deposit`
  mapping (address => mapping (address => uint)) _deposit;

  // last recovery block of delegatee
  mapping (address => uint256) _last_recovery_block;

  // depositor => [index] => Withdrawal
  mapping (address => Withdrawal[]) _withdrawal;
  mapping (address => uint256) _last_processed_withdrawal;
  mapping (address => uint) _num_recovery;

  /**
   * Public States
   */
  bool public initialized;

  uint public MIN_DEPOSIT;
  uint public RECOVER_EPOCH_LENGTH; // stamina is recovered when block number % RECOVER_DELAY == 0
  uint public WITHDRAWAL_DELAY;     // Refund will be made WITHDRAWAL_DELAY blocks after depositor request Withdrawal.
                                    // WITHDRAWAL_DELAY prevents immediate withdrawal.
                                    // RECOVER_EPOCH_LENGTH * 2 < WITHDRAWAL_DELAY


  bool public development = true;

  modifier onlyChain() {
    require(development || msg.sender == address(0));
    _;
  }

  modifier onlyInitialized() {
    require(initialized);
    _;
  }

  event Deposited(address indexed depositor, address indexed delegatee, uint amount);
  event DelegateeChanged(address delegator, address oldDelegatee, address newDelegatee);
  event WithdrawalRequested(address indexed depositor, address indexed delegatee, uint amount, uint requestBlockNumber, uint withdrawalIndex);
  event Withdrawn(address indexed depositor, address indexed delegatee, uint amount, uint withdrawalIndex);

  function init(uint minDeposit, uint recoveryEpochLength, uint withdrawalDelay) external {
    require(!initialized);

    require(minDeposit > 0);
    require(recoveryEpochLength > 0);
    require(withdrawalDelay > 0);

    require(recoveryEpochLength * 2 < withdrawalDelay);

    MIN_DEPOSIT = minDeposit;
    RECOVER_EPOCH_LENGTH = recoveryEpochLength;
    WITHDRAWAL_DELAY = withdrawalDelay;

    initialized = true;
  }

  function getDelegatee(address delegator) public view returns (address) {
    return _delegatee[delegator];
  }

  function getStamina(address addr) public view returns (uint) {
    return _stamina[addr];
  }

  function getTotalDeposit(address delegatee) public view returns (uint) {
    return _total_deposit[delegatee];
  }

  function getDeposit(address depositor, address delegatee) public view returns (uint) {
    return _deposit[depositor][delegatee];
  }

  function getNumWithdrawals(address depositor) public view returns (uint) {
    return _withdrawal[depositor].length;
  }

  function getLastRecoveryBlock(address delegatee) public view returns (uint) {
    return _last_recovery_block[delegatee];
  }

  function getNumRecovery(address delegatee) public view returns (uint) {
    return _num_recovery[delegatee];
  }

  function getWithdrawal(address depositor, uint withdrawalIndex)
    public
    view
    returns (uint128 amount, uint128 requestBlockNumber, address delegatee, bool processed)
  {
    require(withdrawalIndex < getNumWithdrawals(depositor));

    Withdrawal memory w = _withdrawal[depositor][withdrawalIndex];

    amount = w.amount;
    requestBlockNumber = w.requestBlockNumber;
    delegatee = w.delegatee;
    processed = w.processed;
  }

  function setDelegator(address delegator)
    external
    onlyInitialized
    returns (bool)
  {
    address oldDelegatee = _delegatee[delegator];

    _delegatee[delegator] = msg.sender;

    emit DelegateeChanged(delegator, oldDelegatee, msg.sender);
    return true;
  }

  function deposit(address delegatee)
    external
    payable
    onlyInitialized
    returns (bool)
  {
    require(msg.value >= MIN_DEPOSIT);

    uint totalDeposit = _total_deposit[delegatee];
    uint deposit = _deposit[msg.sender][delegatee];
    uint stamina = _stamina[delegatee];

    require(totalDeposit + msg.value > totalDeposit);
    require(deposit + msg.value > deposit);
    require(stamina + msg.value > stamina);

    _total_deposit[delegatee] = totalDeposit + msg.value;
    _deposit[msg.sender][delegatee] = deposit + msg.value;
    _stamina[delegatee] = stamina + msg.value;

    if (_last_recovery_block[delegatee] == 0) {
      _last_recovery_block[delegatee] = block.number;
    }

    emit Deposited(msg.sender, delegatee, msg.value);
    return true;
  }

  function requestWithdrawal(address delegatee, uint amount)
    external
    onlyInitialized
    returns (bool)
  {
    require(amount > 0);

    uint totalDeposit = _total_deposit[delegatee];
    uint deposit = _deposit[msg.sender][delegatee];
    uint stamina = _stamina[delegatee];

    require(deposit > 0);

    require(totalDeposit - amount < totalDeposit);
    require(deposit - amount < deposit); // this guarentees deposit >= amount

    _total_deposit[delegatee] = totalDeposit - amount;
    _deposit[msg.sender][delegatee] = deposit - amount;

    if (stamina > amount) {
      _stamina[delegatee] = stamina - amount;
    } else {
      _stamina[delegatee] = 0;
    }

    Withdrawal[] storage withdrawals = _withdrawal[msg.sender];

    uint withdrawalIndex = withdrawals.length;
    Withdrawal storage withdrawal = withdrawals[withdrawals.length++];

    withdrawal.amount = uint128(amount);
    withdrawal.requestBlockNumber = uint128(block.number);
    withdrawal.delegatee = delegatee;

    emit WithdrawalRequested(msg.sender, delegatee, amount, block.number, withdrawalIndex);
    return true;
  }

  function withdraw() external returns (bool) {
    Withdrawal[] storage withdrawals = _withdrawal[msg.sender];
    require(withdrawals.length > 0);

    uint lastWithdrawalIndex = _last_processed_withdrawal[msg.sender];
    uint withdrawalIndex;

    if (lastWithdrawalIndex == 0 && !withdrawals[0].processed) {
      withdrawalIndex = 0;
    } else if (lastWithdrawalIndex == 0) { // lastWithdrawalIndex == 0 && withdrawals[0].processed
      require(withdrawals.length >= 2);

      withdrawalIndex = 1;
    } else {
      withdrawalIndex = lastWithdrawalIndex + 1;
    }

    require(withdrawalIndex < withdrawals.length);

    Withdrawal storage withdrawal = _withdrawal[msg.sender][withdrawalIndex];

    require(!withdrawal.processed);
    require(withdrawal.requestBlockNumber + WITHDRAWAL_DELAY <= block.number);

    uint amount = uint(withdrawal.amount);

    withdrawal.processed = true;
    _last_processed_withdrawal[msg.sender] = withdrawalIndex;

    msg.sender.transfer(amount);
    emit Withdrawn(msg.sender, withdrawal.delegatee, amount, withdrawalIndex);

    return true;
  }

  function addStamina(address delegatee, uint amount) external onlyChain returns (bool) {
    if (_last_recovery_block[delegatee] + RECOVER_EPOCH_LENGTH <= block.number) {
      _stamina[delegatee] = _total_deposit[delegatee];
      _last_recovery_block[delegatee] = block.number;
      _num_recovery[delegatee] += 1;

      return true;
    }

    uint totalDeposit = _total_deposit[delegatee];
    uint stamina = _stamina[delegatee];

    require(stamina + amount > stamina);
    uint targetBalance = stamina + amount;

    if (targetBalance > totalDeposit) _stamina[delegatee] = totalDeposit;
    else _stamina[delegatee] = targetBalance;

    return true;
  }

  function subtractStamina(address delegatee, uint amount) external onlyChain returns (bool) {
    uint stamina = _stamina[delegatee];

    require(stamina - amount < stamina);
    _stamina[delegatee] = stamina - amount;
    return true;
  }
}
'''

another_contract = '''
pragma solidity ^0.4.23;


/**
 * @title SafeMath
 * @dev Math operations with safety checks that throw on error
 */
library SafeMath {

  /**
  * @dev Multiplies two numbers, throws on overflow.
  */
  function mul(uint256 a, uint256 b) internal pure returns (uint256 c) {
    // Gas optimization: this is cheaper than asserting 'a' not being zero, but the
    // benefit is lost if 'b' is also tested.
    // See: https://github.com/OpenZeppelin/openzeppelin-solidity/pull/522
    if (a == 0) {
      return 0;
    }

    c = a * b;
    assert(c / a == b);
    return c;
  }

  /**
  * @dev Integer division of two numbers, truncating the quotient.
  */
  function div(uint256 a, uint256 b) internal pure returns (uint256) {
    // assert(b > 0); // Solidity automatically throws when dividing by 0
    // uint256 c = a / b;
    // assert(a == b * c + a % b); // There is no case in which this doesn't hold
    return a / b;
  }

  /**
  * @dev Subtracts two numbers, throws on overflow (i.e. if subtrahend is greater than minuend).
  */
  function sub(uint256 a, uint256 b) internal pure returns (uint256) {
    assert(b <= a);
    return a - b;
  }

  /**
  * @dev Adds two numbers, throws on overflow.
  */
  function add(uint256 a, uint256 b) internal pure returns (uint256 c) {
    c = a + b;
    assert(c >= a);
    return c;
  }
}



/**
 * @title ERC20Basic
 * @dev Simpler version of ERC20 interface
 * @dev see https://github.com/ethereum/EIPs/issues/179
 */
contract ERC20Basic {
  function totalSupply() public view returns (uint256);
  function balanceOf(address who) public view returns (uint256);
  function transfer(address to, uint256 value) public returns (bool);
  event Transfer(address indexed from, address indexed to, uint256 value);
}


/**
 * @title Basic token
 * @dev Basic version of StandardToken, with no allowances.
 */
contract BasicToken is ERC20Basic {
  using SafeMath for uint256;

  mapping(address => uint256) balances;

  uint256 totalSupply_;

  /**
  * @dev total number of tokens in existence
  */
  function totalSupply() public view returns (uint256) {
    return totalSupply_;
  }

  /**
  * @dev transfer token for a specified address
  * @param _to The address to transfer to.
  * @param _value The amount to be transferred.
  */
  function transfer(address _to, uint256 _value) public returns (bool) {
    require(_to != address(0));
    require(_value <= balances[msg.sender]);

    balances[msg.sender] = balances[msg.sender].sub(_value);
    balances[_to] = balances[_to].add(_value);
    emit Transfer(msg.sender, _to, _value);
    return true;
  }

  /**
  * @dev Gets the balance of the specified address.
  * @param _owner The address to query the the balance of.
  * @return An uint256 representing the amount owned by the passed address.
  */
  function balanceOf(address _owner) public view returns (uint256) {
    return balances[_owner];
  }

}


/**
 * @title ERC20 interface
 * @dev see https://github.com/ethereum/EIPs/issues/20
 */
contract ERC20 is ERC20Basic {
  function allowance(address owner, address spender)
    public view returns (uint256);

  function transferFrom(address from, address to, uint256 value)
    public returns (bool);

  function approve(address spender, uint256 value) public returns (bool);
  event Approval(
    address indexed owner,
    address indexed spender,
    uint256 value
  );
}


/**
 * @title Standard ERC20 token
 *
 * @dev Implementation of the basic standard token.
 * @dev https://github.com/ethereum/EIPs/issues/20
 * @dev Based on code by FirstBlood: https://github.com/Firstbloodio/token/blob/master/smart_contract/FirstBloodToken.sol
 */
contract StandardToken is ERC20, BasicToken {

  mapping (address => mapping (address => uint256)) internal allowed;


  /**
   * @dev Transfer tokens from one address to another
   * @param _from address The address which you want to send tokens from
   * @param _to address The address which you want to transfer to
   * @param _value uint256 the amount of tokens to be transferred
   */
  function transferFrom(
    address _from,
    address _to,
    uint256 _value
  )
    public
    returns (bool)
  {
    require(_to != address(0));
    require(_value <= balances[_from]);
    require(_value <= allowed[_from][msg.sender]);

    balances[_from] = balances[_from].sub(_value);
    balances[_to] = balances[_to].add(_value);
    allowed[_from][msg.sender] = allowed[_from][msg.sender].sub(_value);
    emit Transfer(_from, _to, _value);
    return true;
  }

  /**
   * @dev Approve the passed address to spend the specified amount of tokens on behalf of msg.sender.
   *
   * Beware that changing an allowance with this method brings the risk that someone may use both the old
   * and the new allowance by unfortunate transaction ordering. One possible solution to mitigate this
   * race condition is to first reduce the spender's allowance to 0 and set the desired value afterwards:
   * https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729
   * @param _spender The address which will spend the funds.
   * @param _value The amount of tokens to be spent.
   */
  function approve(address _spender, uint256 _value) public returns (bool) {
    allowed[msg.sender][_spender] = _value;
    emit Approval(msg.sender, _spender, _value);
    return true;
  }

  /**
   * @dev Function to check the amount of tokens that an owner allowed to a spender.
   * @param _owner address The address which owns the funds.
   * @param _spender address The address which will spend the funds.
   * @return A uint256 specifying the amount of tokens still available for the spender.
   */
  function allowance(
    address _owner,
    address _spender
   )
    public
    view
    returns (uint256)
  {
    return allowed[_owner][_spender];
  }

  /**
   * @dev Increase the amount of tokens that an owner allowed to a spender.
   *
   * approve should be called when allowed[_spender] == 0. To increment
   * allowed value is better to use this function to avoid 2 calls (and wait until
   * the first transaction is mined)
   * From MonolithDAO Token.sol
   * @param _spender The address which will spend the funds.
   * @param _addedValue The amount of tokens to increase the allowance by.
   */
  function increaseApproval(
    address _spender,
    uint _addedValue
  )
    public
    returns (bool)
  {
    allowed[msg.sender][_spender] = (
      allowed[msg.sender][_spender].add(_addedValue));
    emit Approval(msg.sender, _spender, allowed[msg.sender][_spender]);
    return true;
  }

  /**
   * @dev Decrease the amount of tokens that an owner allowed to a spender.
   *
   * approve should be called when allowed[_spender] == 0. To decrement
   * allowed value is better to use this function to avoid 2 calls (and wait until
   * the first transaction is mined)
   * From MonolithDAO Token.sol
   * @param _spender The address which will spend the funds.
   * @param _subtractedValue The amount of tokens to decrease the allowance by.
   */
  function decreaseApproval(
    address _spender,
    uint _subtractedValue
  )
    public
    returns (bool)
  {
    uint oldValue = allowed[msg.sender][_spender];
    if (_subtractedValue > oldValue) {
      allowed[msg.sender][_spender] = 0;
    } else {
      allowed[msg.sender][_spender] = oldValue.sub(_subtractedValue);
    }
    emit Approval(msg.sender, _spender, allowed[msg.sender][_spender]);
    return true;
  }

}


contract SimpleToken is StandardToken {

  string public constant name = "SimpleToken"; // solium-disable-line uppercase
  string public constant symbol = "SIM"; // solium-disable-line uppercase
  uint8 public constant decimals = 18; // solium-disable-line uppercase

  uint256 public constant INITIAL_SUPPLY = 10000 * (10 ** uint256(decimals));

  /**
   * @dev Constructor that gives msg.sender all of existing tokens.
   */
  constructor() public {
    totalSupply_ = INITIAL_SUPPLY;
    balances[msg.sender] = INITIAL_SUPPLY;
    emit Transfer(0x0, msg.sender, INITIAL_SUPPLY);
  }

}
'''

def run() -> None:
    # get Byzantium VM
    chain = get_chain(ByzantiumVM)
    _deploy_stamina(chain)

def _deploy_stamina(chain: MiningChain) -> None:

    compiled_sol = compile_source(contract_source_code) # Compiled source code
    contract_interface = compiled_sol['<stdin>:Stamina']

    # Instantiate and deploy contract
    SimpleToken = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

    # Build transaction to deploy the contract
    w3_tx = SimpleToken.constructor().buildTransaction(W3_TX_DEFAULTS)
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=CREATE_CONTRACT_ADDRESS,
        amount=0,
        gas=FIRST_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)
    # Keep track of deployed contract address
    deployed_contract_address = computation.msg.storage_address

    print(computation.is_success)
    assert computation.is_success
    # Keep track of simple_token object

    # chain.mine_block()
    # # print(computation.is_success)
    # print(deployed_contract_address)
    #
    a = chain.get_vm().state.account_db.get_code(deployed_contract_address)
    print(a)

if __name__ == '__main__':
    run()
