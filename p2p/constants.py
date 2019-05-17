SUPPORTED_RLPX_VERSION = 4

# The p2p protocol version from which Snappy Compression is Enabled
SNAPPY_PROTOCOL_VERSION = 5

# Overhead added by ECIES encryption
ENCRYPT_OVERHEAD_LENGTH = 113

# Lentgh of elliptic S256 signatures
SIGNATURE_LEN = 65

# Length of public keys: 512 bit keys in uncompressed form, without format byte
PUBKEY_LEN = 64

# Hash length (for nonce etc)
HASH_LEN = 32

# Length of initial auth handshake message
AUTH_MSG_LEN = SIGNATURE_LEN + HASH_LEN + PUBKEY_LEN + HASH_LEN + 1

# Length of auth ack handshake message
AUTH_ACK_LEN = PUBKEY_LEN + HASH_LEN + 1

# Length of encrypted pre-EIP-8 initiator handshake
ENCRYPTED_AUTH_MSG_LEN = AUTH_MSG_LEN + ENCRYPT_OVERHEAD_LENGTH

# Length of encrypted pre-EIP-8 handshake reply
ENCRYPTED_AUTH_ACK_LEN = AUTH_ACK_LEN + ENCRYPT_OVERHEAD_LENGTH

# Length of an RLPx packet's header
HEADER_LEN = 16

# Length of an RLPx header's/frame's MAC
MAC_LEN = 16

# The amount of seconds a connection can be idle.
CONN_IDLE_TIMEOUT = 30

# Timeout used when waiting for a reply from a remote node.
REPLY_TIMEOUT = 3
MAX_REQUEST_ATTEMPTS = 3

# Default timeout before giving up on a caller-initiated interaction
COMPLETION_TIMEOUT = 5

MAINNET_BOOTNODES = (
    'enode://a979fb575495b8d6db44f750317d0f4622bf4c2aa3365d6af7c284339968eef29b69ad0dce72a4d8db5ebb4968de0e3bec910127f134779fbcb0cb6d3331163c@52.16.188.185:30303',  # noqa: E501
    'enode://aa36fdf33dd030378a0168efe6ed7d5cc587fafa3cdd375854fe735a2e11ea3650ba29644e2db48368c46e1f60e716300ba49396cd63778bf8a818c09bded46f@13.93.211.84:30303',  # noqa: E501
    'enode://78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d@191.235.84.50:30303',  # noqa: E501
    'enode://158f8aab45f6d19c6cbf4a089c2670541a8da11978a2f90dbf6a502a4a3bab80d288afdbeb7ec0ef6d92de563767f3b1ea9e8e334ca711e9f8e2df5a0385e8e6@13.75.154.138:30303',  # noqa: E501
    'enode://1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082@52.74.57.123:30303',   # noqa: E501

    # Geth Bootnodes
    # from https://github.com/ethereum/go-ethereum/blob/master/params/bootnodes.go
    "enode://3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99@13.93.211.84:30303",  # noqa: E501
    "enode://979b7fa28feeb35a4741660a16076f1943202cb72b6af70d327f053e248bab9ba81760f39d0701ef1d8f89cc1fbd2cacba0710a12cd5314d5e0c9021aa3637f9@5.1.83.226:30303",  # noqa: E501

    # Parity Bootnodes
    # from https://raw.githubusercontent.com/paritytech/parity-ethereum/master/ethcore/res/ethereum/foundation.json  # noqa: E501
    "enode://81863f47e9bd652585d3f78b4b2ee07b93dad603fd9bc3c293e1244250725998adc88da0cef48f1de89b15ab92b15db8f43dc2b6fb8fbd86a6f217a1dd886701@193.70.55.37:30303",  # noqa: E501
    "enode://4afb3a9137a88267c02651052cf6fb217931b8c78ee058bb86643542a4e2e0a8d24d47d871654e1b78a276c363f3c1bc89254a973b00adc359c9e9a48f140686@144.217.139.5:30303",  # noqa: E501
    "enode://c16d390b32e6eb1c312849fe12601412313165df1a705757d671296f1ac8783c5cff09eab0118ac1f981d7148c85072f0f26407e5c68598f3ad49209fade404d@139.99.51.203:30303",  # noqa: E501
    "enode://4faf867a2e5e740f9b874e7c7355afee58a2d1ace79f7b692f1d553a1134eddbeb5f9210dd14dc1b774a46fd5f063a8bc1fa90579e13d9d18d1f59bac4a4b16b@139.99.160.213:30303",  # noqa: E501
    "enode://6a868ced2dec399c53f730261173638a93a40214cf299ccf4d42a76e3fa54701db410669e8006347a4b3a74fa090bb35af0320e4bc8d04cf5b7f582b1db285f5@163.172.131.191:30303",  # noqa: E501
    "enode://66a483383882a518fcc59db6c017f9cd13c71261f13c8d7e67ed43adbbc82a932d88d2291f59be577e9425181fc08828dc916fdd053af935a9491edf9d6006ba@212.47.247.103:30303",  # noqa: E501
    "enode://cd6611461840543d5b9c56fbf088736154c699c43973b3a1a32390cf27106f87e58a818a606ccb05f3866de95a4fe860786fea71bf891ea95f234480d3022aa3@163.172.157.114:30303",  # noqa: E501
    "enode://1d1f7bcb159d308eb2f3d5e32dc5f8786d714ec696bb2f7e3d982f9bcd04c938c139432f13aadcaf5128304a8005e8606aebf5eebd9ec192a1471c13b5e31d49@138.201.223.35:30303",  # noqa: E501
    "enode://0cc5f5ffb5d9098c8b8c62325f3797f56509bff942704687b6530992ac706e2cb946b90a34f1f19548cd3c7baccbcaea354531e5983c7d1bc0dee16ce4b6440b@40.118.3.223:30305",  # noqa: E501
    "enode://1c7a64d76c0334b0418c004af2f67c50e36a3be60b5e4790bdac0439d21603469a85fad36f2473c9a80eb043ae60936df905fa28f1ff614c3e5dc34f15dcd2dc@40.118.3.223:30308",  # noqa: E501
    "enode://85c85d7143ae8bb96924f2b54f1b3e70d8c4d367af305325d30a61385a432f247d2c75c45c6b4a60335060d072d7f5b35dd1d4c45f76941f62a4f83b6e75daaf@40.118.3.223:30309",  # noqa: E501
    "enode://de471bccee3d042261d52e9bff31458daecc406142b401d4cd848f677479f73104b9fdeb090af9583d3391b7f10cb2ba9e26865dd5fca4fcdc0fb1e3b723c786@54.94.239.50:30303",  # noqa: E501
    "enode://4cd540b2c3292e17cff39922e864094bf8b0741fcc8c5dcea14957e389d7944c70278d872902e3d0345927f621547efa659013c400865485ab4bfa0c6596936f@138.201.144.135:30303",  # noqa: E501
    "enode://01f76fa0561eca2b9a7e224378dd854278735f1449793c46ad0c4e79e8775d080c21dcc455be391e90a98153c3b05dcc8935c8440de7b56fe6d67251e33f4e3c@51.15.42.252:30303",  # noqa: E501
    "enode://2c9059f05c352b29d559192fe6bca272d965c9f2290632a2cfda7f83da7d2634f3ec45ae3a72c54dd4204926fb8082dcf9686e0d7504257541c86fc8569bcf4b@163.172.171.38:30303",  # noqa: E501
    "enode://efe4f2493f4aff2d641b1db8366b96ddacfe13e7a6e9c8f8f8cf49f9cdba0fdf3258d8c8f8d0c5db529f8123c8f1d95f36d54d590ca1bb366a5818b9a4ba521c@163.172.187.252:30303",  # noqa: E501
    "enode://bcc7240543fe2cf86f5e9093d05753dd83343f8fda7bf0e833f65985c73afccf8f981301e13ef49c4804491eab043647374df1c4adf85766af88a624ecc3330e@136.243.154.244:30303",  # noqa: E501
    "enode://ed4227681ca8c70beb2277b9e870353a9693f12e7c548c35df6bca6a956934d6f659999c2decb31f75ce217822eefca149ace914f1cbe461ed5a2ebaf9501455@88.212.206.70:30303",  # noqa: E501
    "enode://cadc6e573b6bc2a9128f2f635ac0db3353e360b56deef239e9be7e7fce039502e0ec670b595f6288c0d2116812516ad6b6ff8d5728ff45eba176989e40dead1e@37.128.191.230:30303",  # noqa: E501
    "enode://595a9a06f8b9bc9835c8723b6a82105aea5d55c66b029b6d44f229d6d135ac3ecdd3e9309360a961ea39d7bee7bac5d03564077a4e08823acc723370aace65ec@46.20.235.22:30303",  # noqa: E501
    "enode://029178d6d6f9f8026fc0bc17d5d1401aac76ec9d86633bba2320b5eed7b312980c0a210b74b20c4f9a8b0b2bf884b111fa9ea5c5f916bb9bbc0e0c8640a0f56c@216.158.85.185:30303",  # noqa: E501
    "enode://fdd1b9bb613cfbc200bba17ce199a9490edc752a833f88d4134bf52bb0d858aa5524cb3ec9366c7a4ef4637754b8b15b5dc913e4ed9fdb6022f7512d7b63f181@212.47.247.103:30303",  # noqa: E501
    "enode://cc26c9671dffd3ee8388a7c8c5b601ae9fe75fc0a85cedb72d2dd733d5916fad1d4f0dcbebad5f9518b39cc1f96ba214ab36a7fa5103aaf17294af92a89f227b@52.79.241.155:30303",  # noqa: E501
    "enode://140872ce4eee37177fbb7a3c3aa4aaebe3f30bdbf814dd112f6c364fc2e325ba2b6a942f7296677adcdf753c33170cb4999d2573b5ff7197b4c1868f25727e45@52.78.149.82:30303"  # noqa: E501
)
ROPSTEN_BOOTNODES = (
    'enode://30b7ab30a01c124a6cceca36863ece12c4f5fa68e3ba9b0b51407ccc002eeed3b3102d20a88f1c1d3c3154e2449317b8ef95090e77b312d5cc39354f86d5d606@52.176.7.10:30303',     # noqa: E501
    'enode://865a63255b3bb68023b6bffd5095118fcc13e79dcf014fe4e47e065c350c7cc72af2e53eff895f11ba1bbb6a2b33271c1116ee870f266618eadfc2e78aa7349c@52.176.100.77:30303',   # noqa: E501
    'enode://6332792c4a00e3e4ee0926ed89e0d27ef985424d97b6a45bf0f23e51f0dcb5e66b875777506458aea7af6f9e4ffb69f43f3778ee73c81ed9d34c51c4b16b0b0f@52.232.243.152:30303',  # noqa: E501
    'enode://94c15d1b9e2fe7ce56e458b9a3b672ef11894ddedd0c6f247e0f1d3487f52b66208fb4aeb8179fce6e3a749ea93ed147c37976d67af557508d199d9594c35f09@192.81.208.223:30303',  # noqa: E501
)
DISCOVERY_V5_BOOTNODES = (
    'enode://06051a5573c81934c9554ef2898eb13b33a34b94cf36b202b69fde139ca17a85051979867720d4bdae4323d4943ddf9aeeb6643633aa656e0be843659795007a@35.177.226.168:30303',  # noqa: E501
    'enode://0cc5f5ffb5d9098c8b8c62325f3797f56509bff942704687b6530992ac706e2cb946b90a34f1f19548cd3c7baccbcaea354531e5983c7d1bc0dee16ce4b6440b@40.118.3.223:30304',    # noqa: E501
    'enode://1c7a64d76c0334b0418c004af2f67c50e36a3be60b5e4790bdac0439d21603469a85fad36f2473c9a80eb043ae60936df905fa28f1ff614c3e5dc34f15dcd2dc@40.118.3.223:30306',    # noqa: E501
    'enode://85c85d7143ae8bb96924f2b54f1b3e70d8c4d367af305325d30a61385a432f247d2c75c45c6b4a60335060d072d7f5b35dd1d4c45f76941f62a4f83b6e75daaf@40.118.3.223:30307',    # noqa: E501
)

# Maximum peers number, we'll try to keep open connections up to this number of peers
DEFAULT_MAX_PEERS = 25

# Maximum allowed depth for chain reorgs.
MAX_REORG_DEPTH = 24

# Random sampling rate (i.e. every K-th) for header seal checks during light/fast sync. Apparently
# 100 was the optimal value determined by geth devs
# (https://github.com/ethereum/go-ethereum/pull/1889#issue-47241762), but in order to err on the
# side of caution, we use a higher value.
SEAL_CHECK_RANDOM_SAMPLE_RATE = 48


# The amount of time that the BasePeerPool will wait for a peer to boot before
# aborting the connection attempt.
DEFAULT_PEER_BOOT_TIMEOUT = 20

# Name of the endpoint that the discovery uses to connect to the eventbus
DISCOVERY_EVENTBUS_ENDPOINT = 'discovery'
# Interval at which peer pool requests new connection candidates
PEER_CONNECT_INTERVAL = 2

# Maximum number of sequential connection attempts that can be made before
# hitting the rate limit
MAX_SEQUENTIAL_PEER_CONNECT = 5

# Timeout used when fetching peer candidates from discovery
REQUEST_PEER_CANDIDATE_TIMEOUT = 1

# The maximum number of concurrent attempts to establis new peer connections
MAX_CONCURRENT_CONNECTION_ATTEMPTS = 10

# Amount of time a peer will be blacklisted when they are disconnected as
# `DisconnectReason.bad_protocol`
BLACKLIST_SECONDS_BAD_PROTOCOL = 60 * 10  # 10 minutes

# Amount of time a peer will be blacklisted when they timeout too frequently
BLACKLIST_SECONDS_TOO_MANY_TIMEOUTS = 60 * 5  # 5 minutes

# Both the amount of time that we consider to be a peer disconnecting from us
# too quickly as well as the amount of time they will be blacklisted for doing
# so.
BLACKLIST_SECONDS_QUICK_DISCONNECT = 60
